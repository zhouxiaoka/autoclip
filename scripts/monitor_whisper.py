#!/usr/bin/env python3
"""
Whisper进程监控工具
用于检测和防止重复的Whisper进程
"""

import psutil
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_whisper_processes():
    """查找所有正在运行的Whisper进程"""
    whisper_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info']):
        try:
            cmdline = proc.info['cmdline'] or []
            if 'whisper' in proc.info['name'].lower() or any('whisper' in str(arg).lower() for arg in cmdline):
                whisper_processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmdline': ' '.join(cmdline),
                    'cpu_percent': proc.info['cpu_percent'],
                    'memory_mb': proc.info['memory_info'].rss / 1024 / 1024
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    return whisper_processes

def check_duplicate_whisper_processes():
    """检查是否有重复的Whisper进程处理同一个文件"""
    whisper_processes = find_whisper_processes()
    
    if not whisper_processes:
        logger.info("没有发现Whisper进程")
        return True
    
    logger.info(f"发现 {len(whisper_processes)} 个Whisper进程:")
    
    # 按视频文件分组
    video_files = {}
    for proc in whisper_processes:
        cmdline = proc['cmdline']
        # 提取视频文件路径
        parts = cmdline.split()
        video_file = None
        for i, part in enumerate(parts):
            if part.endswith(('.mp4', '.avi', '.mkv', '.mov', '.wav', '.mp3')):
                video_file = part
                break
        
        if video_file:
            if video_file not in video_files:
                video_files[video_file] = []
            video_files[video_file].append(proc)
    
    # 检查重复处理
    duplicates_found = False
    for video_file, processes in video_files.items():
        if len(processes) > 1:
            logger.warning(f"发现重复处理文件 {video_file}:")
            duplicates_found = True
            for proc in processes:
                logger.warning(f"  PID {proc['pid']}: CPU {proc['cpu_percent']:.1f}%, 内存 {proc['memory_mb']:.1f}MB")
    
    if not duplicates_found:
        logger.info("没有发现重复处理的Whisper进程")
    
    return not duplicates_found

def kill_duplicate_whisper_processes():
    """终止重复的Whisper进程"""
    whisper_processes = find_whisper_processes()
    
    if not whisper_processes:
        logger.info("没有Whisper进程需要终止")
        return
    
    # 按视频文件分组
    video_files = {}
    for proc in whisper_processes:
        cmdline = proc['cmdline']
        parts = cmdline.split()
        video_file = None
        for i, part in enumerate(parts):
            if part.endswith(('.mp4', '.avi', '.mkv', '.mov', '.wav', '.mp3')):
                video_file = part
                break
        
        if video_file:
            if video_file not in video_files:
                video_files[video_file] = []
            video_files[video_file].append(proc)
    
    # 保留CPU使用率最高的进程，终止其他的
    for video_file, processes in video_files.items():
        if len(processes) > 1:
            logger.info(f"处理重复进程 - 文件: {video_file}")
            
            # 按CPU使用率排序，保留最高的
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            keep_process = processes[0]
            
            logger.info(f"保留进程 PID {keep_process['pid']} (CPU: {keep_process['cpu_percent']:.1f}%)")
            
            # 终止其他进程
            for proc in processes[1:]:
                try:
                    logger.info(f"终止重复进程 PID {proc['pid']}")
                    psutil.Process(proc['pid']).terminate()
                except psutil.NoSuchProcess:
                    logger.info(f"进程 PID {proc['pid']} 已经不存在")
                except psutil.AccessDenied:
                    logger.error(f"无法终止进程 PID {proc['pid']} (权限不足)")

def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == '--kill-duplicates':
        logger.info("检查并终止重复的Whisper进程...")
        kill_duplicate_whisper_processes()
    else:
        logger.info("检查Whisper进程状态...")
        if check_duplicate_whisper_processes():
            logger.info("✅ 系统状态正常")
            sys.exit(0)
        else:
            logger.warning("⚠️ 发现重复的Whisper进程")
            sys.exit(1)

if __name__ == '__main__':
    main()
