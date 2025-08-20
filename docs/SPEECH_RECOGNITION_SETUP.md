# 🎤 语音识别设置指南

## 📋 概述

AutoClip支持多种语音识别方式来生成字幕文件，当视频没有字幕时，系统会自动生成字幕以确保流水线处理能够正常进行。

## 🔧 支持的语音识别方式

### 1. 本地Whisper（推荐）

**特点：**
- ✅ 完全本地运行，无需网络
- ✅ 无需API密钥
- ✅ 免费使用
- ✅ 支持多种语言
- ✅ 准确率较高

**安装方法：**

```bash
# 方法1：使用pip安装
pip install openai-whisper

# 方法2：使用conda安装
conda install -c conda-forge openai-whisper

# 方法3：从源码安装
git clone https://github.com/openai/whisper.git
cd whisper
pip install -e .
```

**验证安装：**
```bash
whisper --help
```

**模型选择：**
- `tiny`: 39MB，最快，准确率较低
- `base`: 74MB，较快，准确率中等（默认）
- `small`: 244MB，中等速度，准确率较高
- `medium`: 769MB，较慢，准确率很高
- `large`: 1550MB，最慢，准确率最高

### 2. OpenAI API（计划中）

**特点：**
- ✅ 准确率最高
- ✅ 支持多种语言
- ❌ 需要API密钥
- ❌ 需要网络连接
- ❌ 有使用费用

**设置方法：**
```bash
# 设置环境变量
export OPENAI_API_KEY="your-api-key-here"
```

### 3. 测试字幕（备选方案）

**特点：**
- ✅ 无需安装任何依赖
- ✅ 立即可用
- ❌ 只是测试内容，不是真实字幕
- ❌ 流水线处理效果有限

## 🚀 使用方式

### 自动模式（默认）

系统会自动选择最佳的可用方法：

```python
from shared.utils.speech_recognizer import generate_subtitle_for_video

# 自动选择最佳方法
result = generate_subtitle_for_video(video_path, method="auto")
```

### 手动指定方法

```python
# 强制使用本地Whisper
result = generate_subtitle_for_video(video_path, method="whisper_local")

# 强制使用OpenAI API
result = generate_subtitle_for_video(video_path, method="openai_api")

# 强制使用测试字幕
result = generate_subtitle_for_video(video_path, method="simple")
```

### 检查可用方法

```python
from shared.utils.speech_recognizer import get_available_speech_recognition_methods

methods = get_available_speech_recognition_methods()
print(methods)
# 输出示例：
# {
#     "whisper_local": True,
#     "openai_api": False,
#     "simple": True
# }
```

## 📝 配置选项

### 修改Whisper参数

在 `shared/utils/speech_recognizer.py` 中可以修改Whisper的参数：

```python
cmd = [
    'whisper',
    str(video_path),
    '--output_dir', str(output_path.parent),
    '--output_format', 'srt',
    '--language', 'zh',  # 语言：zh(中文), en(英文), auto(自动检测)
    '--model', 'base'    # 模型：tiny, base, small, medium, large
]
```

### 常用参数说明

- `--language`: 指定语言，提高识别准确率
- `--model`: 选择模型大小，影响速度和准确率
- `--output_format`: 输出格式，支持srt, vtt, txt等
- `--task`: 任务类型，transcribe(转录)或translate(翻译)

## 🔍 故障排除

### Whisper安装问题

**问题：** `whisper: command not found`

**解决方案：**
```bash
# 检查是否安装成功
pip list | grep whisper

# 重新安装
pip uninstall openai-whisper
pip install openai-whisper

# 检查PATH
which whisper
```

**问题：** 依赖缺失

**解决方案：**
```bash
# 安装系统依赖（Ubuntu/Debian）
sudo apt update
sudo apt install ffmpeg

# 安装系统依赖（macOS）
brew install ffmpeg

# 安装Python依赖
pip install torch torchvision torchaudio
```

### 性能优化

**问题：** Whisper运行太慢

**解决方案：**
1. 使用更小的模型：`--model tiny`
2. 使用GPU加速（如果可用）
3. 分段处理长视频

**问题：** 内存不足

**解决方案：**
1. 使用更小的模型
2. 增加系统内存
3. 使用CPU模式

## 📊 性能对比

| 方法 | 速度 | 准确率 | 成本 | 网络依赖 | 安装难度 |
|------|------|--------|------|----------|----------|
| Whisper tiny | ⭐⭐⭐⭐⭐ | ⭐⭐ | 免费 | 无 | 简单 |
| Whisper base | ⭐⭐⭐⭐ | ⭐⭐⭐ | 免费 | 无 | 简单 |
| Whisper small | ⭐⭐⭐ | ⭐⭐⭐⭐ | 免费 | 无 | 简单 |
| Whisper medium | ⭐⭐ | ⭐⭐⭐⭐⭐ | 免费 | 无 | 简单 |
| OpenAI API | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 付费 | 需要 | 简单 |
| 测试字幕 | ⭐⭐⭐⭐⭐ | ⭐ | 免费 | 无 | 无需安装 |

## 🎯 推荐配置

### 开发环境
```bash
# 安装base模型（平衡速度和准确率）
pip install openai-whisper
```

### 生产环境
```bash
# 安装small或medium模型（更高准确率）
pip install openai-whisper
# 考虑使用GPU加速
```

### 测试环境
```bash
# 无需安装，使用测试字幕
# 系统会自动生成测试字幕文件
```

## 📞 技术支持

如果遇到问题，请：

1. 检查日志文件中的错误信息
2. 验证Whisper是否正确安装
3. 确认视频文件格式是否支持
4. 查看系统资源是否充足

更多帮助请参考：
- [Whisper官方文档](https://github.com/openai/whisper)
- [OpenAI API文档](https://platform.openai.com/docs/api-reference)
