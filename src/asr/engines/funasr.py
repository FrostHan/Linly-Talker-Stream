"""
FunASR 引擎实现
阿里达摩院的 FunASR，专注中文识别
"""

import re
import time
from typing import Dict, Any

from src.utils.logging import logger
from src.asr.base import BaseASR


# 去掉中文字符之间的空格（paraformer-zh 默认按 token 加空格输出）
# 规则：相邻两个 CJK 字符之间的空格全删；CJK 与 ASCII 之间保留 1 个空格
_CJK = r'\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff'
_RE_CJK_SPACE_CJK = re.compile(rf'(?<=[{_CJK}])\s+(?=[{_CJK}])')
_RE_MULTI_SPACE = re.compile(r'\s{2,}')


def _normalize_zh_text(text: str) -> str:
    """规范化 paraformer 输出：去掉中文之间多余的空格。"""
    if not text:
        return text
    # 多次替换以处理多空格情况（如 "你 好 啊"）
    prev = None
    cur = text
    while prev != cur:
        prev = cur
        cur = _RE_CJK_SPACE_CJK.sub('', cur)
    cur = _RE_MULTI_SPACE.sub(' ', cur)
    return cur.strip()


class FunASR(BaseASR):
    """
    FunASR 引擎（阿里达摩院）
    
    专注中文语音识别，速度快，准确度高
    """
    
    def __init__(self, config=None, model_name: str = "paraformer-zh", device: str = "auto", **kwargs):
        """
        初始化 FunASR
        
        Args:
            config: 配置对象
            model_name: 模型名称（默认 paraformer-zh）
            device: 兼容配置中的 ASR device 字段；FunASR AutoModel 这里不强制透传
        """
        super().__init__(config)
        
        self.model_name = model_name
        self.device = device
        self.model = None
        
        if kwargs:
            logger.info(f'[FunASR] 忽略未使用参数: {list(kwargs.keys())}')
        logger.info(f'[FunASR] 模型: {model_name}, 设备配置: {device}')

    def _resolve_device(self) -> str:
        if self.device and self.device != "auto":
            return "cuda:0" if self.device == "cuda" else self.device
        try:
            import torch
            return "cuda:0" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"
    
    def _load_model(self):
        """加载 FunASR 模型"""
        try:
            from funasr import AutoModel
            resolved_device = self._resolve_device()
            logger.info(f'[FunASR] 正在加载模型: {self.model_name}, device={resolved_device}')
            start_time = time.perf_counter()
            load_kwargs = {
                "model": self.model_name,
                "device": resolved_device,
                "disable_update": True,
            }
            try:
                self.model = AutoModel(**load_kwargs)
            except TypeError as e:
                logger.warning(f'[FunASR] 当前版本不支持部分加载参数，降级重试: {e}')
                load_kwargs.pop("disable_update", None)
                try:
                    self.model = AutoModel(**load_kwargs)
                except TypeError:
                    load_kwargs.pop("device", None)
                    self.model = AutoModel(**load_kwargs)
            logger.info(f'[FunASR] 模型加载成功，耗时 {time.perf_counter() - start_time:.3f}s')
            
        except ImportError:
            raise ImportError(
                "请安装 FunASR:\n"
                "  pip install funasr"
            )
        except Exception as e:
            logger.error(f'[FunASR] 模型加载失败: {e}')
            raise
    
    def _transcribe(self, audio_path: str) -> Dict[str, Any]:
        """
        使用 FunASR 识别音频
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            识别结果字典
        """
        start_time = time.perf_counter()
        result = self.model.generate(input=audio_path)
        logger.info(f'[FunASR] generate 耗时: {time.perf_counter() - start_time:.3f}s')
        
        if result and len(result) > 0:
            text = result[0].get("text", "")
            return {
                "text": _normalize_zh_text(text),
                "language": "zh"
            }
        
        return {
            "text": "",
            "language": "zh"
        }
    
    def get_info(self) -> Dict[str, Any]:
        """获取引擎信息"""
        info = super().get_info()
        info.update({
            "model_name": self.model_name
        })
        return info
