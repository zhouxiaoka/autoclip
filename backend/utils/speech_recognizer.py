"""
语音识别工具 - 支持多种语音识别服务
支持本地Whisper、OpenAI API、Azure Speech Services等多种语音识别服务
"""
import logging
import subprocess
import json
import os
import asyncio
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from enum import Enum
import requests
from dataclasses import dataclass
from .ffmpeg_utils import get_ffmpeg_path

logger = logging.getLogger(__name__)


class SpeechRecognitionMethod(str, Enum):
    """语音识别方法枚举"""
    WHISPER_LOCAL = "whisper_local"
    OPENAI_API = "openai_api"
    AZURE_SPEECH = "azure_speech"
    GOOGLE_SPEECH = "google_speech"
    ALIYUN_SPEECH = "aliyun_speech"
    # 预留其他服务扩展
    CUSTOM_API = "custom_api"


class LanguageCode(str, Enum):
    """支持的语言代码"""
    # 中文
    CHINESE_SIMPLIFIED = "zh"
    CHINESE_TRADITIONAL = "zh-TW"
    # 英文
    ENGLISH = "en"
    ENGLISH_US = "en-US"
    ENGLISH_UK = "en-GB"
    # 日文
    JAPANESE = "ja"
    # 韩文
    KOREAN = "ko"
    # 法文
    FRENCH = "fr"
    # 德文
    GERMAN = "de"
    # 西班牙文
    SPANISH = "es"
    # 俄文
    RUSSIAN = "ru"
    # 阿拉伯文
    ARABIC = "ar"
    # 葡萄牙文
    PORTUGUESE = "pt"
    # 意大利文
    ITALIAN = "it"
    # 自动检测
    AUTO = "auto"


@dataclass
class SpeechRecognitionConfig:
    """语音识别配置"""
    method: SpeechRecognitionMethod = SpeechRecognitionMethod.WHISPER_LOCAL
    language: LanguageCode = LanguageCode.AUTO
    model: str = "base"  # Whisper模型大小
    timeout: int = 0  # 超时时间（秒），0表示无限制
    output_format: str = "srt"  # 输出格式
    enable_timestamps: bool = True  # 是否启用时间戳
    enable_punctuation: bool = True  # 是否启用标点符号
    enable_speaker_diarization: bool = False  # 是否启用说话人分离
    enable_fallback: bool = True  # 是否启用回退机制
    fallback_method: SpeechRecognitionMethod = SpeechRecognitionMethod.WHISPER_LOCAL  # 回退方法
    
    # API配置
    openai_api_key: Optional[str] = None
    azure_speech_key: Optional[str] = None
    azure_speech_region: Optional[str] = None
    google_credentials_path: Optional[str] = None
    aliyun_access_key: Optional[str] = None
    aliyun_access_secret: Optional[str] = None
    custom_api_url: Optional[str] = None
    custom_api_key: Optional[str] = None
    
    def __post_init__(self):
        """验证配置参数"""
        # 验证方法
        if not isinstance(self.method, SpeechRecognitionMethod):
            try:
                self.method = SpeechRecognitionMethod(self.method)
            except ValueError:
                raise ValueError(f"不支持的语音识别方法: {self.method}")
        
        # 验证语言
        if not isinstance(self.language, LanguageCode):
            try:
                self.language = LanguageCode(self.language)
            except ValueError:
                raise ValueError(f"不支持的语言代码: {self.language}")
        
        # 验证模型
        valid_models = ["tiny", "base", "small", "medium", "large"]
        if self.model not in valid_models:
            raise ValueError(f"不支持的Whisper模型: {self.model}")
        
        # 验证超时时间
        if self.timeout < 0:
            raise ValueError("超时时间不能为负数")
        
        # 验证输出格式
        valid_formats = ["srt", "vtt", "txt", "json"]
        if self.output_format not in valid_formats:
            raise ValueError(f"不支持的输出格式: {self.output_format}")


class SpeechRecognitionError(Exception):
    """语音识别错误"""
    pass


