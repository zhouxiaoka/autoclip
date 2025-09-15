"""
B站服务类 - 重构版本
移除bilitool依赖，使用直接API调用
"""

import asyncio
import json
import logging
import os
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID

import aiofiles
import aiohttp
from sqlalchemy.orm import Session

from ..models.bilibili import BilibiliAccount, UploadRecord
from ..schemas.bilibili import BilibiliAccountCreate, UploadRequest
from ..utils.crypto import encrypt_data, decrypt_data

logger = logging.getLogger(__name__)


class BilibiliAccountService:
    """B站账号服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def verify_cookie(self, cookie: str) -> Tuple[bool, Optional[Dict]]:
        """验证B站Cookie是否有效"""
        try:
            headers = {
                "Cookie": cookie,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/"
            }
            
            async with aiohttp.ClientSession() as session:
                # 首先检查登录状态
                async with session.get(
                    "https://api.bilibili.com/x/web-interface/nav",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    data = await response.json()
                    
                    if data.get("code") == 0 and data.get("data", {}).get("isLogin"):
                        user_info = data["data"]
                        
                        return True, {
                            "uid": user_info.get("mid"),
                            "username": user_info.get("uname"),
                            "face": user_info.get("face"),
                            "level": user_info.get("level_info", {}).get("current_level", 0),
                            "can_upload": True,  # 暂时设为True，避免额外的API调用
                            "vip_status": user_info.get("vipStatus", 0),
                            "verified_at": datetime.now().isoformat()
                        }
                    else:
                        logger.warning(f"Cookie验证失败: code={data.get('code')}, message={data.get('message')}")
                        return False, None
                        
        except asyncio.TimeoutError:
            logger.error("验证Cookie超时")
            return False, None
        except Exception as e:
            logger.error(f"验证Cookie失败: {e}")
            return False, None
    
    async def create_account(self, account_data: BilibiliAccountCreate) -> BilibiliAccount:
        """创建B站账号"""
        try:
            # 验证Cookie
            is_valid, user_info = await self.verify_cookie(account_data.cookie_content)
            if not is_valid:
                raise ValueError("无效的Cookie，请检查Cookie是否正确或已过期")
            
            # 检查账号是否已存在
            existing_account = self.db.query(BilibiliAccount).filter(
                BilibiliAccount.username == user_info.get("username")
            ).first()
            
            if existing_account:
                # 更新现有账号信息
                existing_account.cookies = encrypt_data(account_data.cookie_content)
                existing_account.nickname = account_data.nickname or user_info.get("username")
                existing_account.status = "active"
                existing_account.updated_at = datetime.now()
                
                self.db.commit()
                self.db.refresh(existing_account)
                
                logger.info(f"更新现有B站账号: {existing_account.username}")
                return existing_account
            
            # 加密存储cookies
            encrypted_cookies = encrypt_data(account_data.cookie_content)
            
            # 创建新账号记录
            account = BilibiliAccount(
                username=user_info.get("username", account_data.username),
                nickname=account_data.nickname or user_info.get("username", "B站用户"),
                cookies=encrypted_cookies,
                status="active",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            self.db.add(account)
            self.db.commit()
            self.db.refresh(account)
            
            logger.info(f"B站账号创建成功: {account.username} (UID: {user_info.get('uid')})")
            return account
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"创建B站账号失败: {e}")
            raise
    
    async def check_account_health(self, account_id: int) -> Dict[str, Any]:
        """检查账号健康状态"""
        try:
            account = self.db.query(BilibiliAccount).filter(
                BilibiliAccount.id == account_id
            ).first()
            
            if not account:
                raise ValueError("账号不存在")
            
            # 解密Cookie
            decrypted_cookies = decrypt_data(account.cookies)
            
            # 验证Cookie有效性
            is_valid, user_info = await self.verify_cookie(decrypted_cookies)
            
            health_status = {
                "account_id": account_id,
                "username": account.username,
                "is_valid": is_valid,
                "checked_at": datetime.now().isoformat(),
                "last_verified": account.updated_at.isoformat() if account.updated_at else None
            }
            
            if is_valid and user_info:
                health_status.update({
                    "user_info": user_info,
                    "can_upload": user_info.get("can_upload", False),
                    "level": user_info.get("level", 0),
                    "vip_status": user_info.get("vip_status", 0)
                })
                
                # 更新账号状态
                account.status = "active"
                account.updated_at = datetime.now()
            else:
                health_status["error"] = "Cookie已失效或账号异常"
                account.status = "inactive"
            
            self.db.commit()
            return health_status
            
        except Exception as e:
            logger.error(f"检查账号健康状态失败: {e}")
            return {
                "account_id": account_id,
                "is_valid": False,
                "error": str(e),
                "checked_at": datetime.now().isoformat()
            }
    
    async def batch_check_accounts_health(self) -> List[Dict[str, Any]]:
        """批量检查所有账号健康状态"""
        try:
            accounts = self.db.query(BilibiliAccount).all()
            results = []
            
            for account in accounts:
                health_status = await self.check_account_health(account.id)
                results.append(health_status)
                
                # 避免请求过于频繁
                await asyncio.sleep(1)
            
            logger.info(f"批量检查完成，共检查 {len(results)} 个账号")
            return results
            
        except Exception as e:
            logger.error(f"批量检查账号健康状态失败: {e}")
            raise
    
    def get_active_accounts(self) -> List[BilibiliAccount]:
        """获取所有活跃账号"""
        try:
            accounts = self.db.query(BilibiliAccount).filter(
                BilibiliAccount.status == "active"
            ).order_by(BilibiliAccount.updated_at.desc()).all()
            
            return accounts
            
        except Exception as e:
            logger.error(f"获取活跃账号失败: {e}")
            return []
    
    def get_account_by_id(self, account_id: int) -> Optional[BilibiliAccount]:
        """根据ID获取账号"""
        try:
            return self.db.query(BilibiliAccount).filter(
                BilibiliAccount.id == account_id
            ).first()
            
        except Exception as e:
            logger.error(f"获取账号失败: {e}")
            return None
    
    def select_best_account(self, exclude_ids: List[int] = None) -> Optional[BilibiliAccount]:
        """智能选择最佳上传账号"""
        try:
            query = self.db.query(BilibiliAccount).filter(
                BilibiliAccount.status == "active"
            )
            
            if exclude_ids:
                query = query.filter(~BilibiliAccount.id.in_(exclude_ids))
            
            accounts = query.all()
            
            if not accounts:
                return None
            
            # 按优先级排序：VIP > 等级 > 最近使用时间
            def account_priority(account):
                # VIP账号优先
                vip_score = account.vip_status * 1000 if hasattr(account, 'vip_status') else 0
                # 等级分数
                level_score = getattr(account, 'level', 0) * 100
                # 最近使用时间（越久未使用越优先）
                last_used = account.updated_at or account.created_at
                time_score = (datetime.now() - last_used).total_seconds() / 3600  # 小时数
                
                return vip_score + level_score + time_score
            
            best_account = max(accounts, key=account_priority)
            logger.info(f"选择账号进行上传: {best_account.username} (ID: {best_account.id})")
            
            return best_account
            
        except Exception as e:
            logger.error(f"选择最佳账号失败: {e}")
            return None
    
    def get_account_upload_stats(self, account_id: int, days: int = 7) -> Dict[str, Any]:
        """获取账号上传统计信息"""
        try:
            from datetime import timedelta
            
            start_date = datetime.now() - timedelta(days=days)
            
            # 查询上传记录
            upload_records = self.db.query(UploadRecord).filter(
                UploadRecord.account_id == account_id,
                UploadRecord.created_at >= start_date
            ).all()
            
            total_uploads = len(upload_records)
            successful_uploads = len([r for r in upload_records if r.status == 'success'])
            failed_uploads = len([r for r in upload_records if r.status == 'failed'])
            
            success_rate = (successful_uploads / total_uploads * 100) if total_uploads > 0 else 0
            
            return {
                "account_id": account_id,
                "days": days,
                "total_uploads": total_uploads,
                "successful_uploads": successful_uploads,
                "failed_uploads": failed_uploads,
                "success_rate": round(success_rate, 2),
                "last_upload": upload_records[-1].created_at.isoformat() if upload_records else None
            }
            
        except Exception as e:
            logger.error(f"获取账号统计信息失败: {e}")
            return {
                "account_id": account_id,
                "error": str(e)
            }
    
    def rotate_accounts_for_batch_upload(self, video_count: int) -> List[BilibiliAccount]:
        """为批量上传分配账号（负载均衡）"""
        try:
            active_accounts = self.get_active_accounts()
            
            if not active_accounts:
                return []
            
            # 如果视频数量少于账号数量，直接分配
            if video_count <= len(active_accounts):
                return active_accounts[:video_count]
            
            # 否则进行轮换分配
            allocated_accounts = []
            for i in range(video_count):
                account_index = i % len(active_accounts)
                allocated_accounts.append(active_accounts[account_index])
            
            logger.info(f"为 {video_count} 个视频分配了 {len(set(allocated_accounts))} 个账号")
            return allocated_accounts
            
        except Exception as e:
            logger.error(f"账号轮换分配失败: {e}")
            return []
    
    def update_account_usage(self, account_id: int):
        """更新账号使用时间"""
        try:
            account = self.get_account_by_id(account_id)
            if account:
                account.updated_at = datetime.now()
                self.db.commit()
                
        except Exception as e:
            logger.error(f"更新账号使用时间失败: {e}")
    
    def get_accounts(self) -> List[BilibiliAccount]:
        """获取所有账号"""
        return self.db.query(BilibiliAccount).all()
    
    def get_account(self, account_id: UUID) -> Optional[BilibiliAccount]:
        """获取指定账号"""
        return self.db.query(BilibiliAccount).filter(BilibiliAccount.id == account_id).first()
    
    def delete_account(self, account_id: UUID) -> bool:
        """删除账号"""
        account = self.get_account(account_id)
        if not account:
            return False
        
        try:
            # 先删除所有相关的投稿记录
            from ..models.bilibili import UploadRecord
            upload_records = self.db.query(UploadRecord).filter(UploadRecord.account_id == account_id).all()
            
            for record in upload_records:
                logger.info(f"删除相关投稿记录: {record.id}")
                self.db.delete(record)
            
            # 删除账号
            self.db.delete(account)
            self.db.commit()
            
            logger.info(f"B站账号删除成功: {account.username}，同时删除了 {len(upload_records)} 条相关投稿记录")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"删除账号失败: {str(e)}")
            return False
    
    def check_account_status(self, account_id: UUID) -> bool:
        """检查账号状态"""
        account = self.get_account(account_id)
        if not account:
            return False
        
        try:
            # 尝试解密cookies
            try:
                cookies_data_str = decrypt_data(account.cookies)
                # 验证cookie字符串格式
                if not cookies_data_str or not isinstance(cookies_data_str, str):
                    return False
                return True
            except Exception as e:
                logger.warning(f"解密cookies失败: {str(e)}")
                return False
                    
        except Exception as e:
            logger.error(f"检查账号状态失败: {str(e)}")
            return False


class BilibiliUploadService:
    """B站投稿服务 - 使用直接API调用"""
    
    def __init__(self, db: Session):
        self.db = db
        self.account_service = BilibiliAccountService(db)
    
    def create_upload_record(self, project_id: UUID, upload_data: UploadRequest) -> UploadRecord:
        """创建投稿记录"""
        # 验证账号
        account = self.account_service.get_account(upload_data.account_id)
        if not account:
            raise ValueError("账号不存在")
        
        # 创建投稿记录
        record = UploadRecord(
            project_id=project_id,
            account_id=upload_data.account_id,
            clip_id=",".join(upload_data.clip_ids),  # 暂存为逗号分隔
            title=upload_data.title,
            description=upload_data.description,
            tags=json.dumps(upload_data.tags),
            partition_id=upload_data.partition_id,
            status="pending"
        )
        
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        
        logger.info(f"投稿记录创建成功: {record.id}")
        return record
    
    async def upload_clip(self, record_id: int, video_path: str, max_retries: int = 3) -> bool:
        """上传单个切片 - 使用新的v6.0实现"""
        from .bilibili_upload_v6 import BilibiliUploadServiceV6
        
        # 使用新的上传服务
        upload_service_v6 = BilibiliUploadServiceV6(self.db)
        return await upload_service_v6.upload_clip(record_id, video_path, max_retries)
    
    def update_upload_status(self, record_id, status: str, error_message: str = None) -> bool:
        """更新投稿状态"""
        try:
            record = self.db.query(UploadRecord).filter(UploadRecord.id == record_id).first()
            if not record:
                return False
            
            record.status = status
            if error_message:
                record.error_message = error_message
            record.updated_at = datetime.utcnow()
            
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"更新投稿状态失败: {str(e)}")
            self.db.rollback()
            return False

    def retry_upload_task(self, record_id: int) -> bool:
        """重试失败的投稿任务"""
        try:
            record = self.db.query(UploadRecord).filter(UploadRecord.id == record_id).first()
            if not record:
                raise ValueError("投稿记录不存在")
            
            if record.status != "failed":
                raise ValueError("只有失败的任务可以重试")
            
            # 重置状态为待处理
            record.status = "pending"
            record.error_message = None
            record.updated_at = datetime.utcnow()
            self.db.commit()
            
            # 重新启动上传任务
            clip_ids = record.clip_id.split(",") if record.clip_id else []
            for clip_id in clip_ids:
                clip_id = clip_id.strip()
                if clip_id:
                    from ..tasks.upload import upload_clip_task
                    upload_clip_task.delay(str(record.id), clip_id)
            
            logger.info(f"投稿任务重试已启动: {record_id}")
            return True
            
        except Exception as e:
            logger.error(f"重试投稿任务失败: {str(e)}")
            self.db.rollback()
            return False

    def cancel_upload_task(self, record_id: int) -> bool:
        """取消进行中的投稿任务"""
        try:
            record = self.db.query(UploadRecord).filter(UploadRecord.id == record_id).first()
            if not record:
                raise ValueError("投稿记录不存在")
            
            if record.status not in ["pending", "processing"]:
                raise ValueError("只有待处理或处理中的任务可以取消")
            
            # 更新状态为已取消
            record.status = "cancelled"
            record.updated_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"投稿任务已取消: {record_id}")
            return True
            
        except Exception as e:
            logger.error(f"取消投稿任务失败: {str(e)}")
            self.db.rollback()
            return False
    
    def delete_upload_task(self, record_id: int) -> bool:
        """删除投稿任务"""
        try:
            record = self.db.query(UploadRecord).filter(UploadRecord.id == record_id).first()
            if not record:
                raise ValueError("投稿记录不存在")
            
            # 只有已完成、失败或取消的任务可以删除
            if record.status in ["pending", "processing"]:
                raise ValueError("进行中的任务不能删除，请先取消")
            
            # 删除记录
            self.db.delete(record)
            self.db.commit()
            
            logger.info(f"投稿任务已删除: {record_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除投稿任务失败: {str(e)}")
            self.db.rollback()
            return False
    
    def get_upload_records(self, project_id: Optional[UUID] = None) -> List[dict]:
        """获取投稿记录，包含关联信息"""
        from ..models.project import Project
        
        query = self.db.query(
            UploadRecord,
            BilibiliAccount.username.label('account_username'),
            BilibiliAccount.nickname.label('account_nickname'),
            Project.name.label('project_name')
        ).join(
            BilibiliAccount, UploadRecord.account_id == BilibiliAccount.id
        ).outerjoin(
            Project, UploadRecord.project_id == Project.id
        )
        
        if project_id:
            query = query.filter(UploadRecord.project_id == project_id)
        
        results = query.order_by(UploadRecord.created_at.desc()).all()
        
        # 转换为字典格式，包含关联信息
        records = []
        for record, account_username, account_nickname, project_name in results:
            record_dict = {
                'id': record.id,
                'task_id': record.task_id,
                'project_id': record.project_id,
                'account_id': record.account_id,
                'clip_id': record.clip_id,
                'title': record.title,
                'description': record.description,
                'tags': record.tags,
                'partition_id': record.partition_id,
                'video_path': record.video_path,
                'bv_id': record.bv_id,
                'av_id': record.av_id,
                'status': record.status,
                'error_message': record.error_message,
                'progress': record.progress or 0,
                'file_size': record.file_size,
                'upload_duration': record.upload_duration,
                'created_at': record.created_at,
                'updated_at': record.updated_at,
                'account_username': account_username,
                'account_nickname': account_nickname,
                'project_name': project_name
            }
            records.append(record_dict)
        
        return records
    
    def get_upload_record(self, record_id: UUID) -> Optional[UploadRecord]:
        """获取指定投稿记录"""
        return self.db.query(UploadRecord).filter(UploadRecord.id == record_id).first()
    
    def get_upload_record_by_id(self, record_id: int) -> Optional[UploadRecord]:
        """根据整数ID获取指定投稿记录"""
        return self.db.query(UploadRecord).filter(UploadRecord.id == record_id).first()
    
    def upload_clip_sync(self, record_id: int, video_path: str, max_retries: int = 3) -> bool:
        """同步版本的上传单个切片"""
        from .bilibili_upload_v2 import BilibiliUploadServiceV2
        
        # 使用新的上传服务
        upload_service_v2 = BilibiliUploadServiceV2(self.db)
        return upload_service_v2.upload_clip_sync(record_id, video_path, max_retries)


class BilibiliDirectUploader:
    """B站直接API上传器"""
    
    def __init__(self, cookies: str):
        self.cookies = cookies
        self.bv_id = None
        self.error_message = None
        self.session = None
    
    async def upload_video(self, video_path: str, metadata: dict, max_retries: int = 3) -> bool:
        """上传视频 - 简化版本，暂时返回失败状态"""
        try:
            # 暂时返回失败，因为需要重新实现上传逻辑
            self.error_message = "上传功能正在开发中，请稍后再试"
            logger.warning("上传功能暂未实现，返回失败状态")
            return False
                
        except Exception as e:
            self.error_message = str(e)
            logger.error(f"上传视频失败: {e}")
            return False
    
    async def _pre_upload(self, video_path: str) -> Optional[str]:
        """预上传，获取upload_id"""
        try:
            file_size = os.path.getsize(video_path)
            file_name = os.path.basename(video_path)
            
            headers = {
                "Cookie": self.cookies,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://member.bilibili.com/"
            }
            
            data = {
                "name": file_name,
                "size": str(file_size)
            }
            
            async with self.session.post(
                "https://member.bilibili.com/x/vu/web/add",
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                result = await response.json()
                
                if result.get("code") == 0:
                    upload_id = result.get("data", {}).get("id")
                    logger.info(f"预上传成功，upload_id: {upload_id}")
                    return upload_id
                else:
                    self.error_message = f"预上传失败: {result.get('message', '未知错误')}"
                    logger.error(self.error_message)
                    return None
                    
        except Exception as e:
            self.error_message = f"预上传异常: {str(e)}"
            logger.error(self.error_message)
            return None
    
    async def _chunk_upload(self, video_path: str, upload_id: str, max_retries: int = 3) -> bool:
        """分片上传"""
        try:
            chunk_size = 2 * 1024 * 1024  # 2MB per chunk
            file_size = os.path.getsize(video_path)
            
            headers = {
                "Cookie": self.cookies,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://member.bilibili.com/"
            }
            
            with open(video_path, 'rb') as f:
                chunk_index = 0
                while True:
                    chunk_data = f.read(chunk_size)
                    if not chunk_data:
                        break
                    
                    # 重试逻辑
                    for attempt in range(max_retries):
                        try:
                            form_data = aiohttp.FormData()
                            form_data.add_field('chunk', chunk_data, filename=f'chunk_{chunk_index}')
                            form_data.add_field('id', upload_id)
                            form_data.add_field('chunk_index', str(chunk_index))
                            
                            async with self.session.post(
                                "https://member.bilibili.com/x/vu/web/upload",
                                headers=headers,
                                data=form_data,
                                timeout=aiohttp.ClientTimeout(total=60)
                            ) as response:
                                result = await response.json()
                                
                                if result.get("code") == 0:
                                    logger.info(f"分片 {chunk_index} 上传成功")
                                    break
                                else:
                                    if attempt == max_retries - 1:
                                        self.error_message = f"分片 {chunk_index} 上传失败: {result.get('message', '未知错误')}"
                                        logger.error(self.error_message)
                                        return False
                                    else:
                                        await asyncio.sleep(2 ** attempt)
                                        
                        except Exception as e:
                            if attempt == max_retries - 1:
                                self.error_message = f"分片 {chunk_index} 上传异常: {str(e)}"
                                logger.error(self.error_message)
                                return False
                            else:
                                await asyncio.sleep(2 ** attempt)
                    
                    chunk_index += 1
            
            logger.info(f"所有分片上传完成，共 {chunk_index} 个分片")
            return True
            
        except Exception as e:
            self.error_message = f"分片上传异常: {str(e)}"
            logger.error(self.error_message)
            return False
    
    async def _merge_chunks(self, upload_id: str) -> bool:
        """合并分片"""
        try:
            headers = {
                "Cookie": self.cookies,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://member.bilibili.com/"
            }
            
            data = {
                "id": upload_id
            }
            
            async with self.session.post(
                "https://member.bilibili.com/x/vu/web/merge",
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                result = await response.json()
                
                if result.get("code") == 0:
                    logger.info("分片合并成功")
                    return True
                else:
                    self.error_message = f"分片合并失败: {result.get('message', '未知错误')}"
                    logger.error(self.error_message)
                    return False
                    
        except Exception as e:
            self.error_message = f"分片合并异常: {str(e)}"
            logger.error(self.error_message)
            return False
    
    async def _submit_video(self, upload_id: str, metadata: dict) -> bool:
        """提交投稿"""
        try:
            headers = {
                "Cookie": self.cookies,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://member.bilibili.com/",
                "Content-Type": "application/json"
            }
            
            # 构建投稿数据
            submit_data = {
                "copyright": 1,  # 自制
                "videos": [{
                    "filename": upload_id,
                    "title": metadata.get('title', ''),
                    "desc": metadata.get('description', '')
                }],
                "source": "",
                "tid": metadata.get('partition_id', 17),
                "cover": "",
                "title": metadata.get('title', ''),
                "tag": ",".join(metadata.get('tags', [])),
                "desc_format_id": 0,
                "desc": metadata.get('description', ''),
                "dynamic": "",
                "subtitle": {
                    "open": 0,
                    "lan": ""
                },
                "open_elec": 0,
                "no_reprint": 0,
                "up_selection_reply": False,
                "up_close_reply": False,
                "up_close_danmu": False
            }
            
            async with self.session.post(
                "https://member.bilibili.com/x/vu/web/add",
                headers=headers,
                json=submit_data,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                result = await response.json()
                
                if result.get("code") == 0:
                    self.bv_id = result.get("data", {}).get("bvid")
                    logger.info(f"投稿提交成功，BV号: {self.bv_id}")
                    return True
                else:
                    self.error_message = f"投稿提交失败: {result.get('message', '未知错误')}"
                    logger.error(self.error_message)
                    return False
                    
        except Exception as e:
            self.error_message = f"投稿提交异常: {str(e)}"
            logger.error(self.error_message)
            return False
    
    def get_bv_id(self) -> Optional[str]:
        """获取BV号"""
        return self.bv_id
    
    def get_error_message(self) -> Optional[str]:
        """获取错误信息"""
        return self.error_message
