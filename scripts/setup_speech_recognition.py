#!/usr/bin/env python3
"""
语音识别环境设置脚本
自动安装 bcut-asr 和相关依赖
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.install_bcut_asr import install_dependencies, check_bcut_asr_installed, check_ffmpeg_installed
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """主函数"""
    logger.info("🎤 AutoClip 语音识别环境设置")
    logger.info("=" * 50)
    
    # 检查当前状态
    logger.info("检查当前环境状态...")
    bcut_available = check_bcut_asr_installed()
    ffmpeg_available = check_ffmpeg_installed()
    
    logger.info(f"bcut-asr 状态: {'✅ 已安装' if bcut_available else '❌ 未安装'}")
    logger.info(f"ffmpeg 状态: {'✅ 已安装' if ffmpeg_available else '❌ 未安装'}")
    
    if bcut_available and ffmpeg_available:
        logger.info("🎉 所有依赖已安装，无需重复安装")
        return True
    
    # 安装依赖
    logger.info("开始安装缺失的依赖...")
    success = install_dependencies()
    
    if success:
        logger.info("🎉 语音识别环境设置完成！")
        logger.info("现在可以使用以下功能:")
        logger.info("  - bcut-asr 云端语音识别（快速）")
        logger.info("  - whisper 本地语音识别（可靠）")
        logger.info("  - 智能回退机制")
        return True
    else:
        logger.error("❌ 环境设置失败")
        logger.info("请检查:")
        logger.info("  1. 网络连接是否正常")
        logger.info("  2. 系统权限是否足够")
        logger.info("  3. 依赖工具是否可用（git, pip等）")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

