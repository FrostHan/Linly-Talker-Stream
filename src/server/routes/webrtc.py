# Linly-Talker-Stream (https://github.com/Kedreamix/Linly-Talker-Stream). Copyright [Linly-talker-stream@kedreamix]. Apache-2.0.
# Based on LiveTalking (C) 2024 LiveTalking@lipku https://github.com/lipku/LiveTalking (Apache-2.0).

"""WebRTC 相关路由"""
import json
import os
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceServer, RTCConfiguration
from aiortc.rtcrtpsender import RTCRtpSender
import asyncio

from src.utils.webrtc import HumanPlayer
from src.avatars.factory import create_avatar
from src.utils.logging import logger
from src.server.state import state
from src.server.utils import randN


_DEFAULT_STUN = 'stun:stun.cloudflare.com:3478'

# 国内可达的公开 STUN（Cloudflare 在部分中国移动 / 电信网络下可能被丢弃）。
# 给前端多几个选择，浏览器会并行尝试，谁先通用谁。
_FALLBACK_STUNS = [
    'stun:stun.miwifi.com:3478',         # 小米
    'stun:stun.qq.com:3478',             # 腾讯
    'stun:stun.l.google.com:19302',      # Google（部分网络可达）
]


def _load_ice_servers_dicts():
    """
    返回 iceServers 列表（dict 格式，可直接 JSON 发给前端）。
    优先级：
      1. 环境变量 ICE_SERVERS_JSON —— 完整 JSON。
         例：'[{"urls":["turn:t.example.com:3478"],"username":"u","credential":"c"}]'
      2. 环境变量 TURN_URL [+ TURN_USERNAME + TURN_CREDENTIAL]。
         TURN_URL 可以是逗号分隔多个 URL。
      3. 都没设，退回 STUN-only（仅本机局域网能走通）。

    无论哪种来源，最终都会追加几个国内可达的备用 STUN，提升中国大陆客户端拿到
    server-reflexive candidate 的概率。
    """
    fallback = [{'urls': [s]} for s in _FALLBACK_STUNS]

    raw = os.environ.get('ICE_SERVERS_JSON', '').strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list) and data:
                return data + fallback
        except Exception as e:
            logger.warning('ICE_SERVERS_JSON 解析失败，忽略：%s', e)

    turn_url = os.environ.get('TURN_URL', '').strip()
    if turn_url:
        urls = [u.strip() for u in turn_url.split(',') if u.strip()]
        entry = {'urls': urls}
        if os.environ.get('TURN_USERNAME'):
            entry['username'] = os.environ['TURN_USERNAME']
        if os.environ.get('TURN_CREDENTIAL'):
            entry['credential'] = os.environ['TURN_CREDENTIAL']
        return [{'urls': [_DEFAULT_STUN]}, entry] + fallback

    return [{'urls': [_DEFAULT_STUN]}] + fallback


def _to_aiortc_servers(dicts):
    """dict 转 aiortc 的 RTCIceServer 对象列表。"""
    out = []
    for d in dicts:
        urls = d.get('urls')
        if not urls:
            continue
        out.append(RTCIceServer(
            urls=urls,
            username=d.get('username'),
            credential=d.get('credential'),
        ))
    return out


async def get_ice_config(request):
    """前端 GET /ice：拿到服务器上设定的 ICE 服务器配置。"""
    return web.json_response({'iceServers': _load_ice_servers_dicts()})


async def offer(request):
    """处理 WebRTC offer 请求"""
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    
    sessionid = randN(6)
    state.add_session(sessionid, None)
    logger.info('sessionid=%d, session num=%d', sessionid, len(state.avatar_streams))
    
    # 创建 avatar 可能耗时，放线程池
    avatar_stream = await asyncio.get_event_loop().run_in_executor(
        None, create_avatar, state.config, state.model, state.avatar, sessionid
    )
    state.add_session(sessionid, avatar_stream)
    
    ice_servers = _to_aiortc_servers(_load_ice_servers_dicts())
    pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=ice_servers))
    state.add_peer_connection(pc, sessionid=sessionid)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info("sessionid=%d Connection state is %s", sessionid, pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            state.remove_peer_connection(pc)
            state.remove_session(sessionid)
        if pc.connectionState == "closed":
            state.remove_peer_connection(pc)
            state.remove_session(sessionid)

    # 部分浏览器/网络场景 connectionstatechange 不会从 connected 跳到 failed/closed，
    # 但 ICE 层会更早地报 disconnected/failed。这里给 30s 宽限期再清。
    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        ice_state = pc.iceConnectionState
        logger.info("sessionid=%d ICE state is %s", sessionid, ice_state)
        if ice_state in ("failed", "closed"):
            try:
                await pc.close()
            except Exception:
                pass
            state.remove_peer_connection(pc)
            state.remove_session(sessionid)
        elif ice_state == "disconnected":
            # 30s 后再看，仍然没恢复就清掉
            async def _grace_close():
                await asyncio.sleep(30)
                if pc.iceConnectionState == "disconnected":
                    logger.warning("sessionid=%d ICE 30s 仍 disconnected，主动关闭", sessionid)
                    try:
                        await pc.close()
                    except Exception:
                        pass
                    state.remove_peer_connection(pc)
                    state.remove_session(sessionid)
            asyncio.ensure_future(_grace_close())

    player = HumanPlayer(state.avatar_streams[sessionid])
    audio_sender = pc.addTrack(player.audio)
    video_sender = pc.addTrack(player.video)
    
    capabilities = RTCRtpSender.getCapabilities("video")
    preferences = list(filter(lambda x: x.name == "H264", capabilities.codecs))
    preferences += list(filter(lambda x: x.name == "VP8", capabilities.codecs))
    preferences += list(filter(lambda x: x.name == "rtx", capabilities.codecs))
    transceiver = pc.getTransceivers()[1]
    transceiver.setCodecPreferences(preferences)

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # 诊断：朋友连不上时关键看这里
    sdp = pc.localDescription.sdp
    relay = sum(1 for l in sdp.split('\n') if ' typ relay ' in l)
    srflx = sum(1 for l in sdp.split('\n') if ' typ srflx ' in l)
    host  = sum(1 for l in sdp.split('\n') if ' typ host ' in l)
    logger.info('sessionid=%d ICE candidates: host=%d srflx=%d relay=%d (relay=0 远程客户端可能连不上)',
                sessionid, host, srflx, relay)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type, "sessionid": sessionid}
        ),
    )
