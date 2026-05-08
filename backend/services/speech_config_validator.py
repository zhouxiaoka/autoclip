"""
语音转写配置验证服务
负责验证配置的有效性和完整性
"""
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from backend.core.desktop_config import SpeechRecognitionSettings, WhisperConfig, ApiConfig
from backend.services.whisper_model_manager import get_model_manager, ModelStatus

logger = logging.getLogger(__name__)


class SpeechConfigValidator:
    """语音转写配置验证器"""
    
    def __init__(self):
        self.model_manager = get_model_manager()
    
    def validate_config(self, config: SpeechRecognitionSettings) -> Dict[str, any]:
        """
        验证语音转写配置
        
        Args:
            config: 语音转写配置
            
        Returns:
            验证结果字典
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "recommendations": []
        }
        
        # 验证主方法
        method_validation = self._validate_method(config.method)
        if not method_validation["valid"]:
            result["valid"] = False
            result["errors"].extend(method_validation["errors"])
        
        # 验证具体配置
        if config.method == "whisper_local":
            whisper_validation = self._validate_whisper_config(config.whisper_config)
            if not whisper_validation["valid"]:
                result["valid"] = False
                result["errors"].extend(whisper_validation["errors"])
            result["warnings"].extend(whisper_validation["warnings"])
            result["recommendations"].extend(whisper_validation["recommendations"])
        
        elif config.method in ["openai_api", "azure_speech", "google_speech", "aliyun_speech", "custom_api"]:
            api_validation = self._validate_api_config(config, config.method)
            if not api_validation["valid"]:
                result["valid"] = False
                result["errors"].extend(api_validation["errors"])
            result["warnings"].extend(api_validation["warnings"])
            result["recommendations"].extend(api_validation["recommendations"])
        
        # 验证回退配置
        if config.enable_fallback:
            fallback_validation = self._validate_fallback_config(config)
            if not fallback_validation["valid"]:
                result["warnings"].extend(fallback_validation["warnings"])
        
        return result
    
    def _validate_method(self, method: str) -> Dict[str, any]:
        """验证方法选择"""
        valid_methods = [
            "whisper_local", "openai_api", "azure_speech", 
            "google_speech", "aliyun_speech", "custom_api"
        ]
        
        if method not in valid_methods:
            return {
                "valid": False,
                "errors": [f"不支持的语音识别方法: {method}"]
            }
        
        return {"valid": True, "errors": []}
    
    def _validate_whisper_config(self, config: WhisperConfig) -> Dict[str, any]:
        """验证Whisper配置"""
        result = {"valid": True, "errors": [], "warnings": [], "recommendations": []}
        
        # 验证模型名称
        valid_models = ["tiny", "base", "small", "medium", "large"]
        if config.model_name not in valid_models:
            result["valid"] = False
            result["errors"].append(f"不支持的Whisper模型: {config.model_name}")
        
        # 检查模型是否已下载
        model_info = self.model_manager.get_model_info(config.model_name)
        if model_info and model_info.status != ModelStatus.DOWNLOADED:
            if model_info.status == ModelStatus.AVAILABLE:
                result["warnings"].append(f"模型 {config.model_name} 未下载，首次使用时会自动下载")
            elif model_info.status == ModelStatus.DOWNLOADING:
                result["warnings"].append(f"模型 {config.model_name} 正在下载中")
            elif model_info.status == ModelStatus.ERROR:
                result["errors"].append(f"模型 {config.model_name} 下载失败")
        
        # 验证超时时间
        if config.timeout < 60:
            result["warnings"].append("超时时间过短，建议至少60秒")
        elif config.timeout > 7200:
            result["warnings"].append("超时时间过长，建议不超过2小时")
        
        # 验证自定义模型目录
        if config.custom_models_dir:
            custom_dir = Path(config.custom_models_dir)
            if not custom_dir.exists():
                result["errors"].append(f"自定义模型目录不存在: {config.custom_models_dir}")
            elif not custom_dir.is_dir():
                result["errors"].append(f"自定义模型目录不是有效目录: {config.custom_models_dir}")
        
        # 添加推荐
        if config.model_name == "tiny":
            result["recommendations"].append("tiny模型速度最快但准确度较低，建议用于实时处理")
        elif config.model_name == "base":
            result["recommendations"].append("base模型是平衡选择，推荐日常使用")
        elif config.model_name in ["small", "medium", "large"]:
            result["recommendations"].append(f"{config.model_name}模型准确度高但速度较慢，适合重要内容")
        
        return result
    
    def _validate_api_config(self, config: SpeechRecognitionSettings, method: str) -> Dict[str, any]:
        """验证API配置"""
        result = {"valid": True, "errors": [], "warnings": [], "recommendations": []}
        
        # 获取对应的API配置
        if method == "openai_api":
            api_config = config.openai_config
        elif method == "azure_speech":
            api_config = config.azure_config
        elif method == "google_speech":
            api_config = config.google_config
        elif method == "aliyun_speech":
            api_config = config.aliyun_config
        elif method == "custom_api":
            api_config = config.custom_api_config
        else:
            return {"valid": False, "errors": [f"不支持的API方法: {method}"]}
        
        # 验证API密钥
        if not api_config.api_key:
            result["valid"] = False
            result["errors"].append(f"{method} API密钥不能为空")
        elif len(api_config.api_key) < 10:
            result["warnings"].append("API密钥长度过短，请检查是否正确")
        
        # 验证Azure区域
        if method == "azure_speech" and not api_config.region:
            result["valid"] = False
            result["errors"].append("Azure Speech服务需要指定区域")
        
        # 验证自定义API端点
        if method == "custom_api":
            if not api_config.endpoint:
                result["valid"] = False
                result["errors"].append("自定义API需要指定端点URL")
            elif not api_config.endpoint.startswith(("http://", "https://")):
                result["errors"].append("API端点必须是有效的HTTP/HTTPS URL")
        
        # 添加推荐
        if method == "openai_api":
            result["recommendations"].append("OpenAI API准确度最高，但需要付费")
        elif method == "azure_speech":
            result["recommendations"].append("Azure Speech适合企业级应用，支持多种语言")
        elif method == "google_speech":
            result["recommendations"].append("Google Speech功能丰富，支持实时识别")
        elif method == "aliyun_speech":
            result["recommendations"].append("阿里云语音识别对中文优化较好")
        
        return result
    
    def _validate_fallback_config(self, config: SpeechRecognitionSettings) -> Dict[str, any]:
        """验证回退配置"""
        result = {"valid": True, "warnings": [], "recommendations": []}
        
        # 检查回退方法是否与主方法相同
        if config.fallback_method == config.method:
            result["warnings"].append("回退方法与主方法相同，建议选择不同的回退方法")
        
        # 检查回退方法是否可用
        if config.fallback_method == "whisper_local":
            model_info = self.model_manager.get_model_info(config.whisper_config.model_name)
            if model_info and model_info.status not in [ModelStatus.DOWNLOADED, ModelStatus.AVAILABLE]:
                result["warnings"].append("回退方法使用的Whisper模型不可用")
        
        # 添加推荐
        if config.method != "whisper_local" and config.fallback_method != "whisper_local":
            result["recommendations"].append("建议将Whisper本地模型作为回退方法，确保离线可用")
        
        return result
    
    def get_config_recommendations(self, config: SpeechRecognitionSettings) -> List[str]:
        """获取配置建议"""
        recommendations = []
        
        # 根据使用场景推荐
        if config.method == "whisper_local":
            if config.whisper_config.model_name == "tiny":
                recommendations.append("tiny模型适合快速处理，但准确度较低")
            elif config.whisper_config.model_name in ["medium", "large"]:
                recommendations.append("大模型准确度高但处理时间长，适合重要内容")
        
        # 网络环境建议
        if config.method != "whisper_local":
            recommendations.append("使用API服务需要稳定的网络连接")
            if config.enable_fallback and config.fallback_method == "whisper_local":
                recommendations.append("已配置本地回退，确保离线可用")
        
        # 性能建议
        if config.whisper_config.enable_speaker_diarization:
            recommendations.append("说话人分离功能会增加处理时间")
        
        return recommendations


# 全局验证器实例
_validator: Optional[SpeechConfigValidator] = None


def get_config_validator() -> SpeechConfigValidator:
    """获取配置验证器实例"""
    global _validator
    if _validator is None:
        _validator = SpeechConfigValidator()
    return _validator
