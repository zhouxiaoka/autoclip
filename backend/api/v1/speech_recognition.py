"""
语音识别配置API
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from backend.utils.speech_recognizer import (
    SpeechRecognitionMethod, 
    SpeechRecognitionConfig, 
    SpeechRecognizer,
    generate_subtitle_for_video
)
from backend.core.desktop_config import (
    get_desktop_config, 
    save_desktop_config, 
    DesktopConfig,
    SpeechRecognitionSettings,
    WhisperConfig,
    ApiConfig
)
from backend.services.whisper_model_manager import (
    get_model_manager, 
    WhisperModelManager,
    ModelInfo,
    ModelStatus
)
from backend.services.speech_config_validator import get_config_validator

logger = logging.getLogger(__name__)
router = APIRouter()

# 全局语音识别器实例
_speech_recognizer: Optional[SpeechRecognizer] = None

def get_speech_recognizer() -> SpeechRecognizer:
    """获取语音识别器实例"""
    global _speech_recognizer
    if _speech_recognizer is None:
        _speech_recognizer = SpeechRecognizer()
    return _speech_recognizer

class SpeechConfigRequest(BaseModel):
    """语音识别配置请求"""
    method: str
    model: Optional[str] = "base"
    openaiApiKey: Optional[str] = None
    aliyunApiKey: Optional[str] = None
    enableTimestamps: Optional[bool] = True
    enablePunctuation: Optional[bool] = True
    enableSpeakerDiarization: Optional[bool] = False
    enableFallback: Optional[bool] = True
    fallbackMethod: Optional[str] = "whisper_local"
    timeout: Optional[int] = 1800  # 30分钟，适合Whisper模型处理
    outputFormat: Optional[str] = "srt"

class SpeechConfigResponse(BaseModel):
    """语音识别配置响应"""
    method: str
    model: str
    openaiApiKey: Optional[str] = None
    aliyunApiKey: Optional[str] = None
    enableTimestamps: bool
    enablePunctuation: bool
    enableSpeakerDiarization: bool
    enableFallback: bool
    fallbackMethod: str
    timeout: int
    outputFormat: str

class SpeechMethodStatus(BaseModel):
    """语音识别方法状态"""
    method: str
    available: bool
    message: Optional[str] = None

class WhisperModelInfo(BaseModel):
    """Whisper模型信息"""
    name: str
    size: str
    sizeBytes: int
    description: str
    accuracy: str
    speed: str
    status: str  # 'available' | 'downloading' | 'downloaded' | 'error'
    downloadProgress: Optional[int] = None

class TestSpeechServiceRequest(BaseModel):
    """测试语音识别服务请求"""
    method: str

class TestSpeechServiceResponse(BaseModel):
    """测试语音识别服务响应"""
    success: bool
    message: str

class DownloadModelRequest(BaseModel):
    """下载模型请求"""
    model: str

@router.get("/speech-recognition/config")
async def get_speech_config(config: DesktopConfig = Depends(get_desktop_config)):
    """获取语音识别配置"""
    try:
        speech_config = config.speech_recognition
        
        return {
            "method": speech_config.method,
            "whisper_config": {
                "model_name": speech_config.whisper_config.model_name,
                "language": speech_config.whisper_config.language,
                "custom_models_dir": speech_config.whisper_config.custom_models_dir,
                "enable_timestamps": speech_config.whisper_config.enable_timestamps,
                "enable_punctuation": speech_config.whisper_config.enable_punctuation,
                "enable_speaker_diarization": speech_config.whisper_config.enable_speaker_diarization,
                "timeout": speech_config.whisper_config.timeout
            },
            "openai_config": {
                "api_key": speech_config.openai_config.api_key,
                "language": speech_config.openai_config.language,
                "enable_timestamps": speech_config.openai_config.enable_timestamps,
                "enable_punctuation": speech_config.openai_config.enable_punctuation
            },
            "azure_config": {
                "api_key": speech_config.azure_config.api_key,
                "region": speech_config.azure_config.region,
                "language": speech_config.azure_config.language,
                "enable_timestamps": speech_config.azure_config.enable_timestamps,
                "enable_punctuation": speech_config.azure_config.enable_punctuation
            },
            "google_config": {
                "api_key": speech_config.google_config.api_key,
                "language": speech_config.google_config.language,
                "enable_timestamps": speech_config.google_config.enable_timestamps,
                "enable_punctuation": speech_config.google_config.enable_punctuation
            },
            "aliyun_config": {
                "api_key": speech_config.aliyun_config.api_key,
                "language": speech_config.aliyun_config.language,
                "enable_timestamps": speech_config.aliyun_config.enable_timestamps,
                "enable_punctuation": speech_config.aliyun_config.enable_punctuation
            },
            "custom_api_config": {
                "api_key": speech_config.custom_api_config.api_key,
                "endpoint": speech_config.custom_api_config.endpoint,
                "language": speech_config.custom_api_config.language,
                "enable_timestamps": speech_config.custom_api_config.enable_timestamps,
                "enable_punctuation": speech_config.custom_api_config.enable_punctuation
            },
            "enable_fallback": speech_config.enable_fallback,
            "fallback_method": speech_config.fallback_method,
            "output_format": speech_config.output_format
        }
    except Exception as e:
        logger.error(f"获取语音识别配置失败: {e}")
        raise HTTPException(status_code=500, detail="获取语音识别配置失败")

class SpeechConfigUpdateRequest(BaseModel):
    """语音识别配置更新请求"""
    method: str
    whisper_config: Optional[Dict[str, Any]] = None
    openai_config: Optional[Dict[str, Any]] = None
    azure_config: Optional[Dict[str, Any]] = None
    google_config: Optional[Dict[str, Any]] = None
    aliyun_config: Optional[Dict[str, Any]] = None
    custom_api_config: Optional[Dict[str, Any]] = None
    enable_fallback: Optional[bool] = None
    fallback_method: Optional[str] = None
    output_format: Optional[str] = None


@router.put("/speech-recognition/config")
async def update_speech_config(
    request: SpeechConfigUpdateRequest,
    config: DesktopConfig = Depends(get_desktop_config)
):
    """更新语音识别配置"""
    try:
        # 验证方法
        try:
            method = SpeechRecognitionMethod(request.method)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"不支持的语音识别方法: {request.method}")
        
        # 验证回退方法
        if request.fallback_method:
            try:
                fallback_method = SpeechRecognitionMethod(request.fallback_method)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"不支持的回退方法: {request.fallback_method}")
        
        # 更新配置
        speech_config = config.speech_recognition
        speech_config.method = request.method
        
        # 更新Whisper配置
        if request.whisper_config:
            for key, value in request.whisper_config.items():
                if hasattr(speech_config.whisper_config, key):
                    setattr(speech_config.whisper_config, key, value)
        
        # 更新API配置
        if request.openai_config:
            for key, value in request.openai_config.items():
                if hasattr(speech_config.openai_config, key):
                    setattr(speech_config.openai_config, key, value)
        
        if request.azure_config:
            for key, value in request.azure_config.items():
                if hasattr(speech_config.azure_config, key):
                    setattr(speech_config.azure_config, key, value)
        
        if request.google_config:
            for key, value in request.google_config.items():
                if hasattr(speech_config.google_config, key):
                    setattr(speech_config.google_config, key, value)
        
        if request.aliyun_config:
            for key, value in request.aliyun_config.items():
                if hasattr(speech_config.aliyun_config, key):
                    setattr(speech_config.aliyun_config, key, value)
        
        if request.custom_api_config:
            for key, value in request.custom_api_config.items():
                if hasattr(speech_config.custom_api_config, key):
                    setattr(speech_config.custom_api_config, key, value)
        
        # 更新其他配置
        if request.enable_fallback is not None:
            speech_config.enable_fallback = request.enable_fallback
        
        if request.fallback_method:
            speech_config.fallback_method = request.fallback_method
        
        if request.output_format:
            speech_config.output_format = request.output_format
        
        # 保存配置
        if save_desktop_config(config):
            logger.info(f"语音识别配置已更新: {request.method}")
            return {"message": "语音识别配置已更新", "success": True}
        else:
            raise HTTPException(status_code=500, detail="保存配置失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新语音识别配置失败: {e}")
        raise HTTPException(status_code=500, detail="更新语音识别配置失败")

@router.get("/speech-methods-status", response_model=List[SpeechMethodStatus])
async def get_speech_methods_status():
    """获取语音识别方法状态"""
    try:
        recognizer = get_speech_recognizer()
        available_methods = recognizer.get_available_methods()
        
        status_list = []
        for method in SpeechRecognitionMethod:
            available = available_methods.get(method, False)
            message = None
            
            if not available:
                if method == SpeechRecognitionMethod.WHISPER_LOCAL:
                    message = "需要安装Whisper"
                elif method == SpeechRecognitionMethod.OPENAI_API:
                    message = "需要配置OpenAI API Key"
                elif method == SpeechRecognitionMethod.ALIYUN_SPEECH:
                    message = "需要配置阿里云API Key"
                else:
                    message = "服务不可用"
            
            status_list.append(SpeechMethodStatus(
                method=method.value,
                available=available,
                message=message
            ))
        
        return status_list
        
    except Exception as e:
        logger.error(f"获取语音识别方法状态失败: {e}")
        raise HTTPException(status_code=500, detail="获取语音识别方法状态失败")

@router.get("/whisper-models")
async def get_whisper_models():
    """获取Whisper模型信息"""
    try:
        model_manager = get_model_manager()
        models_info = model_manager.get_all_models_info()
        
        models = []
        for model_info in models_info:
            models.append({
                "name": model_info.name,
                "size": model_info.size,
                "sizeBytes": model_info.size_bytes,
                "description": model_info.description,
                "accuracy": model_info.accuracy,
                "speed": model_info.speed,
                "status": model_info.status.value,
                "downloadProgress": model_info.download_progress,
                "localPath": model_info.local_path,
                "errorMessage": model_info.error_message
            })
        
        return models
        
    except Exception as e:
        logger.error(f"获取Whisper模型信息失败: {e}")
        raise HTTPException(status_code=500, detail="获取Whisper模型信息失败")

@router.post("/test-speech-service", response_model=TestSpeechServiceResponse)
async def test_speech_service(request: TestSpeechServiceRequest):
    """测试语音识别服务"""
    try:
        recognizer = get_speech_recognizer()
        available_methods = recognizer.get_available_methods()
        
        try:
            method = SpeechRecognitionMethod(request.method)
        except ValueError:
            return TestSpeechServiceResponse(
                success=False,
                message=f"不支持的语音识别方法: {request.method}"
            )
        
        if available_methods.get(method, False):
            return TestSpeechServiceResponse(
                success=True,
                message=f"{method.value} 服务可用"
            )
        else:
            return TestSpeechServiceResponse(
                success=False,
                message=f"{method.value} 服务不可用，请检查配置"
            )
            
    except Exception as e:
        logger.error(f"测试语音识别服务失败: {e}")
        return TestSpeechServiceResponse(
            success=False,
            message=f"测试失败: {str(e)}"
        )

@router.post("/whisper-models/download")
async def download_whisper_model(request: DownloadModelRequest):
    """下载Whisper模型"""
    try:
        model_manager = get_model_manager()
        
        # 检查模型是否已存在
        model_info = model_manager.get_model_info(request.model)
        if model_info and model_info.status == ModelStatus.DOWNLOADED:
            return {"message": f"模型 {request.model} 已存在", "success": True}
        
        # 开始下载
        success = await model_manager.download_model(request.model)
        
        if success:
            return {"message": f"模型 {request.model} 下载完成", "success": True}
        else:
            raise HTTPException(status_code=500, detail=f"模型 {request.model} 下载失败")
        
    except Exception as e:
        logger.error(f"下载Whisper模型失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载Whisper模型失败: {str(e)}")

@router.delete("/whisper-models/{model_name}")
async def delete_whisper_model(model_name: str):
    """删除Whisper模型"""
    try:
        model_manager = get_model_manager()
        
        # 检查模型是否存在
        model_info = model_manager.get_model_info(model_name)
        if not model_info or model_info.status != ModelStatus.DOWNLOADED:
            raise HTTPException(status_code=404, detail=f"模型 {model_name} 不存在")
        
        # 删除模型
        success = model_manager.delete_model(model_name)
        
        if success:
            return {"message": f"模型 {model_name} 已删除", "success": True}
        else:
            raise HTTPException(status_code=500, detail=f"删除模型 {model_name} 失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除Whisper模型失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除Whisper模型失败: {str(e)}")


@router.get("/whisper-models/{model_name}/status")
async def get_model_status(model_name: str):
    """获取模型状态"""
    try:
        model_manager = get_model_manager()
        model_info = model_manager.get_model_info(model_name)
        
        if not model_info:
            raise HTTPException(status_code=404, detail=f"模型 {model_name} 不存在")
        
        return {
            "name": model_info.name,
            "status": model_info.status.value,
            "downloadProgress": model_info.download_progress,
            "localPath": model_info.local_path,
            "errorMessage": model_info.error_message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模型状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取模型状态失败: {str(e)}")


@router.post("/whisper-models/{model_name}/cancel-download")
async def cancel_model_download(model_name: str):
    """取消模型下载"""
    try:
        model_manager = get_model_manager()
        success = model_manager.cancel_download(model_name)
        
        if success:
            return {"message": f"已取消模型 {model_name} 的下载", "success": True}
        else:
            return {"message": f"模型 {model_name} 没有正在下载", "success": False}
        
    except Exception as e:
        logger.error(f"取消模型下载失败: {e}")
        raise HTTPException(status_code=500, detail=f"取消模型下载失败: {str(e)}")


@router.post("/speech-recognition/validate")
async def validate_speech_config(
    request: SpeechConfigUpdateRequest,
    config: DesktopConfig = Depends(get_desktop_config)
):
    """验证语音转写配置"""
    try:
        # 创建临时配置对象进行验证
        temp_config = config.speech_recognition.copy()
        
        # 更新临时配置
        temp_config.method = request.method
        
        if request.whisper_config:
            for key, value in request.whisper_config.items():
                if hasattr(temp_config.whisper_config, key):
                    setattr(temp_config.whisper_config, key, value)
        
        if request.openai_config:
            for key, value in request.openai_config.items():
                if hasattr(temp_config.openai_config, key):
                    setattr(temp_config.openai_config, key, value)
        
        if request.azure_config:
            for key, value in request.azure_config.items():
                if hasattr(temp_config.azure_config, key):
                    setattr(temp_config.azure_config, key, value)
        
        if request.google_config:
            for key, value in request.google_config.items():
                if hasattr(temp_config.google_config, key):
                    setattr(temp_config.google_config, key, value)
        
        if request.aliyun_config:
            for key, value in request.aliyun_config.items():
                if hasattr(temp_config.aliyun_config, key):
                    setattr(temp_config.aliyun_config, key, value)
        
        if request.custom_api_config:
            for key, value in request.custom_api_config.items():
                if hasattr(temp_config.custom_api_config, key):
                    setattr(temp_config.custom_api_config, key, value)
        
        if request.enable_fallback is not None:
            temp_config.enable_fallback = request.enable_fallback
        
        if request.fallback_method:
            temp_config.fallback_method = request.fallback_method
        
        if request.output_format:
            temp_config.output_format = request.output_format
        
        # 验证配置
        validator = get_config_validator()
        validation_result = validator.validate_config(temp_config)
        
        return {
            "valid": validation_result["valid"],
            "errors": validation_result["errors"],
            "warnings": validation_result["warnings"],
            "recommendations": validation_result["recommendations"]
        }
        
    except Exception as e:
        logger.error(f"验证语音转写配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"验证配置失败: {str(e)}")


@router.get("/speech-recognition/recommendations")
async def get_speech_recommendations():
    """获取语音转写配置建议"""
    try:
        recommendations = {
            "scenarios": {
                "新手用户": {
                    "method": "whisper_local",
                    "model": "base",
                    "description": "免费离线，平衡准确度和速度"
                },
                "专业用户": {
                    "method": "openai_api",
                    "model": "whisper-1",
                    "description": "最高准确度，适合重要内容"
                },
                "中文内容": {
                    "method": "aliyun_speech",
                    "model": "default",
                    "description": "中文识别效果更好"
                },
                "企业应用": {
                    "method": "azure_speech",
                    "model": "default",
                    "description": "企业级服务，稳定可靠"
                }
            },
            "model_guide": {
                "tiny": {
                    "size": "39 MB",
                    "speed": "最快",
                    "accuracy": "较低",
                    "recommended_for": "实时处理、快速预览"
                },
                "base": {
                    "size": "74 MB",
                    "speed": "快",
                    "accuracy": "中等",
                    "recommended_for": "日常使用、平衡选择"
                },
                "small": {
                    "size": "244 MB",
                    "speed": "中等",
                    "accuracy": "较好",
                    "recommended_for": "重要内容、知识类视频"
                },
                "medium": {
                    "size": "769 MB",
                    "speed": "较慢",
                    "accuracy": "高",
                    "recommended_for": "专业用途、演讲内容"
                },
                "large": {
                    "size": "1550 MB",
                    "speed": "最慢",
                    "accuracy": "最高",
                    "recommended_for": "重要项目、最高质量要求"
                }
            },
            "tips": [
                "首次使用建议先下载base模型进行测试",
                "如果网络不稳定，建议使用本地Whisper模型",
                "中文内容推荐使用阿里云语音识别服务",
                "重要项目建议启用回退机制",
                "说话人分离功能会增加处理时间",
                "定期检查模型状态，确保服务可用"
            ]
        }
        
        return recommendations
        
    except Exception as e:
        logger.error(f"获取配置建议失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取建议失败: {str(e)}")