class SpeechRecognizer:
    """语音识别器，支持多种语音识别服务"""
    
    def __init__(self, config: Optional[SpeechRecognitionConfig] = None):
        self.config = config or SpeechRecognitionConfig()
        self.available_methods = self._check_available_methods()
    
    def _check_available_methods(self) -> Dict[SpeechRecognitionMethod, bool]:
        """检查可用的语音识别方法"""
        methods = {}
        
        # 检查本地Whisper
        methods[SpeechRecognitionMethod.WHISPER_LOCAL] = self._check_whisper_availability()
        
        # 检查OpenAI API
        methods[SpeechRecognitionMethod.OPENAI_API] = self._check_openai_availability()
        
        # 检查Azure Speech Services
        methods[SpeechRecognitionMethod.AZURE_SPEECH] = self._check_azure_speech_availability()
        
        # 检查Google Speech-to-Text
        methods[SpeechRecognitionMethod.GOOGLE_SPEECH] = self._check_google_speech_availability()
        
        # 检查阿里云语音识别
        methods[SpeechRecognitionMethod.ALIYUN_SPEECH] = self._check_aliyun_speech_availability()
        
        # 检查自定义API
        methods[SpeechRecognitionMethod.CUSTOM_API] = self._check_custom_api_availability()
        
        return methods
    
    def _check_whisper_availability(self) -> bool:
        """检查本地Whisper是否可用"""
        try:
            result = subprocess.run(['whisper', '--help'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("本地Whisper未安装或不可用")
            return False
    
    def _check_openai_availability(self) -> bool:
        """检查OpenAI API是否可用"""
        api_key = os.getenv("OPENAI_API_KEY")
        return api_key is not None and len(api_key.strip()) > 0
    
    def _check_azure_speech_availability(self) -> bool:
        """检查Azure Speech Services是否可用"""
        api_key = os.getenv("AZURE_SPEECH_KEY")
        region = os.getenv("AZURE_SPEECH_REGION")
        return api_key is not None and region is not None
    
    def _check_google_speech_availability(self) -> bool:
        """检查Google Speech-to-Text是否可用"""
        # 检查Google Cloud凭证文件
        cred_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_file and Path(cred_file).exists():
            return True
        
        # 检查API密钥
        api_key = os.getenv("GOOGLE_SPEECH_API_KEY")
        return api_key is not None
    
    def _check_aliyun_speech_availability(self) -> bool:
        """检查阿里云语音识别是否可用"""
        try:
            # 检查配置中的API Key
            # 这里可以检查环境变量或者配置对象中的API Key
            access_key = os.getenv("ALIYUN_API_KEY") or (self.config.aliyun_access_key if hasattr(self, 'config') else None)
            return bool(access_key)
        except Exception:
            return False
    
    def _extract_audio_from_video(self, video_path: Path, output_dir: Path) -> Path:
        """
        从视频文件中提取音频
        
        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            
        Returns:
            提取的音频文件路径
        """
        try:
            # 检查ffmpeg是否可用
            ffmpeg_bin = get_ffmpeg_path()
            result = subprocess.run([ffmpeg_bin, '-version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise SpeechRecognitionError("ffmpeg不可用，请安装ffmpeg")
            
            # 生成音频文件路径
            audio_filename = f"{video_path.stem}_audio.wav"
            audio_path = output_dir / audio_filename
            
            # 如果音频文件已存在，直接返回
            if audio_path.exists():
                logger.info(f"音频文件已存在: {audio_path}")
                return audio_path
            
            logger.info(f"正在从视频提取音频: {video_path} -> {audio_path}")
            
            # 使用ffmpeg提取音频
            cmd = [
                ffmpeg_bin,
                '-i', str(video_path),
                '-vn',  # 不处理视频流
                '-acodec', 'pcm_s16le',  # 使用PCM 16位编码
                '-ar', '16000',  # 采样率16kHz
                '-ac', '1',  # 单声道
                '-y',  # 覆盖输出文件
                str(audio_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                raise SpeechRecognitionError(f"音频提取失败: {result.stderr}")
            
            if not audio_path.exists():
                raise SpeechRecognitionError("音频提取失败，输出文件不存在")
            
            logger.info(f"音频提取成功: {audio_path}")
            return audio_path
            
        except subprocess.TimeoutExpired:
            raise SpeechRecognitionError("音频提取超时")
        except Exception as e:
            raise SpeechRecognitionError(f"音频提取失败: {e}")
    
    def generate_subtitle(self, video_path: Path, output_path: Optional[Path] = None, 
                         config: Optional[SpeechRecognitionConfig] = None) -> Path:
        """
        生成字幕文件
        
        Args:
            video_path: 视频文件路径
            output_path: 输出字幕文件路径
            config: 语音识别配置
            
        Returns:
            生成的字幕文件路径
            
        Raises:
            SpeechRecognitionError: 语音识别失败
        """
        if not video_path.exists():
            raise SpeechRecognitionError(f"视频文件不存在: {video_path}")
        
        # 使用传入的配置或默认配置
        config = config or self.config
        
        # 确定输出路径
        if output_path is None:
            output_path = video_path.parent / f"{video_path.stem}.{config.output_format}"
        
        # 根据配置的方法选择识别服务，支持回退机制
        try:
            if config.method == SpeechRecognitionMethod.WHISPER_LOCAL:
                return self._generate_subtitle_whisper_local(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.OPENAI_API:
                return self._generate_subtitle_openai_api(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.AZURE_SPEECH:
                return self._generate_subtitle_azure_speech(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.GOOGLE_SPEECH:
                return self._generate_subtitle_google_speech(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.ALIYUN_SPEECH:
                return self._generate_subtitle_aliyun_speech(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.CUSTOM_API:
                return self._generate_subtitle_custom_api(video_path, output_path, config)
            else:
                raise SpeechRecognitionError(f"不支持的语音识别方法: {config.method}")
        except SpeechRecognitionError as e:
            # 如果启用了回退机制且当前方法不是回退方法，则尝试回退
            if (config.enable_fallback and 
                config.method != config.fallback_method and 
                self.available_methods.get(config.fallback_method, False)):
                
                logger.warning(f"主方法 {config.method} 失败: {e}")
                logger.info(f"尝试回退到 {config.fallback_method}")
                
                # 创建回退配置
                fallback_config = SpeechRecognitionConfig(
                    method=config.fallback_method,
                    language=config.language,
                    model=config.model,
                    timeout=config.timeout,
                    output_format=config.output_format,
                    enable_timestamps=config.enable_timestamps,
                    enable_punctuation=config.enable_punctuation,
                    enable_speaker_diarization=config.enable_speaker_diarization,
                    enable_fallback=False  # 避免无限回退
                )
                
                return self.generate_subtitle(video_path, output_path, fallback_config)
            else:
                raise
    
    def _check_custom_api_availability(self) -> bool:
        """检查自定义API是否可用"""
        # 检查是否有配置自定义API
        if self.config.custom_api_url and self.config.custom_api_key:
            try:
                # 简单的健康检查
                response = requests.get(f"{self.config.custom_api_url}/health", timeout=5)
                return response.status_code == 200
            except Exception:
                return False
        return False
    
    def _generate_subtitle_whisper_local(self, video_path: Path, output_path: Path, 
                                       config: SpeechRecognitionConfig) -> Path:
        """使用本地Whisper生成字幕"""
        if not self.available_methods[SpeechRecognitionMethod.WHISPER_LOCAL]:
            raise SpeechRecognitionError(
                "本地Whisper不可用，请安装whisper: pip install openai-whisper\n"
                "同时确保已安装ffmpeg:\n"
                "  macOS: brew install ffmpeg\n"
                "  Ubuntu: sudo apt install ffmpeg\n"
                "  Windows: 下载ffmpeg并添加到PATH"
            )
        
        try:
            logger.info(f"开始使用本地Whisper生成字幕: {video_path}")
            
            # 检查视频文件是否存在
            if not video_path.exists():
                raise SpeechRecognitionError(f"视频文件不存在: {video_path}")
            
            # 检查视频文件大小
            file_size = video_path.stat().st_size
            if file_size == 0:
                raise SpeechRecognitionError(f"视频文件为空: {video_path}")
            
            # 检查输出文件是否已存在，避免重复处理
            if output_path.exists():
                logger.info(f"字幕文件已存在，跳过Whisper处理: {output_path}")
                return output_path
            
            # 构建whisper命令
            cmd = [
                'whisper',
                str(video_path),
                '--output_dir', str(output_path.parent),
                '--output_format', config.output_format,
                '--model', config.model
            ]
            
            # 添加语言参数
            if config.language != LanguageCode.AUTO:
                cmd.extend(['--language', config.language])
            
            # 添加超时处理
            logger.info(f"执行Whisper命令: {' '.join(cmd)}")
            
            # 使用进程锁文件防止重复处理
            lock_file = output_path.parent / f".{video_path.stem}.whisper.lock"
            try:
                # 创建锁文件
                with open(lock_file, 'w') as f:
                    f.write(str(os.getpid()))
                
                # 根据超时配置决定是否设置超时
                if config.timeout > 0:
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True, 
                        timeout=config.timeout,
                        cwd=str(video_path.parent)  # 设置工作目录
                    )
                else:
                    # 无超时限制
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True, 
                        cwd=str(video_path.parent)  # 设置工作目录
                    )
            finally:
                # 清理锁文件
                if lock_file.exists():
                    lock_file.unlink()
            
            if result.returncode == 0:
                # 检查输出文件是否存在
                if output_path.exists():
                    logger.info(f"本地Whisper字幕生成成功: {output_path}")
                    return output_path
                else:
                    # 尝试查找其他可能的输出文件
                    possible_outputs = list(output_path.parent.glob(f"{video_path.stem}*.{config.output_format}"))
                    if possible_outputs:
                        actual_output = possible_outputs[0]
                        logger.info(f"找到Whisper输出文件: {actual_output}")
                        return actual_output
                    else:
                        raise SpeechRecognitionError(f"Whisper执行成功但未找到输出文件: {output_path}")
            else:
                error_msg = f"本地Whisper执行失败 (返回码: {result.returncode}):\n"
                if result.stderr:
                    error_msg += f"错误信息: {result.stderr}\n"
                if result.stdout:
                    error_msg += f"输出信息: {result.stdout}"
                
                # 提供具体的错误解决建议
                if "command not found" in result.stderr:
                    error_msg += "\n\n解决方案: 请安装whisper: pip install openai-whisper"
                elif "ffmpeg" in result.stderr.lower():
                    error_msg += "\n\n解决方案: 请安装ffmpeg:\n  macOS: brew install ffmpeg\n  Ubuntu: sudo apt install ffmpeg"
                elif "timeout" in result.stderr.lower():
                    error_msg += f"\n\n解决方案: 视频处理超时，请尝试使用更小的模型 (--model tiny) 或增加超时时间"
                
                logger.error(error_msg)
                raise SpeechRecognitionError(error_msg)
                
        except subprocess.TimeoutExpired:
            error_msg = f"本地Whisper执行超时（{config.timeout}秒）\n"
            error_msg += "解决方案:\n"
            error_msg += "1. 使用更小的模型: --model tiny\n"
            error_msg += "2. 增加超时时间\n"
            error_msg += "3. 检查视频文件是否损坏"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
        except FileNotFoundError:
            error_msg = "找不到whisper命令\n"
            error_msg += "解决方案:\n"
            error_msg += "1. 安装whisper: pip install openai-whisper\n"
            error_msg += "2. 确保whisper在PATH中: which whisper\n"
            error_msg += "3. 重新安装: pip uninstall openai-whisper && pip install openai-whisper"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
        except Exception as e:
            error_msg = f"本地Whisper生成字幕时发生错误: {e}\n"
            error_msg += "请检查:\n"
            error_msg += "1. 视频文件格式是否支持\n"
            error_msg += "2. 系统是否有足够的内存\n"
            error_msg += "3. 是否有足够的磁盘空间"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def _generate_subtitle_openai_api(self, video_path: Path, output_path: Path, 
                                    config: SpeechRecognitionConfig) -> Path:
        """使用OpenAI API生成字幕"""
        if not self.available_methods[SpeechRecognitionMethod.OPENAI_API]:
            raise SpeechRecognitionError("OpenAI API不可用，请设置OPENAI_API_KEY环境变量")
        
        try:
            logger.info(f"开始使用OpenAI API生成字幕: {video_path}")
            
            # 这里需要实现OpenAI API调用
            # 由于需要额外的依赖，这里先抛出异常
            raise SpeechRecognitionError("OpenAI API功能暂未实现，请使用本地Whisper")
            
        except Exception as e:
            error_msg = f"OpenAI API生成字幕时发生错误: {e}"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def _generate_subtitle_azure_speech(self, video_path: Path, output_path: Path, 
                                      config: SpeechRecognitionConfig) -> Path:
        """使用Azure Speech Services生成字幕"""
        if not self.available_methods[SpeechRecognitionMethod.AZURE_SPEECH]:
            raise SpeechRecognitionError("Azure Speech Services不可用，请设置AZURE_SPEECH_KEY和AZURE_SPEECH_REGION环境变量")
        
        try:
            logger.info(f"开始使用Azure Speech Services生成字幕: {video_path}")
            
            # 这里需要实现Azure Speech Services调用
            raise SpeechRecognitionError("Azure Speech Services功能暂未实现，请使用本地Whisper")
            
        except Exception as e:
            error_msg = f"Azure Speech Services生成字幕时发生错误: {e}"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def _generate_subtitle_google_speech(self, video_path: Path, output_path: Path, 
                                       config: SpeechRecognitionConfig) -> Path:
        """使用Google Speech-to-Text生成字幕"""
        if not self.available_methods[SpeechRecognitionMethod.GOOGLE_SPEECH]:
            raise SpeechRecognitionError("Google Speech-to-Text不可用，请设置GOOGLE_APPLICATION_CREDENTIALS或GOOGLE_SPEECH_API_KEY环境变量")
        
        try:
            logger.info(f"开始使用Google Speech-to-Text生成字幕: {video_path}")
            
            # 这里需要实现Google Speech-to-Text调用
            raise SpeechRecognitionError("Google Speech-to-Text功能暂未实现，请使用本地Whisper")
            
        except Exception as e:
            error_msg = f"Google Speech-to-Text生成字幕时发生错误: {e}"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def _generate_subtitle_aliyun_speech(self, video_path: Path, output_path: Path, 
                                       config: SpeechRecognitionConfig) -> Path:
        """使用阿里云语音识别生成字幕"""
        if not self.available_methods[SpeechRecognitionMethod.ALIYUN_SPEECH]:
            raise SpeechRecognitionError("阿里云语音识别不可用，请配置API Key")
        
        try:
            logger.info(f"开始使用阿里云语音识别生成字幕: {video_path}")
            
            # 检查视频文件是否存在
            if not video_path.exists():
                raise SpeechRecognitionError(f"视频文件不存在: {video_path}")
            
            # 提取音频文件
            audio_path = self._extract_audio_from_video(video_path, output_path.parent)
            
            # 使用阿里云语音识别API
            # 注意：这里使用阿里云百炼的语音识别服务，默认使用qwen3-asr-flash模型
            import requests
            import base64
            
            # 读取音频文件并编码
            with open(audio_path, 'rb') as audio_file:
                audio_data = base64.b64encode(audio_file.read()).decode('utf-8')
            
            # 准备请求数据
            request_data = {
                "model": "qwen3-asr-flash",  # 使用最新的ASR模型
                "input": {
                    "audio": f"data:audio/wav;base64,{audio_data}"
                },
                "parameters": {
                    "format": "srt",  # 输出SRT格式
                    "enable_timestamps": config.enable_timestamps,
                    "enable_punctuation": config.enable_punctuation
                }
            }
            
            # 发送请求到阿里云百炼API
            headers = {
                'Authorization': f'Bearer {config.aliyun_access_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                'https://dashscope.aliyuncs.com/api/v1/services/aigc/audio/asr',
                headers=headers,
                json=request_data,
                timeout=config.timeout if config.timeout > 0 else 300
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('output', {}).get('text'):
                    # 保存字幕文件
                    subtitle_content = result['output']['text']
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(subtitle_content)
                    
                    logger.info(f"阿里云语音识别字幕生成成功: {output_path}")
                    return output_path
                else:
                    raise SpeechRecognitionError("阿里云语音识别返回结果为空")
            else:
                error_detail = response.json().get('message', '未知错误') if response.headers.get('content-type', '').startswith('application/json') else response.text
                raise SpeechRecognitionError(f"阿里云语音识别API调用失败: {response.status_code} - {error_detail}")
            
        except Exception as e:
            error_msg = f"阿里云语音识别生成字幕时发生错误: {e}"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def _generate_subtitle_custom_api(self, video_path: Path, output_path: Path, 
                                     config: SpeechRecognitionConfig) -> Path:
        """使用自定义API生成字幕"""
        if not config.custom_api_url or not config.custom_api_key:
            raise SpeechRecognitionError(
                "自定义API配置不完整，请配置 custom_api_url 和 custom_api_key"
            )
        
        try:
            logger.info(f"开始使用自定义API生成字幕: {video_path}")
            
            # 检查视频文件是否存在
            if not video_path.exists():
                raise SpeechRecognitionError(f"视频文件不存在: {video_path}")
            
            # 提取音频文件
            audio_path = self._extract_audio_from_video(video_path, output_path.parent)
            
            # 准备API请求
            headers = {
                'Authorization': f'Bearer {config.custom_api_key}',
                'Content-Type': 'audio/wav'
            }
            
            # 发送音频文件到API
            with open(audio_path, 'rb') as audio_file:
                files = {'audio': audio_file}
                data = {
                    'language': config.language.value if config.language != LanguageCode.AUTO else 'auto',
                    'format': config.output_format
                }
                
                response = requests.post(
                    f"{config.custom_api_url}/transcribe",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=config.timeout if config.timeout > 0 else 300
                )
            
            if response.status_code == 200:
                # 保存字幕文件
                subtitle_content = response.text
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(subtitle_content)
                
                logger.info(f"自定义API字幕生成成功: {output_path}")
                return output_path
            else:
                raise SpeechRecognitionError(f"自定义API调用失败: {response.status_code} - {response.text}")
                
        except Exception as e:
            error_msg = f"自定义API生成字幕时发生错误: {e}"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def get_available_methods(self) -> Dict[SpeechRecognitionMethod, bool]:
        """获取可用的语音识别方法"""
        return self.available_methods.copy()
    
    def get_supported_languages(self) -> List[LanguageCode]:
        """获取支持的语言列表"""
        return list(LanguageCode)
    
    def get_whisper_models(self) -> List[str]:
        """获取可用的Whisper模型列表"""
        return ["tiny", "base", "small", "medium", "large"]


def generate_subtitle_for_video(video_path: Path, output_path: Optional[Path] = None, 
                               method: str = "auto", language: str = "auto", 
                               model: str = "base", enable_fallback: bool = True) -> Path:
    """
    为视频生成字幕文件的便捷函数
    
    Args:
        video_path: 视频文件路径
        output_path: 输出字幕文件路径
        method: 生成方法 ("auto", "whisper_local", "openai_api", "azure_speech", "google_speech", "aliyun_speech", "custom_api")
        language: 语言代码
        model: Whisper模型大小（仅对whisper_local有效）
        enable_fallback: 是否启用回退机制
        
    Returns:
        生成的字幕文件路径
        
    Raises:
        SpeechRecognitionError: 语音识别失败
    """
    # 创建配置
    config = SpeechRecognitionConfig(
        method=SpeechRecognitionMethod(method) if method != "auto" else SpeechRecognitionMethod.WHISPER_LOCAL,
        language=LanguageCode(language),
        model=model,
        enable_fallback=enable_fallback
    )
    
    recognizer = SpeechRecognizer()
    
    if method == "auto":
        # 自动选择最佳方法
        available_methods = recognizer.get_available_methods()
        
        # 按优先级选择方法（Whisper本地优先，因为免费且离线）
        priority_methods = [
            SpeechRecognitionMethod.WHISPER_LOCAL,
            SpeechRecognitionMethod.OPENAI_API,
            SpeechRecognitionMethod.AZURE_SPEECH,
            SpeechRecognitionMethod.GOOGLE_SPEECH,
            SpeechRecognitionMethod.ALIYUN_SPEECH,
            SpeechRecognitionMethod.CUSTOM_API
        ]
        
        for priority_method in priority_methods:
            if available_methods.get(priority_method, False):
                config.method = priority_method
                break
        else:
            raise SpeechRecognitionError("没有可用的语音识别服务，请安装whisper或配置API密钥")
    
    return recognizer.generate_subtitle(video_path, output_path, config)


def get_available_speech_recognition_methods() -> Dict[str, bool]:
    """
    获取可用的语音识别方法
    
    Returns:
        可用方法字典
    """
    recognizer = SpeechRecognizer()
    available_methods = recognizer.get_available_methods()
    
    return {
        method.value: available 
        for method, available in available_methods.items()
    }


def get_supported_languages() -> List[str]:
    """
    获取支持的语言列表
    
    Returns:
        支持的语言代码列表
    """
    return [lang.value for lang in LanguageCode]


def get_whisper_models() -> List[str]:
    """
    获取可用的Whisper模型列表
    
    Returns:
        Whisper模型列表
    """
    return ["tiny", "base", "small", "medium", "large"]

