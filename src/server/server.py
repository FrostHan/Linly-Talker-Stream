# Linly-Talker-Stream (https://github.com/Kedreamix/Linly-Talker-Stream). Copyright [Linly-talker-stream@kedreamix]. Apache-2.0.
# Based on LiveTalking (C) 2024 LiveTalking@lipku https://github.com/lipku/LiveTalking (Apache-2.0).

"""服务器启动和配置"""
import asyncio
import os
from aiohttp import web
import aiohttp_cors

from src.utils.logging import logger
from src.server.state import state
from src.server import routes


# 需要鉴权的路由前缀：进入直播间 + 所有会耗 LLM/TTS 资源的接口
# 不在列表里的（/health /ice /auth_required /download /静态资源）不要求密码
_PROTECTED_PATHS = (
    '/offer',           # 建立 WebRTC 会话
    '/human',           # LLM 对话
    '/humanaudio',      # 上传音频说话
    '/asr',             # 服务器端 ASR
    '/set_audiotype',
    '/record',
    '/interrupt_talk',
    '/is_speaking',
    '/clear_history',
    '/download',        # 录像下载也要密码（防止枚举 timestamp 拖走他人录像）
)


@web.middleware
async def password_middleware(request, handler):
    """环境变量 ROOM_PASSWORD 设了就启用，未设则不拦截（局域网开发友好）"""
    expected = os.environ.get('ROOM_PASSWORD', '').strip()
    if not expected:
        return await handler(request)

    # CORS 预检请求 (OPTIONS) 不能带自定义 header，必须放行让 aiohttp_cors 处理
    if request.method == 'OPTIONS':
        return await handler(request)

    if not any(request.path == p or request.path.startswith(p + '/') for p in _PROTECTED_PATHS):
        return await handler(request)

    # 优先用 header；body 中的 password 字段作为备选（不读 body 以免耗掉流）
    provided = request.headers.get('X-Room-Password', '').strip()
    if provided != expected:
        logger.warning('鉴权失败 path=%s remote=%s', request.path, request.remote)
        return web.json_response({'error': 'unauthorized'}, status=401)

    return await handler(request)


async def auth_required(request):
    """前端 查询本服务器是否需要密码"""
    return web.json_response({
        'required': bool(os.environ.get('ROOM_PASSWORD', '').strip())
    })


# 闲置会话清理参数（环境变量可调）
# - SESSION_IDLE_TIMEOUT_SEC: 单个 session 多久无交互就回收，默认 300 (5 分钟)
# - SESSION_CLEANUP_INTERVAL_SEC: 后台扫描周期，默认 30
def _idle_timeout() -> float:
    try:
        return float(os.environ.get('SESSION_IDLE_TIMEOUT_SEC', '300'))
    except ValueError:
        return 300.0


def _cleanup_interval() -> float:
    try:
        return float(os.environ.get('SESSION_CLEANUP_INTERVAL_SEC', '30'))
    except ValueError:
        return 30.0


async def _close_session(sessionid: int, reason: str = 'idle'):
    """主动关闭 session 对应的 pc + 清掉 state 中的引用。"""
    pc = state.session_pcs.get(sessionid)
    if pc is not None:
        try:
            await pc.close()
        except Exception as e:
            logger.warning('关闭 sessionid=%s pc 失败: %s', sessionid, e)
        state.remove_peer_connection(pc)
    state.remove_session(sessionid)
    logger.info('已回收 sessionid=%s (reason=%s)', sessionid, reason)


async def idle_cleanup_task(app):
    """周期性扫描 idle session 并清理。绑定到 app 生命周期。"""
    timeout = _idle_timeout()
    interval = _cleanup_interval()
    logger.info('🧹 idle cleanup 任务启动: timeout=%.0fs interval=%.0fs', timeout, interval)
    try:
        while True:
            await asyncio.sleep(interval)
            try:
                idle = state.idle_sessions(timeout)
                for sid in idle:
                    logger.warning('sessionid=%s 闲置超过 %.0fs，主动回收', sid, timeout)
                    await _close_session(sid, reason='idle')
            except Exception:
                logger.exception('idle cleanup 扫描异常')
    except asyncio.CancelledError:
        logger.info('🧹 idle cleanup 任务已取消')
        raise


def _asr_preload_enabled() -> bool:
    return os.environ.get('ASR_PRELOAD', '1').strip().lower() not in ('0', 'false', 'no')


def _preload_asr_sync():
    """后台预热 ASR，避免第一次 /asr 请求承担模型冷启动。"""
    if not _asr_preload_enabled():
        logger.info('[ASR] 后台预热已关闭 (ASR_PRELOAD=0)')
        return
    if state.config is None or not getattr(state.config, 'asr', None):
        return

    asr_config = state.config.asr
    try:
        from src.asr.factory import preload_asr_engine
        logger.info('[ASR] 后台预热开始: type=%s device=%s', asr_config.type, asr_config.device)
        preload_asr_engine(
            asr_type=asr_config.type,
            model_size=asr_config.model_size,
            config=asr_config,
            device=asr_config.device,
        )
        logger.info('[ASR] 后台预热完成')
    except Exception:
        logger.exception('[ASR] 后台预热失败')


