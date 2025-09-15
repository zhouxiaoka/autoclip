"""
B站投稿上传服务 v2.0
基于 biliup-rs 项目的实现思路重新开发
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

logger = logging.getLogger(__name__)

class BilibiliUploaderV2:
    """B站投稿上传器 v2.0"""
    
    def __init__(self, cookies: str):
        self.cookies = cookies
        self.session = None
        self.upload_id = None
        self.bv_id = None
        self.error_message = None
        
        # 上传线路配置 (基于 biliup-rs)
        self.upload_lines = {
            'bda2': 'https://upos-sz-upcdnbda2.bilivideo.com/upgcxcode/',
            'qn': 'https://upos-sz-upcdnqn.bilivideo.com/upgcxcode/',
            'alia': 'https://upos-sz-upcdn-ali.bilivideo.com/upgcxcode/',
            'bldsa': 'https://upos-sz-upcdnbldsa.bilivideo.com/upgcxcode/',
            'tx': 'https://upos-sz-upcdntx.bilivideo.com/upgcxcode/',
            'txa': 'https://upos-sz-upcdntxa.bilivideo.com/upgcxcode/',
            'bda': 'https://upos-sz-upcdnbda.bilivideo.com/upgcxcode/',
        }
        
        # 默认上传线路
        self.default_line = 'bda2'
        
    async def upload_video(self, video_path: str, metadata: dict, max_retries: int = 3) -> bool:
        """上传视频主流程 - 真实B站上传实现"""
        try:
            async with aiohttp.ClientSession() as session:
                self.session = session
                
                # 1. 验证登录状态
                if not await self._check_login_status():
                    return False
                
                # 2. 获取预上传信息
                pre_upload_info = await self._get_pre_upload_info(video_path)
                if not pre_upload_info:
                    return False
                
                # 3. 选择最佳上传线路
                best_line = await self._select_best_upload_line()
                if not best_line:
                    best_line = self.default_line
                
                logger.info(f"选择上传线路: {best_line}")
                
                # 4. 分片上传
                success = await self._chunk_upload_real(video_path, pre_upload_info, best_line, max_retries)
                if not success:
                    return False
                
                # 5. 合并分片
                success = await self._merge_chunks_real(pre_upload_info, best_line)
                if not success:
                    return False
                
                # 6. 提交投稿
                success = await self._submit_video_real(pre_upload_info, metadata)
                if not success:
                    return False
                
                return True
                
        except Exception as e:
            self.error_message = str(e)
            logger.error(f"上传视频失败: {e}")
            return False
    
    async def _check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            headers = {
                "Cookie": self.cookies,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.bilibili.com/"
            }
            
            async with self.session.get(
                "https://api.bilibili.com/x/web-interface/nav",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == 0 and data.get("data", {}).get("isLogin"):
                        user_info = data["data"]
                        logger.info(f"登录状态正常，用户: {user_info.get('uname')}")
                        return True
                    else:
                        self.error_message = f"登录状态异常: {data.get('message', '未知错误')}"
                        logger.error(self.error_message)
                        return False
                else:
                    self.error_message = f"检查登录状态失败: HTTP {response.status}"
                    logger.error(self.error_message)
                    return False
                    
        except Exception as e:
            self.error_message = f"检查登录状态异常: {str(e)}"
            logger.error(self.error_message)
            return False
    
    async def _get_pre_upload_info(self, video_path: str) -> Optional[dict]:
        """获取预上传信息 - 基于biliup-rs的真实实现"""
        try:
            file_size = os.path.getsize(video_path)
            file_name = os.path.basename(video_path)
            
            # 解析Cookie获取CSRF token
            csrf_token = None
            for cookie in self.cookies.split(';'):
                cookie = cookie.strip()
                if cookie.startswith('bili_jct='):
                    csrf_token = cookie.split('=', 1)[1]
                    break
            
            if not csrf_token:
                self.error_message = "Cookie中缺少bili_jct字段"
                logger.error(self.error_message)
                return None
            
            headers = {
                "Cookie": self.cookies,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://member.bilibili.com/",
                "Origin": "https://member.bilibili.com"
            }
            
            # 使用正确的B站预上传API
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
                        # B站的预上传信息直接在result中，不在data字段
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
                    self.error_message = f"预上传请求失败: HTTP {response.status}"
                    logger.error(self.error_message)
                    return None
                    
        except Exception as e:
            self.error_message = f"预上传异常: {str(e)}"
            logger.error(self.error_message)
            return None
    
    async def _select_best_upload_line(self) -> Optional[str]:
        """选择最佳上传线路"""
        try:
            # 测试各线路的响应时间
            line_times = {}
            
            for line_name, line_url in self.upload_lines.items():
                try:
                    start_time = time.time()
                    async with self.session.get(
                        f"{line_url}ping",
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        if response.status == 200:
                            response_time = time.time() - start_time
                            line_times[line_name] = response_time
                            logger.debug(f"线路 {line_name} 响应时间: {response_time:.3f}s")
                except Exception as e:
                    logger.debug(f"线路 {line_name} 测试失败: {e}")
                    continue
            
            if line_times:
                # 选择响应时间最短的线路
                best_line = min(line_times, key=line_times.get)
                logger.info(f"最佳线路: {best_line} (响应时间: {line_times[best_line]:.3f}s)")
                return best_line
            else:
                logger.warning("所有线路测试失败，使用默认线路")
                return self.default_line
                
        except Exception as e:
            logger.error(f"选择上传线路失败: {e}")
            return self.default_line
    
    async def _chunk_upload_real(self, video_path: str, upload_info: dict, line: str, max_retries: int = 3) -> bool:
        """真实分片上传 - 基于biliup-rs实现"""
        try:
            upload_id = upload_info.get("upload_id")
            if not upload_id:
                self.error_message = "预上传信息中缺少upload_id"
                logger.error(self.error_message)
                return False
            
            chunk_size = 2 * 1024 * 1024  # 2MB per chunk
            file_size = os.path.getsize(video_path)
            total_chunks = (file_size + chunk_size - 1) // chunk_size
            
            logger.info(f"开始分片上传，文件大小: {file_size}, 分片数: {total_chunks}")
            
            # 获取上传URL和认证信息
            endpoint = upload_info.get("endpoint", "//upos-cs-upcdnbda2.bilivideo.com")
            auth = upload_info.get("auth", "")
            upos_uri = upload_info.get("upos_uri", "")
            put_query = upload_info.get("put_query", "")
            
            # 处理多个endpoint，选择第一个
            if "," in endpoint:
                endpoint = endpoint.split(",")[0]
            
            # 确保endpoint包含完整的域名
            if not endpoint.endswith('.bilivideo.com'):
                endpoint = endpoint.replace('//upos-cs-upcdnbda2', '//upos-cs-upcdnbda2.bilivideo.com')
            
            # 构建上传URL - 处理upos_uri格式
            if upos_uri.startswith("upos://"):
                # 移除upos://前缀，只保留路径部分
                upos_path = upos_uri[7:]  # 移除"upos://"
            else:
                upos_path = upos_uri
            
            # 构建基础URL
            upload_url = f"https:{endpoint}/{upos_path}"
            
            # 只使用auth参数，避免重复
            if auth:
                upload_url += "?" + auth
            
            logger.info(f"构建的上传URL: {upload_url}")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://member.bilibili.com/",
                "Origin": "https://member.bilibili.com",
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "cross-site"
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
                            # 构建分片上传URL - 使用partNumber参数
                            separator = "&" if "?" in upload_url else "?"
                            chunk_url = f"{upload_url}{separator}partNumber={chunk_index + 1}"
                            
                            logger.debug(f"分片 {chunk_index + 1} 上传URL: {chunk_url}")
                            
                            # 使用PUT方法直接上传二进制数据
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
                                        await asyncio.sleep(1)
                                        continue
                                    else:
                                        self.error_message = f"分片 {chunk_index + 1} 上传失败: HTTP {response.status}"
                                        logger.error(self.error_message)
                                        return False
                        except Exception as e:
                            if attempt < max_retries - 1:
                                logger.warning(f"分片 {chunk_index + 1} 上传异常，重试 {attempt + 1}/{max_retries}: {e}")
                                await asyncio.sleep(1)
                                continue
                            else:
                                self.error_message = f"分片 {chunk_index + 1} 上传异常: {str(e)}"
                                logger.error(self.error_message)
                                return False
                    else:
                        # 所有重试都失败了
                        return False
            
            logger.info("所有分片上传完成")
            return True
            
        except Exception as e:
            self.error_message = f"分片上传异常: {str(e)}"
            logger.error(self.error_message)
            return False
    
    async def _merge_chunks_real(self, upload_info: dict, line: str) -> bool:
        """真实合并分片 - 基于biliup-rs实现"""
        try:
            upload_id = upload_info.get("upload_id")
            if not upload_id:
                self.error_message = "预上传信息中缺少upload_id"
                logger.error(self.error_message)
                return False
            
            # 解析Cookie获取CSRF token
            csrf_token = None
            for cookie in self.cookies.split(';'):
                cookie = cookie.strip()
                if cookie.startswith('bili_jct='):
                    csrf_token = cookie.split('=', 1)[1]
                    break
            
            if not csrf_token:
                self.error_message = "Cookie中缺少bili_jct字段"
                logger.error(self.error_message)
                return False
            
            headers = {
                "Cookie": self.cookies,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://member.bilibili.com/",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # 使用B站的合并API
            data = {
                "biz_id": upload_id,
                "csrf": csrf_token
            }
            
            async with self.session.post(
                "https://member.bilibili.com/x/vu/web/complete",
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 0:
                        logger.info("分片合并成功")
                        return True
                    else:
                        self.error_message = f"分片合并失败: {result.get('message', '未知错误')}"
                        logger.error(self.error_message)
                        return False
                else:
                    self.error_message = f"分片合并请求失败: HTTP {response.status}"
                    logger.error(self.error_message)
                    return False
                    
        except Exception as e:
            self.error_message = f"分片合并异常: {str(e)}"
            logger.error(self.error_message)
            return False
    
    async def _submit_video_real(self, upload_info: dict, metadata: dict) -> bool:
        """真实提交投稿 - 基于biliup-rs实现"""
        try:
            upload_id = upload_info.get("upload_id")
            if not upload_id:
                self.error_message = "预上传信息中缺少upload_id"
                logger.error(self.error_message)
                return False
            
            # 解析Cookie获取CSRF token
            csrf_token = None
            for cookie in self.cookies.split(';'):
                cookie = cookie.strip()
                if cookie.startswith('bili_jct='):
                    csrf_token = cookie.split('=', 1)[1]
                    break
            
            if not csrf_token:
                self.error_message = "Cookie中缺少bili_jct字段"
                logger.error(self.error_message)
                return False
            
            headers = {
                "Cookie": self.cookies,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://member.bilibili.com/",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # 构建投稿数据 - 使用B站的真实API格式
            submit_data = {
                "copyright": "1",  # 1-自制 2-转载
                "videos": json.dumps([{
                    "filename": upload_info.get("upos_uri", "").split("/")[-1],  # 使用upos_uri中的文件名
                    "title": metadata.get('title', '')[:80],
                    "desc": metadata.get('description', '')[:2000]
                }]),
                "source": "",
                "tid": str(metadata.get('partition_id', 171)),
                "cover": "",
                "title": metadata.get('title', '')[:80],
                "tag": ",".join(metadata.get('tags', [])),
                "desc_format_id": "0",
                "desc": metadata.get('description', '')[:2000],
                "dynamic": "",
                "subtitle": json.dumps({
                    "open": 0,
                    "lan": ""
                }),
                "open_elec": "0",
                "no_reprint": "0",
                "up_selection_reply": "false",
                "up_close_reply": "false",
                "up_close_danmu": "false",
                "csrf": csrf_token
            }
            
            async with self.session.post(
                "https://member.bilibili.com/x/vu/web/add",
                headers=headers,
                data=submit_data,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 0:
                        bv_id = result.get("data", {}).get("bvid")
                        if bv_id:
                            self.bv_id = bv_id
                            logger.info(f"投稿提交成功，BV号: {bv_id}")
                            return True
                        else:
                            self.error_message = "投稿提交成功但未返回BV号"
                            logger.error(self.error_message)
                            return False
                    else:
                        self.error_message = f"投稿提交失败: {result.get('message', '未知错误')}"
                        logger.error(self.error_message)
                        return False
                else:
                    self.error_message = f"投稿提交请求失败: HTTP {response.status}"
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


class BilibiliUploadServiceV2:
    """B站投稿服务 v2.0"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.account_service = None  # 需要注入账号服务
    
    async def upload_clip(self, record_id: int, video_path: str, max_retries: int = 3) -> bool:
        """上传单个切片"""
        record = None
        try:
            record = self.db.query(BilibiliUploadRecord).filter(BilibiliUploadRecord.id == record_id).first()
            if not record:
                raise ValueError("投稿记录不存在")
            
            # 验证视频文件
            if not os.path.exists(video_path):
                raise ValueError(f"视频文件不存在: {video_path}")
            
            # 检查文件大小（B站限制）
            file_size = os.path.getsize(video_path)
            max_size = 8 * 1024 * 1024 * 1024  # 8GB
            if file_size > max_size:
                raise ValueError(f"视频文件过大: {file_size / (1024**3):.2f}GB，超过8GB限制")
            
            # 更新状态为处理中
            record.status = "processing"
            record.file_size = file_size
            self.db.commit()
            
            # 获取账号cookies
            account = self.db.query(BilibiliAccount).filter(BilibiliAccount.id == record.account_id).first()
            if not account:
                raise ValueError("账号不存在")
            
            # 检查账号状态
            if account.status != "active":
                raise ValueError(f"账号状态异常: {account.status}，请先检查账号健康状态")
            
            # 解密cookies
            try:
                cookies_str = decrypt_data(account.cookies)
            except Exception as e:
                logger.error(f"解密账号cookies失败: {str(e)}")
                raise ValueError("账号cookies数据无效，请重新登录")
            
            # 使用新的上传服务
            uploader = BilibiliUploaderV2(cookies_str)
            
            # 准备上传元数据
            metadata = {
                'title': record.title[:80] if record.title else "",
                'description': record.description[:2000] if record.description else "",
                'tags': json.loads(record.tags) if record.tags else [],
                'partition_id': record.partition_id
            }
            
            # 执行上传
            start_time = time.time()
            success = await uploader.upload_video(video_path, metadata, max_retries)
            upload_duration = int(time.time() - start_time)
            
            if success:
                record.status = "success"
                record.bv_id = uploader.get_bv_id()
                record.upload_duration = upload_duration
                record.progress = 100
                record.updated_at = datetime.utcnow()
                self.db.commit()
                
                logger.info(f"视频投稿成功: {record.bv_id}")
                return True
            else:
                record.status = "failed"
                record.error_message = uploader.get_error_message()
                record.upload_duration = upload_duration
                record.updated_at = datetime.utcnow()
                self.db.commit()
                
                logger.error(f"视频投稿失败: {uploader.get_error_message()}")
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
    
    def upload_clip_sync(self, record_id: int, video_path: str, max_retries: int = 3) -> bool:
        """同步版本的上传单个切片"""
        import asyncio
        try:
            # 在同步上下文中运行异步方法
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self.upload_clip(record_id, video_path, max_retries))
                logger.info(f"同步上传完成，结果: {result}")
                return result
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"同步上传失败: {str(e)}")
            return False
