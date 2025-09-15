#!/bin/bash
# bcut-asr 手动安装脚本

echo "开始安装 bcut-asr..."

# 检查 Python 版本
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python 版本: $python_version"

if [[ $(echo "$python_version < 3.10" | bc -l) -eq 1 ]]; then
    echo "错误: 需要 Python 3.10 或更高版本"
    exit 1
fi

# 安装 ffmpeg
echo "安装 ffmpeg..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    if command -v brew &> /dev/null; then
        brew install ffmpeg
    else
        echo "请先安装 Homebrew: https://brew.sh/"
        exit 1
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    sudo apt update
    sudo apt install -y ffmpeg
else
    echo "请手动安装 ffmpeg"
fi

# 克隆并安装 bcut-asr
echo "克隆 bcut-asr 仓库..."
git clone https://github.com/SocialSisterYi/bcut-asr.git
cd bcut-asr

echo "安装 bcut-asr..."
pip install .

echo "验证安装..."
python3 -c "import bcut_asr; print('bcut-asr 安装成功')"

echo "安装完成！"
