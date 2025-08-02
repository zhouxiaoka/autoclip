"""
API密钥管理系统 - 提供安全的密钥存储、验证和轮换功能
"""
import os
import json
import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from .error_handler import ConfigurationError, APIError, ValidationError

logger = logging.getLogger(__name__)

class APIKeyManager:
    """API密钥管理器"""
    
    def __init__(self, storage_path: Optional[Path] = None, master_password: Optional[str] = None):
        """
        初始化API密钥管理器
        
        Args:
            storage_path: 密钥存储路径
            master_password: 主密码，用于加密存储
        """
        self.storage_path = storage_path or Path.home() / ".auto_clips" / "api_keys"
        self.master_password = master_password or self._get_master_password()
        self.fernet = self._create_fernet()
        self.keys_file = self.storage_path / "keys.enc"
        self.metadata_file = self.storage_path / "metadata.json"
        
        # 确保存储目录存在
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # 加载现有密钥
        self._load_keys()
    
    def _get_master_password(self) -> str:
        """获取主密码"""
        # 优先从环境变量获取
        master_password = os.getenv("AUTO_CLIPS_MASTER_PASSWORD")
        if master_password:
            return master_password
        
        # 如果没有设置，使用默认密码（仅用于开发环境）
        if os.getenv("AUTO_CLIPS_DEV_MODE"):
            return "dev_master_password"
        
        # 生产环境应该设置环境变量
        raise ConfigurationError(
            "未设置主密码。请设置 AUTO_CLIPS_MASTER_PASSWORD 环境变量。"
        )
    
    def _create_fernet(self) -> Fernet:
        """创建Fernet加密器"""
        # 使用主密码生成密钥
        salt = b'auto_clips_salt'  # 在实际应用中应该使用随机salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_password.encode()))
        return Fernet(key)
    
    def _load_keys(self):
        """加载存储的密钥"""
        self.keys: Dict[str, Dict[str, Any]] = {}
        
        if self.keys_file.exists():
            try:
                with open(self.keys_file, 'rb') as f:
                    encrypted_data = f.read()
                    decrypted_data = self.fernet.decrypt(encrypted_data)
                    self.keys = json.loads(decrypted_data.decode())
                logger.info(f"成功加载 {len(self.keys)} 个API密钥")
            except Exception as e:
                logger.warning(f"加载API密钥失败: {e}")
                self.keys = {}
        
        # 加载元数据
        self.metadata: Dict[str, Any] = {}
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            except Exception as e:
                logger.warning(f"加载API密钥元数据失败: {e}")
                self.metadata = {}
    
    def _save_keys(self):
        """保存密钥到文件"""
        try:
            # 加密并保存密钥
            data = json.dumps(self.keys, ensure_ascii=False)
            encrypted_data = self.fernet.encrypt(data.encode())
            
            with open(self.keys_file, 'wb') as f:
                f.write(encrypted_data)
            
            # 保存元数据（不加密）
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
            
            logger.debug("API密钥已保存")
        except Exception as e:
            logger.error(f"保存API密钥失败: {e}")
            raise ConfigurationError(f"保存API密钥失败: {e}")
    
    def add_api_key(self, key_name: str, api_key: str, provider: str = "dashscope", 
                   description: str = "", expires_at: Optional[datetime] = None) -> bool:
        """
        添加API密钥
        
        Args:
            key_name: 密钥名称
            api_key: API密钥值
            provider: 提供商（如dashscope）
            description: 描述信息
            expires_at: 过期时间
            
        Returns:
            是否添加成功
        """
        try:
            # 验证密钥格式
            if not self._validate_api_key_format(api_key, provider):
                raise ValidationError(f"无效的{provider} API密钥格式")
            
            # 检查密钥是否已存在
            if key_name in self.keys:
                logger.warning(f"密钥名称 '{key_name}' 已存在，将被覆盖")
            
            # 存储密钥信息
            self.keys[key_name] = {
                "api_key": api_key,
                "provider": provider,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "expires_at": expires_at.isoformat() if expires_at else None,
                "last_used": None,
                "usage_count": 0,
                "is_active": True
            }
            
            # 更新元数据
            self.metadata["last_updated"] = datetime.now().isoformat()
            self.metadata["total_keys"] = len(self.keys)
            
            # 保存到文件
            self._save_keys()
            
            logger.info(f"成功添加API密钥: {key_name}")
            return True
            
        except Exception as e:
            logger.error(f"添加API密钥失败: {e}")
            raise
    
    def get_api_key(self, key_name: str) -> Optional[str]:
        """
        获取API密钥
        
        Args:
            key_name: 密钥名称
            
        Returns:
            API密钥值，如果不存在或已过期则返回None
        """
        if key_name not in self.keys:
            return None
        
        key_info = self.keys[key_name]
        
        # 检查是否激活
        if not key_info.get("is_active", True):
            logger.warning(f"API密钥 '{key_name}' 已停用")
            return None
        
        # 检查是否过期
        if key_info.get("expires_at"):
            expires_at = datetime.fromisoformat(key_info["expires_at"])
            if datetime.now() > expires_at:
                logger.warning(f"API密钥 '{key_name}' 已过期")
                return None
        
        # 更新使用统计
        key_info["last_used"] = datetime.now().isoformat()
        key_info["usage_count"] = key_info.get("usage_count", 0) + 1
        self._save_keys()
        
        return key_info["api_key"]
    
    def get_active_api_key(self, provider: str = "dashscope") -> Optional[str]:
        """
        获取活跃的API密钥
        
        Args:
            provider: 提供商
            
        Returns:
            活跃的API密钥，如果没有则返回None
        """
        active_keys = []
        
        for key_name, key_info in self.keys.items():
            if (key_info.get("provider") == provider and 
                key_info.get("is_active", True)):
                
                # 检查是否过期
                if key_info.get("expires_at"):
                    expires_at = datetime.fromisoformat(key_info["expires_at"])
                    if datetime.now() > expires_at:
                        continue
                
                active_keys.append((key_name, key_info))
        
        if not active_keys:
            return None
        
        # 优先返回最近使用的密钥
        active_keys.sort(key=lambda x: x[1].get("last_used", ""), reverse=True)
        return active_keys[0][1]["api_key"]
    
    def remove_api_key(self, key_name: str) -> bool:
        """
        删除API密钥
        
        Args:
            key_name: 密钥名称
            
        Returns:
            是否删除成功
        """
        if key_name not in self.keys:
            logger.warning(f"API密钥 '{key_name}' 不存在")
            return False
        
        del self.keys[key_name]
        self.metadata["last_updated"] = datetime.now().isoformat()
        self.metadata["total_keys"] = len(self.keys)
        self._save_keys()
        
        logger.info(f"成功删除API密钥: {key_name}")
        return True
    
    def update_api_key(self, key_name: str, **updates) -> bool:
        """
        更新API密钥信息
        
        Args:
            key_name: 密钥名称
            **updates: 要更新的字段
            
        Returns:
            是否更新成功
        """
        if key_name not in self.keys:
            logger.warning(f"API密钥 '{key_name}' 不存在")
            return False
        
        # 允许更新的字段
        allowed_fields = ["description", "expires_at", "is_active"]
        
        for field, value in updates.items():
            if field in allowed_fields:
                if field == "expires_at" and value is not None:
                    if isinstance(value, datetime):
                        value = value.isoformat()
                self.keys[key_name][field] = value
        
        self.metadata["last_updated"] = datetime.now().isoformat()
        self._save_keys()
        
        logger.info(f"成功更新API密钥: {key_name}")
        return True
    
    def list_api_keys(self) -> List[Dict[str, Any]]:
        """
        列出所有API密钥（不包含实际密钥值）
        
        Returns:
            API密钥信息列表
        """
        result = []
        
        for key_name, key_info in self.keys.items():
            # 不返回实际的API密钥值
            safe_info = {
                "name": key_name,
                "provider": key_info.get("provider"),
                "description": key_info.get("description"),
                "created_at": key_info.get("created_at"),
                "expires_at": key_info.get("expires_at"),
                "last_used": key_info.get("last_used"),
                "usage_count": key_info.get("usage_count", 0),
                "is_active": key_info.get("is_active", True)
            }
            
            # 检查是否过期
            if key_info.get("expires_at"):
                expires_at = datetime.fromisoformat(key_info["expires_at"])
                safe_info["is_expired"] = datetime.now() > expires_at
            else:
                safe_info["is_expired"] = False
            
            result.append(safe_info)
        
        return result
    
    def test_api_key(self, key_name: str) -> Dict[str, Any]:
        """
        测试API密钥
        
        Args:
            key_name: 密钥名称
            
        Returns:
            测试结果
        """
        api_key = self.get_api_key(key_name)
        if not api_key:
            return {
                "success": False,
                "error": "密钥不存在或已过期"
            }
        
        try:
            # 这里可以添加实际的API测试逻辑
            # 目前只是简单的格式验证
            if self._validate_api_key_format(api_key, "dashscope"):
                return {
                    "success": True,
                    "message": "API密钥格式正确"
                }
            else:
                return {
                    "success": False,
                    "error": "API密钥格式不正确"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"测试失败: {str(e)}"
            }
    
    def _validate_api_key_format(self, api_key: str, provider: str) -> bool:
        """
        验证API密钥格式
        
        Args:
            api_key: API密钥
            provider: 提供商
            
        Returns:
            格式是否正确
        """
        if not api_key or len(api_key.strip()) < 10:
            return False
        
        if provider == "dashscope":
            # DashScope API密钥通常是sk-开头的字符串
            return api_key.startswith("sk-") and len(api_key) >= 20
        
        # 其他提供商可以添加相应的验证逻辑
        return True
    
    def rotate_api_key(self, key_name: str, new_api_key: str) -> bool:
        """
        轮换API密钥
        
        Args:
            key_name: 密钥名称
            new_api_key: 新的API密钥
            
        Returns:
            是否轮换成功
        """
        if key_name not in self.keys:
            logger.warning(f"API密钥 '{key_name}' 不存在")
            return False
        
        old_key_info = self.keys[key_name]
        
        # 验证新密钥格式
        if not self._validate_api_key_format(new_api_key, old_key_info.get("provider", "dashscope")):
            raise ValidationError("新API密钥格式不正确")
        
        # 更新密钥
        self.keys[key_name]["api_key"] = new_api_key
        self.keys[key_name]["rotated_at"] = datetime.now().isoformat()
        self.keys[key_name]["last_used"] = None
        self.keys[key_name]["usage_count"] = 0
        
        self.metadata["last_updated"] = datetime.now().isoformat()
        self._save_keys()
        
        logger.info(f"成功轮换API密钥: {key_name}")
        return True
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """
        获取使用统计
        
        Returns:
            使用统计信息
        """
        total_keys = len(self.keys)
        active_keys = sum(1 for k in self.keys.values() if k.get("is_active", True))
        expired_keys = 0
        total_usage = 0
        
        for key_info in self.keys.values():
            if key_info.get("expires_at"):
                expires_at = datetime.fromisoformat(key_info["expires_at"])
                if datetime.now() > expires_at:
                    expired_keys += 1
            
            total_usage += key_info.get("usage_count", 0)
        
        return {
            "total_keys": total_keys,
            "active_keys": active_keys,
            "expired_keys": expired_keys,
            "total_usage": total_usage,
            "last_updated": self.metadata.get("last_updated")
        }
    
    def cleanup_expired_keys(self) -> int:
        """
        清理过期的API密钥
        
        Returns:
            清理的密钥数量
        """
        cleaned_count = 0
        current_time = datetime.now()
        
        keys_to_remove = []
        
        for key_name, key_info in self.keys.items():
            if key_info.get("expires_at"):
                expires_at = datetime.fromisoformat(key_info["expires_at"])
                if current_time > expires_at:
                    keys_to_remove.append(key_name)
        
        for key_name in keys_to_remove:
            self.remove_api_key(key_name)
            cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"清理了 {cleaned_count} 个过期的API密钥")
        
        return cleaned_count

# 全局API密钥管理器实例
api_key_manager = APIKeyManager()

def get_api_key(key_name: Optional[str] = None, provider: str = "dashscope") -> Optional[str]:
    """
    获取API密钥的便捷函数
    
    Args:
        key_name: 密钥名称，如果为None则获取活跃密钥
        provider: 提供商
        
    Returns:
        API密钥
    """
    if key_name:
        return api_key_manager.get_api_key(key_name)
    else:
        return api_key_manager.get_active_api_key(provider)

def set_api_key(api_key: str, key_name: str = "default", provider: str = "dashscope") -> bool:
    """
    设置API密钥的便捷函数
    
    Args:
        api_key: API密钥
        key_name: 密钥名称
        provider: 提供商
        
    Returns:
        是否设置成功
    """
    return api_key_manager.add_api_key(key_name, api_key, provider) 