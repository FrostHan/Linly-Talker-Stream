"""
ASR 引擎基类
所有 ASR 引擎的统一抽象接口
"""

from __future__ import annotations

import os
import tempfile
import soundfile as sf
from io import BytesIO
from typing import Dict, Any
from abc import ABC, abstractmethod

from src.utils.logging import logger


class BaseASR(ABC):
    """
    所有 ASR 引擎的基类
    
    统一接口：
    - transcribe: 识别音频字节数据
    - set_language: 设置识别语言
    - get_info: 获取引擎信息
    """
    
    def __init__(self, config=None):
        """
        初始化 ASR 引擎
        
        Args:
            config: 配置对象（可选）
        """
        self.config = config
        self.language = "zh"  # 默认中文
        self._initialized = False
        
        logger.info(f'[ASR] 初始化 {self.__class__.__name__}')
    
    @abstractmethod
    def _load_model(self):
        """加载 ASR 模型（子类实现）"""
        pass
    
    @abstractmethod
    def _transcribe(self, audio_path: str) -> Dict[str, Any]:
        """
        识别音频文件（子类实现）
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            Dict 包含:
                - text: 识别的文本
                - language: 检测到的语言（可选）
                - confidence: 置信度（可选）
        """
        pass
    
    def transcribe(self, audio_bytes: bytes) -> Dict[str, Any]:
        """
        识别音频字节数据（统一入口）
        
        Args:
            audio_bytes: 音频文件的字节数据
            
        Returns:
            Dict 包含识别结果
        """
        # 延迟加载模型，避免启动时耗时/占用显存
        if not self._initialized:
            self._load_model()
            self._initialized = True
        
        # 统一转成临时文件，方便不同引擎复用文件接口
        temp_audio_path = None
        try:
            temp_audio_path = self._save_temp_audio(audio_bytes)
            result = self._transcribe(temp_audio_path)
            
            logger.info(f'[ASR] 识别结果: {result.get("text", "")}')
            return result
            
        finally:
            # 清理临时文件
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.unlink(temp_audio_path)
                except Exception as e:
                    logger.warning(f'[ASR] 清理临时文件失败: {e}')
    
    def _save_temp_audio(self, audio_bytes: bytes) -> str:
        """
        保存临时音频文件并转换为 wav 格式
        
        Args:
            audio_bytes: 音频字节数据
            
        Returns:
            临时文件路径
        """
        try:
            # 优先尝试 soundfile（支持 wav/flac/ogg）
            audio_stream = BytesIO(audio_bytes)
            data, samplerate = sf.read(audio_stream)
            
            # 创建临时 wav 文件
            temp_fd, temp_path = tempfile.mkstemp(suffix='.wav')
            os.close(temp_fd)
            
            sf.write(temp_path, data, samplerate)
            logger.debug(f'[ASR] 音频已保存: {temp_path}, 采样率: {samplerate}Hz')
            return temp_path
            
        except Exception as e:
            logger.debug(f'[ASR] soundfile 无法解码（{e}），尝试 ffmpeg 转码')
            
            # 退路 1：调用 ffmpeg 转 16kHz 单声道 wav，可处理 webm/m4a/mp4/ogg/opus 等
            # FunASR / kaldiio 都需要标准 wav，所以这里必须真正转码而不是只改扩展名
            try:
                import subprocess
                
                # 先把原始字节落到带原扩展名的文件，让 ffmpeg 走容器探测
                src_fd, src_path = tempfile.mkstemp(suffix='.bin')
                os.close(src_fd)
                with open(src_path, 'wb') as f:
                    f.write(audio_bytes)
                
                dst_fd, dst_path = tempfile.mkstemp(suffix='.wav')
                os.close(dst_fd)
                
                cmd = [
                    'ffmpeg', '-y', '-loglevel', 'error',
                    '-i', src_path,
                    '-ac', '1',          # 单声道
                    '-ar', '16000',      # 16kHz（whisper / paraformer 通用）
                    '-f', 'wav',
                    dst_path,
                ]
                proc = subprocess.run(cmd, capture_output=True, timeout=30)
                
                # 清理源文件
                try:
                    os.unlink(src_path)
                except Exception:
                    pass
                
                if proc.returncode == 0 and os.path.getsize(dst_path) > 44:  # > wav header
                    logger.debug(f'[ASR] ffmpeg 转码成功: {dst_path}')
                    return dst_path
                
                logger.warning(f'[ASR] ffmpeg 转码失败 rc={proc.returncode}: {proc.stderr.decode("utf-8", errors="ignore")[:200]}')
                try:
                    os.unlink(dst_path)
                except Exception:
                    pass
            except FileNotFoundError:
                logger.warning('[ASR] ffmpeg 未安装，跳过转码')
            except Exception as e2:
                logger.warning(f'[ASR] ffmpeg 调用异常: {e2}')
            
            # 退路 2：直接保存原始字节（whisper 内部能 ffmpeg 解码，funasr 多半不行）
            logger.warning(f'[ASR] 音频格式转换失败，保存原始格式: {e}')
            temp_fd, temp_path = tempfile.mkstemp(suffix='.webm')
            os.close(temp_fd)
            
            with open(temp_path, 'wb') as f:
                f.write(audio_bytes)
            
            return temp_path
    
    def transcribe_text(self, audio_bytes: bytes) -> str:
        """
        简化接口：只返回识别的文本
        
        Args:
            audio_bytes: 音频文件的字节数据
            
        Returns:
            识别的文本字符串
        """
        result = self.transcribe(audio_bytes)
        return result.get("text", "")
    
    def set_language(self, language: str):
        """
        设置识别语言
        
        Args:
            language: 语言代码（如 'zh', 'en', 'auto'）
        """
        self.language = language
        logger.info(f'[ASR] 语言设置为: {language}')
    
    def get_info(self) -> Dict[str, Any]:
        """
        获取 ASR 引擎信息
        
        Returns:
            Dict 包含引擎信息
        """
        return {
            "engine": self.__class__.__name__,
            "language": self.language,
            "initialized": self._initialized
        }


__all__ = ["BaseASR"]
