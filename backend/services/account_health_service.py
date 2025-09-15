from typing import Dict, List, Optional, Tuple
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..core.database import get_db
from ..models.bilibili import BilibiliAccount
from ..utils.crypto import decrypt_data, encrypt_data
from ..core.celery_app import celery_app

logger = logging.getLogger(__name__)

class AccountHealthStatus:
    """账号健康状态枚举"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    EXPIRED = "expired"
    UNKNOWN = "unknown"

class AccountHealthService:
    """账号健康检查服务"""
    
    def __init__(self):
        self.check_interval = 300  # 5分钟检查一次
        self.cookie_expire_days = 30  # Cookie过期天数
        self.warning_days = 7  # 提前警告天数
        
    async def check_account_health(self, account_id: int) -> Dict:
        """检查单个账号健康状态"""
        try:
            db = next(get_db())
            account = db.query(BilibiliAccount).filter(BilibiliAccount.id == account_id).first()
            
            if not account:
                return {
                    "account_id": account_id,
                    "status": AccountHealthStatus.UNKNOWN,
                    "message": "账号不存在",
                    "last_check": datetime.now()
                }
            
            # 检查Cookie有效性
            cookie_status = await self._check_cookie_validity(account)
            
            # 检查登录状态
            login_status = await self._check_login_status(account)
            
            # 检查上传权限
            upload_status = await self._check_upload_permission(account)
            
            # 综合评估健康状态
            overall_status = self._evaluate_overall_status(
                cookie_status, login_status, upload_status
            )
            
            # 更新账号状态
            account.health_status = overall_status["status"]
            account.last_health_check = datetime.now()
            account.health_details = {
                "cookie": cookie_status,
                "login": login_status,
                "upload": upload_status,
                "last_check": datetime.now().isoformat()
            }
            
            db.commit()
            
            return {
                "account_id": account_id,
                "username": account.username,
                "status": overall_status["status"],
                "message": overall_status["message"],
                "details": {
                    "cookie": cookie_status,
                    "login": login_status,
                    "upload": upload_status
                },
                "last_check": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"检查账号 {account_id} 健康状态失败: {str(e)}")
            return {
                "account_id": account_id,
                "status": AccountHealthStatus.UNKNOWN,
                "message": f"检查失败: {str(e)}",
                "last_check": datetime.now()
            }
    
    async def _check_cookie_validity(self, account: BilibiliAccount) -> Dict:
        """检查Cookie有效性"""
        try:
            if not account.cookies:
                return {
                    "status": AccountHealthStatus.CRITICAL,
                    "message": "Cookie为空",
                    "expires_in": None
                }
            
            # 解密Cookie
            try:
                cookies = decrypt_data(account.cookies)
            except Exception as e:
                return {
                    "status": AccountHealthStatus.CRITICAL,
                    "message": f"Cookie解密失败: {str(e)}",
                    "expires_in": None
                }
            
            # 检查Cookie格式和必要字段
            required_fields = ['SESSDATA', 'bili_jct', 'DedeUserID']
            missing_fields = []
            
            for field in required_fields:
                if field not in cookies:
                    missing_fields.append(field)
            
            if missing_fields:
                return {
                    "status": AccountHealthStatus.CRITICAL,
                    "message": f"Cookie缺少必要字段: {', '.join(missing_fields)}",
                    "expires_in": None
                }
            
            # 检查Cookie是否过期
            if account.cookie_expires_at:
                now = datetime.now()
                expires_in = (account.cookie_expires_at - now).days
                
                if expires_in <= 0:
                    return {
                        "status": AccountHealthStatus.EXPIRED,
                        "message": "Cookie已过期",
                        "expires_in": expires_in
                    }
                elif expires_in <= self.warning_days:
                    return {
                        "status": AccountHealthStatus.WARNING,
                        "message": f"Cookie将在 {expires_in} 天后过期",
                        "expires_in": expires_in
                    }
                else:
                    return {
                        "status": AccountHealthStatus.HEALTHY,
                        "message": "Cookie有效",
                        "expires_in": expires_in
                    }
            
            return {
                "status": AccountHealthStatus.HEALTHY,
                "message": "Cookie格式正确",
                "expires_in": None
            }
            
        except Exception as e:
            logger.error(f"检查Cookie有效性失败: {str(e)}")
            return {
                "status": AccountHealthStatus.UNKNOWN,
                "message": f"检查失败: {str(e)}",
                "expires_in": None
            }
    
    async def _check_login_status(self, account: BilibiliAccount) -> Dict:
        """检查登录状态"""
        try:
            import aiohttp
            
            if not account.cookies:
                return {
                    "status": AccountHealthStatus.CRITICAL,
                    "message": "无Cookie信息"
                }
            
            # 解密Cookie
            cookies = decrypt_data(account.cookies)
            
            # 构建Cookie字符串
            cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Cookie': cookie_str,
                'Referer': 'https://www.bilibili.com/'
            }
            
            # 检查登录状态
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.bilibili.com/x/web-interface/nav', headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == 0:
                            user_info = data.get('data', {})
                            if user_info.get('isLogin'):
                                return {
                                    "status": AccountHealthStatus.HEALTHY,
                                    "message": "登录状态正常",
                                    "user_info": {
                                        "uname": user_info.get('uname'),
                                        "mid": user_info.get('mid'),
                                        "level": user_info.get('level_info', {}).get('current_level')
                                    }
                                }
                            else:
                                return {
                                    "status": AccountHealthStatus.CRITICAL,
                                    "message": "未登录状态"
                                }
                        else:
                            return {
                                "status": AccountHealthStatus.CRITICAL,
                                "message": f"API返回错误: {data.get('message')}"
                            }
                    else:
                        return {
                            "status": AccountHealthStatus.CRITICAL,
                            "message": f"请求失败: HTTP {response.status}"
                        }
            
        except Exception as e:
            logger.error(f"检查登录状态失败: {str(e)}")
            return {
                "status": AccountHealthStatus.UNKNOWN,
                "message": f"检查失败: {str(e)}"
            }
    
    async def _check_upload_permission(self, account: BilibiliAccount) -> Dict:
        """检查上传权限"""
        try:
            import aiohttp
            
            if not account.cookies:
                return {
                    "status": AccountHealthStatus.CRITICAL,
                    "message": "无Cookie信息"
                }
            
            # 解密Cookie
            cookies = decrypt_data(account.cookies)
            
            # 构建Cookie字符串
            cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Cookie': cookie_str,
                'Referer': 'https://member.bilibili.com/'
            }
            
            # 检查上传权限
            async with aiohttp.ClientSession() as session:
                async with session.get('https://member.bilibili.com/x/web/archive/pre', headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == 0:
                            return {
                                "status": AccountHealthStatus.HEALTHY,
                                "message": "具有上传权限"
                            }
                        elif data.get('code') == -101:
                            return {
                                "status": AccountHealthStatus.CRITICAL,
                                "message": "账号未登录或Cookie失效"
                            }
                        else:
                            return {
                                "status": AccountHealthStatus.WARNING,
                                "message": f"上传权限受限: {data.get('message')}"
                            }
                    else:
                        return {
                            "status": AccountHealthStatus.WARNING,
                            "message": f"无法检查上传权限: HTTP {response.status}"
                        }
            
        except Exception as e:
            logger.error(f"检查上传权限失败: {str(e)}")
            return {
                "status": AccountHealthStatus.UNKNOWN,
                "message": f"检查失败: {str(e)}"
            }
    
    def _evaluate_overall_status(self, cookie_status: Dict, login_status: Dict, upload_status: Dict) -> Dict:
        """综合评估账号健康状态"""
        statuses = [cookie_status["status"], login_status["status"], upload_status["status"]]
        messages = []
        
        # 收集所有问题
        if cookie_status["status"] != AccountHealthStatus.HEALTHY:
            messages.append(f"Cookie: {cookie_status['message']}")
        if login_status["status"] != AccountHealthStatus.HEALTHY:
            messages.append(f"登录: {login_status['message']}")
        if upload_status["status"] != AccountHealthStatus.HEALTHY:
            messages.append(f"上传: {upload_status['message']}")
        
        # 确定整体状态
        if AccountHealthStatus.CRITICAL in statuses or AccountHealthStatus.EXPIRED in statuses:
            overall_status = AccountHealthStatus.CRITICAL
        elif AccountHealthStatus.WARNING in statuses:
            overall_status = AccountHealthStatus.WARNING
        elif AccountHealthStatus.UNKNOWN in statuses:
            overall_status = AccountHealthStatus.WARNING
        else:
            overall_status = AccountHealthStatus.HEALTHY
        
        if messages:
            message = "; ".join(messages)
        else:
            message = "账号状态正常"
        
        return {
            "status": overall_status,
            "message": message
        }
    
    async def check_all_accounts(self) -> List[Dict]:
        """检查所有账号健康状态"""
        try:
            db = next(get_db())
            accounts = db.query(BilibiliAccount).filter(BilibiliAccount.is_active == True).all()
            
            results = []
            for account in accounts:
                result = await self.check_account_health(account.id)
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"批量检查账号健康状态失败: {str(e)}")
            return []
    
    async def auto_refresh_cookies(self, account_id: int) -> Dict:
        """自动刷新Cookie"""
        try:
            db = next(get_db())
            account = db.query(BilibiliAccount).filter(BilibiliAccount.id == account_id).first()
            
            if not account:
                return {
                    "success": False,
                    "message": "账号不存在"
                }
            
            # 这里可以实现自动刷新Cookie的逻辑
            # 例如通过二维码登录、短信验证等方式
            # 目前返回提示信息
            
            return {
                "success": False,
                "message": "自动刷新Cookie功能待实现，请手动更新Cookie",
                "account_id": account_id,
                "username": account.username
            }
            
        except Exception as e:
            logger.error(f"自动刷新Cookie失败: {str(e)}")
            return {
                "success": False,
                "message": f"刷新失败: {str(e)}"
            }

# 全局服务实例
health_service = AccountHealthService()

# Celery任务
@celery_app.task(name="check_account_health")
def check_account_health_task(account_id: int):
    """检查账号健康状态的Celery任务"""
    import asyncio
    
    async def run_check():
        return await health_service.check_account_health(account_id)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_check())
        return result
    finally:
        loop.close()

@celery_app.task(name="check_all_accounts_health")
def check_all_accounts_health_task():
    """批量检查所有账号健康状态的Celery任务"""
    import asyncio
    
    async def run_check():
        return await health_service.check_all_accounts()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_check())
        return result
    finally:
        loop.close()

@celery_app.task(name="auto_refresh_cookies")
def auto_refresh_cookies_task(account_id: int):
    """自动刷新Cookie的Celery任务"""
    import asyncio
    
    async def run_refresh():
        return await health_service.auto_refresh_cookies(account_id)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_refresh())
        return result
    finally:
        loop.close()