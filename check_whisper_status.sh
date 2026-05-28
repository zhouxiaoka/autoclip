#!/bin/bash

# Whisper进程状态检查脚本
# 用于快速检查系统状态

echo "🔍 AutoClip Whisper进程状态检查"
echo "=================================="

# 检查Whisper进程
echo "📊 Whisper进程状态:"
python scripts/monitor_whisper.py

echo ""
echo "📈 系统资源使用情况:"
echo "CPU使用率: $(top -l 1 | grep "CPU usage" | awk '{print $3}' | sed 's/%//')"
echo "内存使用: $(ps -A -o %mem | awk '{s+=$1} END {print s "%"}')"

echo ""
echo "🛠️ 可用命令:"
echo "  检查状态: python scripts/monitor_whisper.py"
echo "  清理重复: python scripts/monitor_whisper.py --kill-duplicates"
echo "  停止系统: ./stop_autoclip.sh"