async def asr_preload_task(app):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _preload_asr_sync)


async def on_startup(app):
    """启动后台 idle cleanup 任务"""
    app['idle_cleanup_task'] = asyncio.create_task(idle_cleanup_task(app))
    app['asr_preload_task'] = asyncio.create_task(asr_preload_task(app))


async def on_shutdown(app):
    """服务器关闭时的清理操作"""
    task = app.get('idle_cleanup_task')
    if task is not None:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    asr_task = app.get('asr_preload_task')
    if asr_task is not None and not asr_task.done():
        asr_task.cancel()
        try:
            await asr_task
        except (asyncio.CancelledError, Exception):
            pass
    coros = [pc.close() for pc in state.pcs]
    await asyncio.gather(*coros, return_exceptions=True)
    state.pcs.clear()


def create_app():
    """创建并配置 aiohttp 应用"""
    # 单独设置较大的请求体上限，方便上传音视频
    app = web.Application(
        client_max_size=1024**2*100,
        middlewares=[password_middleware],
    )
    app.on_shutdown.append(on_shutdown)
    app.on_startup.append(on_startup)
    
    # 路由集中注册，避免分散难维护
    app.router.add_post("/offer", routes.offer)
    app.router.add_post("/human", routes.human)
    app.router.add_post("/humanaudio", routes.humanaudio)
    app.router.add_post("/asr", routes.asr)
    app.router.add_post("/asr/", routes.asr)
    app.router.add_post("/set_audiotype", routes.set_audiotype)
    app.router.add_post("/record", routes.record)
    app.router.add_post("/interrupt_talk", routes.interrupt_talk)
    app.router.add_post("/is_speaking", routes.is_speaking)
    app.router.add_post("/clear_history", routes.clear_history)
    app.router.add_get("/health", routes.health_check)
    app.router.add_get("/ice", routes.get_ice_config)
    app.router.add_get("/auth_required", auth_required)
    app.router.add_get("/download/{filename}", routes.download_record)
    # 前端静态资源托管
    app.router.add_static('/', path='web')
    
    # CORS：默认只放行公网域名 + 本地开发地址；可用 ALLOWED_ORIGINS 环境变量覆盖（逗号分隔）
    default_origins = [
        'https://talker.frostnova.uk',
        'https://localhost:3000',
        'https://127.0.0.1:3000',
    ]
    extra = os.environ.get('ALLOWED_ORIGINS', '').strip()
    origins = [o.strip() for o in extra.split(',') if o.strip()] if extra else default_origins
    cors_defaults = {
        origin: aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
        for origin in origins
    }
    cors = aiohttp_cors.setup(app, defaults=cors_defaults)
    
    for route in list(app.router.routes()):
        cors.add(route)
    
    return app


def run_server(app, config):
    """运行服务器"""
    # 兼容新旧配置字段
    use_ssl = getattr(config.app, 'ssl', False)
    if not use_ssl:
        use_ssl = hasattr(config.app, 'ssl_cert') and config.app.ssl_cert and \
                  hasattr(config.app, 'ssl_key') and config.app.ssl_key
    
    protocol = 'https' if use_ssl else 'http'
    listen_host = getattr(config.app, 'listenhost', '0.0.0.0')
    listen_port = config.app.listenport
    
    # 启动信息集中打印，便于排查配置问题
    logger.info('┌─────────────────────────────────────────────┐')
    logger.info('│  🚀 Linly-Talker-Stream 后端服务启动中...   │')
    logger.info('├─────────────────────────────────────────────┤')
    logger.info(f'│  协议: {protocol.upper():<37} │')
    logger.info(f'│  监听地址: {listen_host:<30} │')
    logger.info(f'│  监听端口: {listen_port:<30} │')
    
    if protocol == 'http':
        logger.info('│                                             │')
        logger.info('│  ⚠️  HTTP 模式：浏览器录音仅支持 localhost  │')
        logger.info('│  💡 远程访问需要在配置中启用 ssl: true     │')
    else:
        logger.info(f'│  证书文件: {config.app.ssl_cert:<28} │')
    
    logger.info('└─────────────────────────────────────────────┘')
    
    config.app.protocol = protocol
    
    # 标记可用，供健康检查使用
    state.server_ready = True
    logger.info('✅ 服务已就绪，可以接受连接')
    
    def _run():
        # 独立事件循环，避免与外部线程冲突
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runner = web.AppRunner(app)
        loop.run_until_complete(runner.setup())
        
        if use_ssl:
            import ssl
            # 仅做服务端 TLS，不做客户端校验
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(config.app.ssl_cert, config.app.ssl_key)
            site = web.TCPSite(runner, listen_host, listen_port, ssl_context=ssl_context)
            logger.info(f'✅ HTTPS 服务已启动: https://{listen_host}:{listen_port}')
        else:
            site = web.TCPSite(runner, listen_host, listen_port)
            logger.info(f'✅ HTTP 服务已启动: http://{listen_host}:{listen_port}')
        
        loop.run_until_complete(site.start())
        loop.run_forever()
    
    _run()
