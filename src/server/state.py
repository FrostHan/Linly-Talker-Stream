"""全局状态管理"""
import time
from typing import Dict, Set, Optional
from src.avatars.base import BaseAvatar
from aiortc import RTCPeerConnection


class ServerState:
    """服务器全局状态管理类"""
    
    def __init__(self):
        # 会话管理
        self.avatar_streams: Dict[int, BaseAvatar] = {}  # sessionid -> BaseAvatar
        # 每个 session 的最近活跃时间（time.monotonic 秒）。后台 idle cleanup 用。
        self.last_active: Dict[int, float] = {}
        # session -> pc，便于 idle cleanup 时一并关闭 WebRTC 连接
        self.session_pcs: Dict[int, RTCPeerConnection] = {}
        
        # WebRTC 连接管理
        self.pcs: Set[RTCPeerConnection] = set()
        
        # 配置和模型
        self.config = None
        self.model = None
        self.avatar = None
        
        # 服务状态
        self.server_ready = False
    
    def add_session(self, sessionid: int, avatar_stream: BaseAvatar = None):
        """添加会话"""
        self.avatar_streams[sessionid] = avatar_stream
        self.last_active[sessionid] = time.monotonic()
    
    def remove_session(self, sessionid: int):
        """移除会话（同时清理 last_active / session_pcs 索引）"""
        self.avatar_streams.pop(sessionid, None)
        self.last_active.pop(sessionid, None)
        self.session_pcs.pop(sessionid, None)
    
    def get_session(self, sessionid: int) -> BaseAvatar:
        """获取会话"""
        return self.avatar_streams.get(sessionid)
    
    def touch_session(self, sessionid: int):
        """续命：每次该 session 有交互就调一下，重置 idle 计时"""
        if sessionid in self.avatar_streams:
            self.last_active[sessionid] = time.monotonic()
    
    def add_peer_connection(self, pc: RTCPeerConnection, sessionid: Optional[int] = None):
        """添加 WebRTC 连接（可选关联 sessionid 以便 idle 清理时一并关闭）"""
        self.pcs.add(pc)
        if sessionid is not None:
            self.session_pcs[sessionid] = pc
    
    def remove_peer_connection(self, pc: RTCPeerConnection):
        """移除 WebRTC 连接"""
        self.pcs.discard(pc)
        # 反向清掉 session_pcs 中指向此 pc 的条目
        for sid in [s for s, p in self.session_pcs.items() if p is pc]:
            self.session_pcs.pop(sid, None)
    
    def idle_sessions(self, timeout_sec: float):
        """返回闲置时间超过 timeout_sec 的 sessionid 列表"""
        now = time.monotonic()
        return [sid for sid, ts in self.last_active.items()
                if now - ts > timeout_sec]


# 全局状态实例
state = ServerState()
