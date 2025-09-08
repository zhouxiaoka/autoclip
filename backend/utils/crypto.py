"""
加密工具
用于加密存储敏感信息如cookies
"""

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)

# 获取加密密钥
def get_encryption_key():
    """获取加密密钥"""
    # 从环境变量获取密钥，如果没有则生成一个
    key = os.getenv('ENCRYPTION_KEY')
    if not key:
        # 生成新密钥
        key = Fernet.generate_key()
        logger.warning("ENCRYPTION_KEY环境变量未设置，使用临时密钥。请设置环境变量以保持数据安全。")
    
    if isinstance(key, str):
        key = key.encode()
    
    return key

def encrypt_data(data: str) -> str:
    """加密数据"""
    try:
        key = get_encryption_key()
        f = Fernet(key)
        encrypted_data = f.encrypt(data.encode())
        return base64.b64encode(encrypted_data).decode()
    except Exception as e:
        logger.error(f"加密数据失败: {str(e)}")
        raise

def decrypt_data(encrypted_data: str) -> str:
    """解密数据"""
    try:
        key = get_encryption_key()
        f = Fernet(key)
        decoded_data = base64.b64decode(encrypted_data.encode())
        decrypted_data = f.decrypt(decoded_data)
        return decrypted_data.decode()
    except Exception as e:
        logger.error(f"解密数据失败: {str(e)}")
        raise

