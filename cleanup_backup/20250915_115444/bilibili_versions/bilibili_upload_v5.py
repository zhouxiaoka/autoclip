"""
B站投稿上传服务 v5.0
基于官方 bilibili-api 库的正确实现
"""

import asyncio
import aiohttp
import json
import os
import time
import hashlib
import random
import string
from typing import Optional, Dict, List, Tuple
from pathlib import Path
from datetime import datetime
import logging

from ..core.database import SessionLocal
from ..models.bilibili import BilibiliAccount, BilibiliUploadRecord
from ..utils.crypto import decrypt_data
import uuid

# 导入官方bilibili-api库
from bilibili_api import Credential, user

logger = logging.getLogger(__name__)

class BilibiliUploaderV5:
    """B站投稿上传器 v5.0 - 基于官方bilibili-api库"""
    
    def __init__(self, cookies: str):
        self.cookies = cookies
        self.session = None
        self.upload_id = None
        self.bv_id = None
        self.error_message = None
        self.credential = None
        
    def _create_credential(self) -> Optional[Credential]:
        """创建Credential对象"""
        try:
            # 解析Cookie
            cookie_dict = {}
            for cookie in self.cookies.split(';'):
                if '=' in cookie:
                    key, value = cookie.split('=', 1)
                    cookie_dict[key.strip()] = value.strip()
            
            # 提取关键字段
            sessdata = cookie_dict.get('SESSDATA', '')
            bili_jct = cookie_dict.get('bili_jct', '')
            buvid3 = cookie_dict.get('buvid3', '')
            dede_user_id = cookie_dict.get('DedeUserID', '')
            
            if not all([sessdata, bili_jct, buvid3, dede_user_id]):
                self.error_message = "Cookie中缺少必要的认证字段"
                return None
            
            # 创建Credential对象
            credential = Credential(
                sessdata=sessdata,
                bili_jct=bili_jct,
                buvid3=buvid3,
                dedeuserid=dede_user_id
            )
            
            return credential
            
        except Exception as e:
            self.error_message = f"创建Credential对象失败: {str(e)}"
            return None
    
    async def upload_video(self, video_path: str, metadata: dict, max_retries: int = 3) -> bool:
        """上传视频主流程 - 基于官方bilibili-api库"""
        try:
            # 创建Credential对象
            self.credential = self._create_credential()
            if not self.credential:
                return False
            
            async with aiohttp.ClientSession() as session:
                self.session = session
                
                # 1. 验证登录状态
                if not await self._check_login_status():
                    return False
                
                # 2. 获取预上传信息
                pre_upload_info = await self._get_pre_upload_info(video_path)
                if not pre_upload_info:
                    return False
                
                # 3. 分片上传 - 使用正确的实现
                success = await self._chunk_upload_correct(video_path, pre_upload_info, max_retries)
                if not success:
                    return False
                
                # 4. 合并分片
                success = await self._merge_chunks_correct(pre_upload_info)
                if not success:
                    return False
                
                # 5. 提交投稿
                success = await self._submit_video_correct(pre_upload_info, metadata)
                if not success:
                    return False
                
                return True
                
        except Exception as e:
            self.error_message = str(e)
            logger.error(f"上传视频失败: {e}")
            return False
    
    async def _check_login_status(self) -> bool:
        """检查登录状态 - 使用官方bilibili-api库"""
        try:
            # 使用官方库检查登录状态
            u = user.User(uid=int(self.credential.dedeuserid), credential=self.credential)
            user_info = await u.get_user_info()
            
            if user_info and user_info.get('mid'):
                logger.info(f"登录状态正常，用户: {user_info.get('name', 'unknown')}")
                return True
            else:
                self.error_message = "用户未登录或登录状态异常"
                logger.error(self.error_message)
                return False
                
        except Exception as e:
            self.error_message = f"检查登录状态异常: {str(e)}"
            logger.error(self.error_message)
            return False
    
    async def _get_pre_upload_info(self, video_path: str) -> Optional[dict]:
        """获取预上传信息 - 使用正确的实现"""
        try:
            file_size = os.path.getsize(video_path)
            file_name = os.path.basename(video_path)
            
            headers = {
                "Cookie": self.cookies,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://member.bilibili.com/",
                "Origin": "https://member.bilibili.com",
                "X-CSRF-Token": self.credential.bili_jct
            }
            
            # 使用正确的参数
            params = {
                "name": file_name,
                "size": str(file_size),
                "r": "upos",
                "profile": "ugcupos/bup",
                "ssl": "0",
                "version": "2.10.4",
                "build": "2100400",
                "upcdn": "bda2,bldsa",
                "probe_version": "20200709"
            }
            
            async with self.session.get(
                "https://member.bilibili.com/preupload",
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"预上传API响应: {result}")
                    if result.get("OK") == 1:
                        upload_info = {
                            "upload_id": result.get("biz_id"),
                            "endpoint": result.get("endpoint"),
                            "auth": result.get("auth"),
                            "chunk_size": result.get("chunk_size", 10485760),
                            "upos_uri": result.get("upos_uri"),
                            "put_query": result.get("put_query")
                        }
                        logger.info(f"预上传信息获取成功: {upload_info}")
                        return upload_info
                    else:
                        self.error_message = f"预上传失败: {result.get('message', '未知错误')}"
                        logger.error(self.error_message)
                        return None
                else:
                    self.error_message = f"预上传请求失败，HTTP状态码: {response.status}"
                    logger.error(self.error_message)
                    return None
                    
        except Exception as e:
            self.error_message = f"获取预上传信息异常: {str(e)}"
            logger.error(self.error_message)
            return None
    
    async def _chunk_upload_correct(self, video_path: str, upload_info: dict, max_retries: int = 3) -> bool:
        """分片上传 - 使用正确的实现方式"""
        try:
            file_size = os.path.getsize(video_path)
            chunk_size = 2 * 1024 * 1024  # 2MB chunks
            total_chunks = (file_size + chunk_size - 1) // chunk_size
            
            endpoint = upload_info.get("endpoint", "//upos-cs-upcdnbda2.bilivideo.com")
            auth = upload_info.get("auth", "")
            upos_uri = upload_info.get("upos_uri", "")
            
            # 处理endpoint格式
            if "," in endpoint:
                endpoint = endpoint.split(",")[0]
            if not endpoint.endswith('.bilivideo.com'):
                endpoint = endpoint.replace('//upos-cs-upcdnbda2', '//upos-cs-upcdnbda2.bilivideo.com')
            
            # 处理upos_uri格式
            if upos_uri.startswith("upos://"):
                upos_path = upos_uri[7:]
            else:
                upos_path = upos_uri
            
            # 构建上传URL
            upload_url = f"https:{endpoint}/{upos_path}"
            if auth:
                upload_url += f"?{auth}"
            
            logger.info(f"构建的上传URL: {upload_url}")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://member.bilibili.com/",
                "Origin": "https://member.bilibili.com"
            }
            
            with open(video_path, 'rb') as f:
                for chunk_index in range(total_chunks):
                    # 读取分片数据
                    chunk_data = f.read(chunk_size)
                    if not chunk_data:
                        break
                    
                    # 重试逻辑
                    for attempt in range(max_retries):
                        try:
                            # 构建分片上传URL - 使用正确的参数格式
                            chunk_url = f"{upload_url}&partNumber={chunk_index + 1}"
                            
                            logger.debug(f"分片 {chunk_index + 1} 上传URL: {chunk_url}")
                            
                            # 使用PUT方法上传分片 - 这是关键！
                            headers['Content-Type'] = 'application/octet-stream'
                            headers['Content-Length'] = str(len(chunk_data))
                            
                            async with self.session.put(
                                chunk_url,
                                headers=headers,
                                data=chunk_data,
                                timeout=aiohttp.ClientTimeout(total=60)
                            ) as response:
                                if response.status in [200, 201, 204]:
                                    logger.debug(f"分片 {chunk_index + 1}/{total_chunks} 上传成功")
                                    break
                                else:
                                    if attempt < max_retries - 1:
                                        logger.warning(f"分片 {chunk_index + 1} 上传失败，重试 {attempt + 1}/{max_retries}: HTTP {response.status}")
                                        await asyncio.sleep(2 ** attempt)  # 指数退避
                                    else:
                                        logger.error(f"分片 {chunk_index + 1} 上传失败: HTTP {response.status}")
                                        response_text = await response.text()
                                        logger.error(f"响应内容: {response_text}")
                                        return False
                                        
                        except Exception as e:
                            if attempt < max_retries - 1:
                                logger.warning(f"分片 {chunk_index + 1} 上传异常，重试 {attempt + 1}/{max_retries}: {str(e)}")
                                await asyncio.sleep(2 ** attempt)
                            else:
                                logger.error(f"分片 {chunk_index + 1} 上传异常: {str(e)}")
                                return False
            
            logger.info("所有分片上传完成")
            return True
            
        except Exception as e:
            self.error_message = f"分片上传异常: {str(e)}"
            logger.error(self.error_message)
            return False
    
    async def _merge_chunks_correct(self, upload_info: dict) -> bool:
        """合并分片 - 使用正确的实现"""
        try:
            headers = {
                "Cookie": self.cookies,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://member.bilibili.com/",
                "Origin": "https://member.bilibili.com",
                "X-CSRF-Token": self.credential.bili_jct,
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "biz_id": upload_info.get("upload_id"),
                "csrf": self.credential.bili_jct
            }
            
            async with self.session.post(
                "https://member.bilibili.com/x/vu/web/complete",
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"合并分片响应: {result}")
                    if result.get("code") == 0:
                        logger.info("分片合并成功")
                        return True
                    else:
                        self.error_message = f"合并分片失败: {result.get('message', '未知错误')}"
                        logger.error(self.error_message)
                        return False
                else:
                    self.error_message = f"合并分片请求失败，HTTP状态码: {response.status}"
                    logger.error(self.error_message)
                    return False
                    
        except Exception as e:
            self.error_message = f"合并分片异常: {str(e)}"
            logger.error(self.error_message)
            return False
    
    async def _submit_video_correct(self, upload_info: dict, metadata: dict) -> bool:
        """提交投稿 - 使用正确的实现"""
        try:
            headers = {
                "Cookie": self.cookies,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://member.bilibili.com/",
                "Origin": "https://member.bilibili.com",
                "X-CSRF-Token": self.credential.bili_jct,
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # 构建投稿数据
            upos_uri = upload_info.get("upos_uri", "")
            filename = upos_uri.split("/")[-1] if "/" in upos_uri else upos_uri
            
            data = {
                "copyright": "1",  # 原创
                "videos": json.dumps([{
                    "filename": filename,
                    "title": metadata.get("title", ""),
                    "desc": metadata.get("description", "")
                }]),
                "source": "",
                "tid": str(metadata.get("partition_id", 1)),
                "cover": "",
                "title": metadata.get("title", ""),
                "tag": ",".join(metadata.get("tags", [])),
                "desc_format_id": "0",
                "desc": metadata.get("description", ""),
                "open_elec": "1",
                "no_reprint": "0",
                "subtitles": json.dumps({
                    "lan": "",
                    "open": "0"
                }),
                "csrf": self.credential.bili_jct
            }
            
            async with self.session.post(
                "https://member.bilibili.com/x/vu/web/add",
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"提交投稿响应: {result}")
                    if result.get("code") == 0:
                        self.bv_id = result.get("data", {}).get("bvid")
                        logger.info(f"投稿提交成功，BV号: {self.bv_id}")
                        return True
                    else:
                        self.error_message = f"投稿提交失败: {result.get('message', '未知错误')}"
                        logger.error(self.error_message)
                        return False
                else:
                    self.error_message = f"投稿提交请求失败，HTTP状态码: {response.status}"
                    logger.error(self.error_message)
                    return False
                    
        except Exception as e:
            self.error_message = f"投稿提交异常: {str(e)}"
            logger.error(self.error_message)
            return False


class BilibiliUploadServiceV5:
    """B站投稿服务 v5.0"""
    
    def __init__(self, db):
        self.db = db
    
    async def upload_clip(self, record_id: int, video_path: str, max_retries: int = 3) -> bool:
        """上传单个切片"""
        try:
            # 获取投稿记录
            record = self.db.query(BilibiliUploadRecord).filter(BilibiliUploadRecord.id == record_id).first()
            if not record:
                logger.error(f"投稿记录不存在: {record_id}")
                return False
            
            # 获取账号信息
            account = self.db.query(BilibiliAccount).filter(BilibiliAccount.id == record.account_id).first()
            if not account:
                logger.error(f"账号不存在: {record.account_id}")
                return False
            
            # 解密Cookie
            try:
                cookies = decrypt_data(account.cookies)
            except Exception as e:
                logger.error(f"解密Cookie失败: {e}")
                return False
            
            # 构建投稿元数据
            metadata = {
                "title": record.title,
                "description": record.description or "",
                "tags": json.loads(record.tags) if record.tags else [],
                "partition_id": record.partition_id
            }
            
            # 使用v5.0上传器
            uploader = BilibiliUploaderV5(cookies)
            success = await uploader.upload_video(video_path, metadata, max_retries)
            
            if success:
                # 更新记录状态
                record.status = "success"
                record.bv_id = uploader.bv_id
                record.updated_at = datetime.utcnow()
                self.db.commit()
                logger.info(f"切片上传成功: {record_id}, BV号: {uploader.bv_id}")
                return True
            else:
                # 更新记录状态
                record.status = "failed"
                record.error_message = uploader.error_message
                record.updated_at = datetime.utcnow()
                self.db.commit()
                logger.error(f"切片上传失败: {record_id}, 错误: {uploader.error_message}")
                return False
                
        except Exception as e:
            logger.error(f"上传切片异常: {e}")
            return False
