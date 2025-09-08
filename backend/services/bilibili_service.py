"""
B站服务类
集成bilitool功能，处理账号管理和投稿
"""

import logging
import json
import os
import subprocess
import tempfile
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import datetime

# bilitool导入
from bilitool import LoginController, UploadController

from ..models.bilibili import BilibiliAccount, UploadRecord
from ..schemas.bilibili import BilibiliAccountCreate, UploadRequest
from ..utils.crypto import encrypt_data, decrypt_data

logger = logging.getLogger(__name__)


class BilibiliAccountService:
    """B站账号服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.login_controller = LoginController()
    
    def create_account(self, account_data: BilibiliAccountCreate) -> BilibiliAccount:
        """创建B站账号"""
        try:
            # 从cookie文件内容创建账号
            cookies_data = json.loads(account_data.cookie_content)
            
            # 验证登录是否成功
            if cookies_data.get('code') != 0:
                raise ValueError(f"登录失败: {cookies_data.get('message', '未知错误')}")
            
            # 加密存储cookies
            encrypted_cookies = encrypt_data(json.dumps(cookies_data))
            
            # 从cookie数据中获取用户信息
            user_data = cookies_data.get('data', {})
            user_mid = user_data.get('mid', '')
            
            # 创建账号记录
            account = BilibiliAccount(
                username=f"user_{user_mid}" if user_mid else account_data.username,
                nickname=account_data.nickname or f"B站用户_{user_mid if user_mid else '未知'}",
                cookies=encrypted_cookies,
                status="active"
            )
            
            self.db.add(account)
            self.db.commit()
            self.db.refresh(account)
            
            logger.info(f"B站账号创建成功: {account.username}")
            return account
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"创建B站账号失败: {str(e)}")
            raise
    
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
                cookies_data = json.loads(cookies_data_str)
            except Exception as e:
                logger.warning(f"解密cookies失败，尝试使用未加密数据: {str(e)}")
                # 尝试使用未加密的cookies（向后兼容）
                if account.cookies and account.cookies.startswith('{'):
                    try:
                        cookies_data = json.loads(account.cookies)
                        logger.info("使用未加密的cookies数据")
                    except json.JSONDecodeError:
                        logger.error("cookies数据格式无效")
                        return False
                else:
                    logger.error("cookies数据无效")
                    return False
            
            # 验证cookie数据格式
            if cookies_data.get('code') != 0:
                return False
            
            # 检查是否有必要的cookie字段
            cookie_info = cookies_data.get('data', {}).get('cookie_info', {})
            if not cookie_info.get('cookies'):
                return False
            
            return True
                    
        except Exception as e:
            logger.error(f"检查账号状态失败: {str(e)}")
            return False


class BilibiliUploadService:
    """B站投稿服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.upload_controller = UploadController()
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
    
    def upload_clip(self, record_id: UUID, video_path: str) -> bool:
        """上传单个切片"""
        record = None
        try:
            record = self.db.query(UploadRecord).filter(UploadRecord.id == record_id).first()
            if not record:
                raise ValueError("投稿记录不存在")
            
            # 更新状态为处理中
            record.status = "processing"
            self.db.commit()
            
            # 获取账号cookies
            account = self.account_service.get_account(record.account_id)
            if not account:
                raise ValueError("账号不存在")
            
            try:
                cookies_data_str = decrypt_data(account.cookies)
                cookies_data = json.loads(cookies_data_str)
            except Exception as e:
                logger.error(f"解密账号cookies失败: {str(e)}")
                # 尝试使用未加密的cookies（向后兼容）
                if account.cookies and account.cookies.startswith('{'):
                    try:
                        cookies_data = json.loads(account.cookies)
                        logger.info("使用未加密的cookies数据")
                    except json.JSONDecodeError:
                        raise ValueError("账号cookies数据格式无效，请重新登录")
                else:
                    raise ValueError("账号cookies数据无效，请重新登录")
            
            # 创建临时cookie文件
            temp_cookie_path = f"temp_cookie_{record.id}.json"
            
            try:
                # 写入cookie内容
                with open(temp_cookie_path, 'w') as f:
                    json.dump(cookies_data, f)
                
                # 解析标签
                tags = json.loads(record.tags) if record.tags else []
                tags_str = ",".join(tags)
                
                # 使用bilitool CLI上传视频
                result = subprocess.run([
                    'bilitool', 'upload',
                    '-f', temp_cookie_path,
                    '--title', record.title,
                    '--desc', record.description,
                    '--tag', tags_str,
                    '--tid', str(record.partition_id),
                    video_path
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    # 解析输出获取BV号
                    upload_result = {"bvid": "BV1234567890"}  # 临时占位，实际需要解析result.stdout
                else:
                    upload_result = None
                    
            finally:
                # 清理临时文件
                if os.path.exists(temp_cookie_path):
                    os.unlink(temp_cookie_path)
            
            if upload_result and "bvid" in upload_result:
                # 投稿成功
                record.bvid = upload_result["bvid"]
                record.status = "success"
                record.updated_at = datetime.utcnow()
                self.db.commit()
                
                logger.info(f"视频投稿成功: {record.bvid}")
                return True
            else:
                # 投稿失败
                record.status = "failed"
                record.error_message = "上传失败，未获取到BV号"
                record.updated_at = datetime.utcnow()
                self.db.commit()
                
                logger.error(f"视频投稿失败: {record.error_message}")
                return False
                
        except Exception as e:
            # 更新失败状态
            if record:
                record.status = "failed"
                record.error_message = str(e)
                record.updated_at = datetime.utcnow()
                self.db.commit()
            
            logger.error(f"投稿过程出错: {str(e)}")
            return False
    
    def update_upload_status(self, record_id: UUID, status: str, error_message: str = None) -> bool:
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

    def retry_upload_task(self, record_id: UUID) -> bool:
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

    def cancel_upload_task(self, record_id: UUID) -> bool:
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
            
            # 这里可以添加取消Celery任务的逻辑
            # 例如：revoke_task(record.celery_task_id)
            
            logger.info(f"投稿任务已取消: {record_id}")
            return True
            
        except Exception as e:
            logger.error(f"取消投稿任务失败: {str(e)}")
            self.db.rollback()
            return False
    
    def get_upload_records(self, project_id: Optional[UUID] = None) -> List[UploadRecord]:
        """获取投稿记录"""
        query = self.db.query(UploadRecord)
        if project_id:
            query = query.filter(UploadRecord.project_id == project_id)
        return query.order_by(UploadRecord.created_at.desc()).all()
    
    def get_upload_record(self, record_id: UUID) -> Optional[UploadRecord]:
        """获取指定投稿记录"""
        return self.db.query(UploadRecord).filter(UploadRecord.id == record_id).first()
