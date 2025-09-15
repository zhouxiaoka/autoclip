#!/usr/bin/env python3
"""
测试真实的投稿上传功能
"""

import asyncio
import os
import sys
sys.path.append('.')

from backend.services.bilibili_upload_v2 import BilibiliUploadServiceV2
from backend.core.database import SessionLocal
from backend.models.bilibili import BilibiliAccount, BilibiliUploadRecord
from backend.utils.crypto import decrypt_data

async def test_real_upload():
    """测试真实的上传功能"""
    print("🧪 测试真实的投稿上传功能...")
    
    db = SessionLocal()
    try:
        # 获取账号
        account = db.query(BilibiliAccount).filter(BilibiliAccount.id == 1).first()
        if not account:
            print("❌ 没有找到账号")
            return False
        
        print(f"✅ 找到账号: {account.username} ({account.nickname})")
        
        # 测试Cookie解密
        try:
            cookies = decrypt_data(account.cookies)
            print(f"✅ Cookie解密成功，长度: {len(cookies)}")
        except Exception as e:
            print(f"❌ Cookie解密失败: {e}")
            return False
        
        # 创建测试投稿记录
        record = BilibiliUploadRecord(
            account_id=account.id,
            clip_id="test_clip_real_upload",
            title="测试投稿 - 真实上传功能验证",
            description="这是一个测试投稿，用于验证真实的B站上传功能。如果成功，应该能在B站创作中心看到这个视频。",
            tags='["测试", "真实上传", "功能验证"]',
            partition_id=3,  # 音乐分区
            status="pending"
        )
        
        db.add(record)
        db.commit()
        db.refresh(record)
        
        print(f"✅ 创建投稿记录成功: ID {record.id}")
        
        # 测试视频文件
        video_path = "/Users/zhoukk/autoclip/data/projects/ee47fe57-b086-44d5-b562-d57fa4334682/output/clips/5_朋友真实故事改编，《侧脸》背后的爱恨与沉默.mp4"
        
        if not os.path.exists(video_path):
            print(f"❌ 视频文件不存在: {video_path}")
            return False
        
        file_size = os.path.getsize(video_path)
        print(f"✅ 视频文件存在，大小: {file_size / (1024*1024):.2f}MB")
        
        # 创建上传服务
        upload_service = BilibiliUploadServiceV2(db)
        
        # 执行上传
        print("🚀 开始真实上传测试...")
        print("⚠️  注意：这将真正上传到B站，请确认是否继续")
        
        success = await upload_service.upload_clip(record.id, video_path, max_retries=1)
        
        if success:
            print("✅ 真实上传测试成功！")
            print("🎉 请检查B站创作中心，应该能看到新上传的视频")
            return True
        else:
            print("❌ 真实上传测试失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

async def main():
    """主函数"""
    print("🚀 开始测试真实的投稿上传功能")
    print("=" * 50)
    print("⚠️  警告：这将真正上传视频到B站！")
    print("=" * 50)
    
    # 询问用户确认
    confirm = input("确认要进行真实上传测试吗？(y/N): ")
    if confirm.lower() != 'y':
        print("❌ 用户取消测试")
        return
    
    success = await test_real_upload()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 真实上传功能测试成功！")
        print("请检查B站创作中心确认视频是否上传成功。")
    else:
        print("⚠️  真实上传功能测试失败，请检查错误信息。")

if __name__ == "__main__":
    asyncio.run(main())
