# 🎤 bcut-asr 集成说明

## 📋 概述

AutoClip 现已成功集成 bcut-asr 语音识别接口，实现了**先调用 bcut-asr 接口，失败时自动回退到 whisper 本地模型**的策略。这大大提升了语音识别的速度，同时保持了系统的可靠性。

## ✨ 主要特性

### 🚀 性能优势
- **速度更快**: bcut-asr 是云端服务，识别速度比本地 whisper 快很多
- **准确率高**: 必剪的语音识别技术准确率较高
- **支持多种格式**: 支持 `flac`, `aac`, `m4a`, `mp3`, `wav` 等音频格式
- **自动转码**: 自动调用 ffmpeg 处理视频伴音和其他格式

### 🔄 智能回退机制
- **主方法**: 优先使用 bcut-asr 进行语音识别
- **回退方法**: 当 bcut-asr 失败时，自动切换到 whisper 本地模型
- **无缝切换**: 用户无需手动干预，系统自动处理

### 🎯 多种输出格式
- **SRT**: 标准字幕格式（默认）
- **JSON**: 结构化数据格式
- **LRC**: 歌词格式
- **TXT**: 纯文本格式

## 🔧 安装和配置

### 🚀 自动安装（推荐）

系统会自动处理 bcut-asr 的安装，无需手动操作：

```python
# 直接使用，系统会自动安装依赖
from backend.utils.speech_recognizer import generate_subtitle_for_video
from pathlib import Path

video_path = Path("your_video.mp4")
subtitle_path = generate_subtitle_for_video(video_path, method="auto")
```

### 📋 手动安装（备选方案）

如果自动安装失败，可以手动安装：

#### 1. 运行自动安装脚本

```bash
# 运行自动安装脚本
python scripts/install_bcut_asr.py

# 或运行环境设置脚本
python scripts/setup_speech_recognition.py
```

#### 2. 手动安装 bcut-asr

```bash
# 克隆仓库
git clone https://github.com/SocialSisterYi/bcut-asr.git
cd bcut-asr

# 安装依赖
poetry lock
poetry build -f wheel

# 安装包
pip install dist/bcut_asr-0.0.3-py3-none-any.whl
```

#### 3. 确保 ffmpeg 已安装

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
winget install ffmpeg
```

#### 4. 获取安装指导

```bash
# 运行手动安装指导脚本
python scripts/manual_install_guide.py
```

### 3. 验证安装

```bash
# 运行测试脚本
python scripts/test_auto_install.py
```

## 🚀 使用方法

### 自动模式（推荐）

```python
from backend.utils.speech_recognizer import generate_subtitle_for_video
from pathlib import Path

# 自动选择最佳方法（优先 bcut-asr，失败时回退到 whisper）
video_path = Path("your_video.mp4")
subtitle_path = generate_subtitle_for_video(
    video_path, 
    method="auto", 
    enable_fallback=True
)
```

### 手动指定方法

```python
from backend.utils.speech_recognizer import (
    SpeechRecognizer, 
    SpeechRecognitionConfig, 
    SpeechRecognitionMethod
)

# 创建配置
config = SpeechRecognitionConfig(
    method=SpeechRecognitionMethod.BCUT_ASR,
    fallback_method=SpeechRecognitionMethod.WHISPER_LOCAL,
    enable_fallback=True,
    output_format="srt"
)

# 创建识别器
recognizer = SpeechRecognizer(config)

# 生成字幕
subtitle_path = recognizer.generate_subtitle(video_path, config=config)
```

### 仅使用 bcut-asr

```python
config = SpeechRecognitionConfig(
    method=SpeechRecognitionMethod.BCUT_ASR,
    enable_fallback=False  # 禁用回退
)
```

### 仅使用 whisper

```python
config = SpeechRecognitionConfig(
    method=SpeechRecognitionMethod.WHISPER_LOCAL,
    enable_fallback=False
)
```

## 📊 方法优先级

系统按以下优先级自动选择语音识别方法：

1. **bcut-asr** - 云端服务，速度快
2. **whisper_local** - 本地模型，可靠性高
3. **openai_api** - OpenAI API（需要配置）
4. **azure_speech** - Azure 语音服务（需要配置）
5. **google_speech** - Google 语音服务（需要配置）
6. **aliyun_speech** - 阿里云语音服务（需要配置）

## 🔍 状态检查

### 检查可用方法

```python
from backend.utils.speech_recognizer import get_available_speech_recognition_methods

available_methods = get_available_speech_recognition_methods()
print(available_methods)
# 输出: {'bcut_asr': True, 'whisper_local': True, ...}
```

### 检查识别器状态

```python
from backend.utils.speech_recognizer import SpeechRecognizer

recognizer = SpeechRecognizer()
available_methods = recognizer.get_available_methods()
supported_languages = recognizer.get_supported_languages()
whisper_models = recognizer.get_whisper_models()
```

## ⚠️ 注意事项

### 网络要求
- bcut-asr 需要网络连接
- 如果网络不稳定，系统会自动回退到 whisper

### 文件大小限制
- bcut-asr 对文件大小可能有限制
- 超大文件建议先压缩或分段处理

### 隐私考虑
- bcut-asr 会将音频上传到云端
- 敏感内容建议使用本地 whisper

## 🐛 故障排除

### bcut-asr 不可用
```bash
# 检查是否已安装
python -c "import bcut_asr; print('bcut-asr 已安装')"

# 重新安装
pip uninstall bcut-asr
# 然后按照安装步骤重新安装
```

### ffmpeg 不可用
```bash
# 检查 ffmpeg
ffmpeg -version

# 如果未安装，按照上述步骤安装
```

### 回退机制不工作
```python
# 检查可用方法
available_methods = get_available_speech_recognition_methods()
print(f"bcut-asr: {available_methods.get('bcut_asr', False)}")
print(f"whisper: {available_methods.get('whisper_local', False)}")
```

## 📈 性能对比

| 方法 | 速度 | 准确率 | 网络要求 | 隐私性 |
|------|------|--------|----------|--------|
| bcut-asr | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 需要 | 云端处理 |
| whisper | ⭐⭐ | ⭐⭐⭐⭐⭐ | 不需要 | 本地处理 |

## 🔮 未来计划

1. **更多云端服务**: 集成更多语音识别服务
2. **智能选择**: 根据文件大小、网络状况智能选择方法
3. **批量处理**: 支持批量文件的语音识别
4. **实时识别**: 支持实时语音识别

## 📞 技术支持

如果遇到问题，请：

1. 查看日志文件 `logs/backend.log`
2. 运行测试脚本 `python scripts/test_bcut_asr_integration.py`
3. 检查网络连接和依赖安装
4. 提交 Issue 到项目仓库

---

**🎉 现在您可以享受更快的语音识别体验了！**
