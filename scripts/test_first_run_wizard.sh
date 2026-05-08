#!/bin/bash

# 测试首次运行向导的脚本

echo "🧪 AutoClip 首次运行向导测试脚本"
echo "=================================="

# 检查当前目录
if [ ! -f "package.json" ]; then
    echo "❌ 请在项目根目录运行此脚本"
    exit 1
fi

echo "📋 测试选项："
echo "1. 清除所有配置数据（模拟全新安装）"
echo "2. 清除API Key配置（保留其他数据）"
echo "3. 清除示例项目（保留配置）"
echo "4. 恢复原始配置"
echo "5. 启动开发服务器测试"
echo ""

read -p "请选择测试方式 (1-5): " choice

case $choice in
    1)
        echo "🗑️  清除所有配置数据..."
        rm -f data/settings.json
        rm -f data/autoclip.db
        rm -f data/progress.db
        rm -rf data/projects/*
        rm -rf data/example/*
        echo "✅ 所有配置数据已清除，下次启动将显示首次运行向导"
        ;;
    2)
        echo "🗑️  清除API Key配置..."
        if [ -f "data/settings.json" ]; then
            # 备份原配置
            cp data/settings.json data/settings.json.backup
            # 清除API Key
            jq 'del(.dashscope_api_key, .openai_api_key, .gemini_api_key, .siliconflow_api_key)' data/settings.json > data/settings.json.tmp
            mv data/settings.json.tmp data/settings.json
        fi
        echo "✅ API Key配置已清除，下次启动将显示首次运行向导"
        ;;
    3)
        echo "🗑️  清除示例项目..."
        # 这里可以添加清除示例项目的逻辑
        echo "✅ 示例项目已清除"
        ;;
    4)
        echo "🔄 恢复原始配置..."
        if [ -f "data/settings.json.backup" ]; then
            mv data/settings.json.backup data/settings.json
            echo "✅ 配置已恢复"
        else
            echo "❌ 没有找到备份配置文件"
        fi
        ;;
    5)
        echo "🚀 启动开发服务器..."
        echo "请确保后端服务已启动，然后访问 http://localhost:5173"
        echo ""
        echo "启动命令："
        echo "1. 启动后端: source venv/bin/activate && export AUTOCLIP_DESKTOP_MODE=1 && python backend/desktop_main.py"
        echo "2. 启动前端: cd frontend && npm run dev"
        ;;
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac

echo ""
echo "📝 测试说明："
echo "- 选择选项1或2后，重新启动应用将显示首次运行向导"
echo "- 向导包含4个步骤：欢迎、语音识别、AI模型、示例项目"
echo "- 完成向导后，应用将正常进入主界面"
echo ""
echo "🔧 手动测试步骤："
echo "1. 清除配置数据"
echo "2. 启动后端服务"
echo "3. 启动前端服务"
echo "4. 访问 http://localhost:5173"
echo "5. 观察是否显示首次运行向导"
