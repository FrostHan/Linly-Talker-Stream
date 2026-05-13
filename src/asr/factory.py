"""
ASR 工厂类

统一根据字符串类型创建不同的 ASR 引擎实例
"""

from typing import Type, Optional
from threading import Lock

from src.asr.base import BaseASR
from src.asr.engines import WhisperASR, FunASR


_ENGINE_MAP: dict[str, Type[BaseASR]] = {
    "whisper": WhisperASR,
    "funasr": FunASR,
}


def create_asr_engine(
    asr_type: str,
    config=None,
    model_size: str = "base",
    **kwargs
) -> BaseASR:
    engine_cls = _ENGINE_MAP.get(asr_type)
    if engine_cls is None:
        raise ValueError(
            f"未知的 ASR 类型: {asr_type!r}\n"
            f"支持的类型: {list(_ENGINE_MAP.keys())}"
        )
    
    # 根据不同引擎传递参数
    if asr_type == "whisper":
        return engine_cls(config=config, model_size=model_size)
    if asr_type == "funasr":
        return engine_cls(
            config=config,
            model_name=kwargs.get("model_name", "paraformer-zh"),
            device=kwargs.get("device", "auto"),
        )

    return engine_cls(config=config)

_asr_instance: Optional[BaseASR] = None
_asr_lock = Lock()


def get_asr_engine(
    asr_type: str = "whisper",
    model_size: str = "base",
    config=None,
    force_new: bool = False,
    **kwargs
) -> BaseASR:
    global _asr_instance
    
    # 单例复用，避免重复加载模型
    if _asr_instance is None or force_new:
        with _asr_lock:
            if _asr_instance is None or force_new:
                _asr_instance = create_asr_engine(
                    asr_type=asr_type,
                    config=config,
                    model_size=model_size,
                    **kwargs
                )
    
    return _asr_instance


def preload_asr_engine(
    asr_type: str = "whisper",
    model_size: str = "base",
    config=None,
    **kwargs
) -> BaseASR:
    """提前加载 ASR 模型，避免第一次语音请求承担冷启动。"""
    engine = get_asr_engine(
        asr_type=asr_type,
        model_size=model_size,
        config=config,
        **kwargs,
    )
    engine.ensure_initialized()
    return engine


def release_asr_engine():
    global _asr_instance
    if _asr_instance is not None:
        from src.utils.logging import logger
        logger.info('[ASR] release ASR engine resources')
        _asr_instance = None
