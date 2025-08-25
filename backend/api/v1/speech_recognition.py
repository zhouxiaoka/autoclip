"""
语音识别API端点
提供语音识别配置管理和状态查询功能
"""
import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from pathlib import Path

from backend.utils.speech_recognizer import (
    get_available_speech_recognition_methods,
    get_supported_languages,
    get_whisper_models,
    SpeechRecognitionConfig,
    SpeechRecognitionMethod,
    LanguageCode
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/speech-recognition", tags=["语音识别"])


class SpeechRecognitionStatus(BaseModel):
    """语音识别状态"""
    available_methods: Dict[str, bool]
    supported_languages: List[str]
    whisper_models: List[str]
    default_config: Dict[str, Any]
    
    class Config:
        arbitrary_types_allowed = True


class SpeechRecognitionRequest(BaseModel):
    """语音识别请求"""
    method: str
    language: str = "auto"
    model: str = "base"
    timeout: int = 300
    output_format: str = "srt"
    enable_timestamps: bool = True
    enable_punctuation: bool = True
    enable_speaker_diarization: bool = False


@router.get("/status", response_model=SpeechRecognitionStatus)
async def get_speech_recognition_status():
    """获取语音识别状态"""
    try:
        available_methods = get_available_speech_recognition_methods()
        supported_languages = get_supported_languages()
        whisper_models = get_whisper_models()
        
        # 默认配置
        default_config = SpeechRecognitionConfig().__dict__
        # 转换枚举为字符串
        default_config["method"] = default_config["method"].value
        default_config["language"] = default_config["language"].value
        
        return SpeechRecognitionStatus(
            available_methods=available_methods,
            supported_languages=supported_languages,
            whisper_models=whisper_models,
            default_config=default_config
        )
    except Exception as e:
        logger.error(f"获取语音识别状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取语音识别状态失败: {e}")


@router.get("/methods")
async def get_available_methods():
    """获取可用的语音识别方法"""
    try:
        return get_available_speech_recognition_methods()
    except Exception as e:
        logger.error(f"获取可用方法失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取可用方法失败: {e}")


@router.get("/languages")
async def get_supported_languages_list():
    """获取支持的语言列表"""
    try:
        return get_supported_languages()
    except Exception as e:
        logger.error(f"获取支持语言失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取支持语言失败: {e}")


@router.get("/whisper-models")
async def get_whisper_models_list():
    """获取可用的Whisper模型列表"""
    try:
        return get_whisper_models()
    except Exception as e:
        logger.error(f"获取Whisper模型失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取Whisper模型失败: {e}")


@router.post("/test")
async def test_speech_recognition(request: SpeechRecognitionRequest):
    """测试语音识别配置"""
    try:
        # 验证方法是否可用
        available_methods = get_available_speech_recognition_methods()
        if not available_methods.get(request.method, False):
            raise HTTPException(
                status_code=400, 
                detail=f"语音识别方法 '{request.method}' 不可用"
            )
        
        # 验证语言是否支持
        supported_languages = get_supported_languages()
        if request.language not in supported_languages:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的语言: {request.language}"
            )
        
        # 验证Whisper模型（如果使用whisper）
        if request.method == "whisper_local":
            whisper_models = get_whisper_models()
            if request.model not in whisper_models:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的Whisper模型: {request.model}"
                )
        
        return {
            "status": "success",
            "message": "语音识别配置验证通过",
            "config": request.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试语音识别配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"测试语音识别配置失败: {e}")


@router.get("/install-guide")
async def get_install_guide(method: str = Query(..., description="语音识别方法")):
    """获取安装指南"""
    guides = {
        "whisper_local": {
            "title": "本地Whisper安装指南",
            "description": "安装本地Whisper语音识别工具",
            "steps": [
                "1. 安装Python依赖: pip install openai-whisper",
                "2. 安装系统依赖:",
                "   - Ubuntu/Debian: sudo apt install ffmpeg",
                "   - macOS: brew install ffmpeg",
                "   - Windows: 下载ffmpeg并添加到PATH",
                "3. 验证安装: whisper --help",
                "4. 可选：安装PyTorch GPU支持以提高性能"
            ],
            "notes": [
                "Whisper支持多种模型大小：tiny(39MB), base(74MB), small(244MB), medium(769MB), large(1550MB)",
                "模型越大，准确率越高，但处理速度越慢",
                "首次使用时会自动下载模型文件"
            ]
        },
        "openai_api": {
            "title": "OpenAI API配置指南",
            "description": "配置OpenAI API语音识别",
            "steps": [
                "1. 注册OpenAI账户并获取API密钥",
                "2. 设置环境变量: export OPENAI_API_KEY='your-api-key'",
                "3. 或在配置文件中设置API密钥"
            ],
            "notes": [
                "需要网络连接",
                "有API调用费用",
                "准确率较高"
            ]
        },
        "azure_speech": {
            "title": "Azure Speech Services配置指南",
            "description": "配置Azure Speech Services",
            "steps": [
                "1. 创建Azure账户并开通Speech Services",
                "2. 获取API密钥和区域信息",
                "3. 设置环境变量:",
                "   export AZURE_SPEECH_KEY='your-api-key'",
                "   export AZURE_SPEECH_REGION='your-region'"
            ],
            "notes": [
                "需要Azure账户",
                "有API调用费用",
                "支持多种语言和功能"
            ]
        },
        "google_speech": {
            "title": "Google Speech-to-Text配置指南",
            "description": "配置Google Speech-to-Text",
            "steps": [
                "1. 创建Google Cloud项目",
                "2. 启用Speech-to-Text API",
                "3. 创建服务账户并下载凭证文件",
                "4. 设置环境变量: export GOOGLE_APPLICATION_CREDENTIALS='path/to/credentials.json'"
            ],
            "notes": [
                "需要Google Cloud账户",
                "有API调用费用",
                "支持多种语言和高级功能"
            ]
        },
        "aliyun_speech": {
            "title": "阿里云语音识别配置指南",
            "description": "配置阿里云语音识别",
            "steps": [
                "1. 注册阿里云账户",
                "2. 开通智能语音交互服务",
                "3. 创建AccessKey和AppKey",
                "4. 设置环境变量:",
                "   export ALIYUN_ACCESS_KEY_ID='your-access-key'",
                "   export ALIYUN_ACCESS_KEY_SECRET='your-secret-key'",
                "   export ALIYUN_SPEECH_APP_KEY='your-app-key'"
            ],
            "notes": [
                "需要阿里云账户",
                "有API调用费用",
                "支持中文识别效果较好"
            ]
        }
    }
    
    if method not in guides:
        raise HTTPException(status_code=400, detail=f"不支持的语音识别方法: {method}")
    
    return guides[method]
