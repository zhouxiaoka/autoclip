# 🎤 语音识别模块重新设计

## 📋 概述

根据用户需求，我们对语音识别模块进行了全面重新设计，主要改进包括：

1. **移除测试字幕数据** - 转写失败直接报任务失败，不再使用mock数据
2. **支持多语种识别** - 支持中文、英文、日文、韩文等多种语言
3. **支持多种API接入** - 支持本地Whisper、OpenAI API、Azure Speech Services等

## 🔧 主要改进

### 1. 移除测试字幕功能

**之前的问题：**
- 当语音识别失败时，系统会生成测试字幕文件
- 测试字幕内容不准确，影响后续处理质量
- 用户可能误以为处理成功

**现在的改进：**
- 完全移除测试字幕生成功能
- 语音识别失败时直接抛出异常
- 确保生产环境的数据质量

```python
# 之前：返回None或测试字幕
result = generate_subtitle_for_video(video_path)
if result is None:
    # 生成测试字幕...

# 现在：失败时抛出异常
try:
    result = generate_subtitle_for_video(video_path)
except SpeechRecognitionError as e:
    # 处理语音识别失败
    logger.error(f"语音识别失败: {e}")
    raise
```

### 2. 多语种支持

**支持的语言：**
- 中文（简体/繁体）
- 英文（美式/英式）
- 日文
- 韩文
- 法文
- 德文
- 西班牙文
- 俄文
- 阿拉伯文
- 葡萄牙文
- 意大利文
- 自动检测

**使用方式：**
```python
from shared.utils.speech_recognizer import generate_subtitle_for_video, LanguageCode

# 指定语言
result = generate_subtitle_for_video(
    video_path, 
    language=LanguageCode.CHINESE_SIMPLIFIED
)

# 自动检测语言
result = generate_subtitle_for_video(
    video_path, 
    language=LanguageCode.AUTO
)
```

### 3. 多种语音识别服务

**支持的服务：**

| 服务 | 特点 | 配置要求 |
|------|------|----------|
| 本地Whisper | 免费、离线、准确率高 | 安装whisper和ffmpeg |
| OpenAI API | 准确率最高、支持多种语言 | OpenAI API密钥 |
| Azure Speech | 企业级、功能丰富 | Azure账户和API密钥 |
| Google Speech | 准确率高、支持高级功能 | Google Cloud账户 |
| 阿里云语音 | 中文识别效果好 | 阿里云账户和API密钥 |

**自动选择策略：**
1. 本地Whisper（推荐）
2. OpenAI API
3. Azure Speech Services
4. Google Speech-to-Text
5. 阿里云语音识别

## 🚀 新的API接口

### 语音识别状态查询

```bash
GET /api/v1/speech-recognition/status
```

返回：
```json
{
  "available_methods": {
    "whisper_local": true,
    "openai_api": false,
    "azure_speech": false,
    "google_speech": false,
    "aliyun_speech": false
  },
  "supported_languages": ["zh", "en", "ja", "ko", "auto"],
  "whisper_models": ["tiny", "base", "small", "medium", "large"],
  "default_config": {
    "method": "whisper_local",
    "language": "auto",
    "model": "base",
    "timeout": 300
  }
}
```

### 配置测试

```bash
POST /api/v1/speech-recognition/test
```

请求体：
```json
{
  "method": "whisper_local",
  "language": "zh",
  "model": "base",
  "timeout": 300
}
```

### 安装指南

```bash
GET /api/v1/speech-recognition/install-guide?method=whisper_local
```

## 📝 配置管理

### 环境变量配置

```bash
# 语音识别方法
export SPEECH_RECOGNITION_METHOD="whisper_local"

# 语言设置
export SPEECH_RECOGNITION_LANGUAGE="zh"

# Whisper模型
export SPEECH_RECOGNITION_MODEL="base"

# 超时时间
export SPEECH_RECOGNITION_TIMEOUT="300"

# API密钥（根据选择的服务）
export OPENAI_API_KEY="your-openai-key"
export AZURE_SPEECH_KEY="your-azure-key"
export AZURE_SPEECH_REGION="your-region"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/credentials.json"
export ALIYUN_ACCESS_KEY_ID="your-access-key"
export ALIYUN_ACCESS_KEY_SECRET="your-secret-key"
export ALIYUN_SPEECH_APP_KEY="your-app-key"
```

### 配置文件

在 `data/settings.json` 中可以配置：

```json
{
  "speech_recognition_method": "whisper_local",
  "speech_recognition_language": "zh",
  "speech_recognition_model": "base",
  "speech_recognition_timeout": 300
}
```

## 🔍 错误处理

### 新的异常类型

```python
from shared.utils.speech_recognizer import SpeechRecognitionError

try:
    result = generate_subtitle_for_video(video_path)
except SpeechRecognitionError as e:
    # 处理语音识别错误
    logger.error(f"语音识别失败: {e}")
    # 可以选择重试或使用其他方法
```

### 错误类型

1. **服务不可用** - 指定的语音识别服务未安装或配置
2. **文件不存在** - 视频文件不存在或无法访问
3. **执行超时** - 语音识别处理超时
4. **执行失败** - 语音识别服务执行失败
5. **配置错误** - 参数配置不正确

## 📊 性能优化

### Whisper模型选择

| 模型 | 大小 | 速度 | 准确率 | 适用场景 |
|------|------|------|--------|----------|
| tiny | 39MB | ⭐⭐⭐⭐⭐ | ⭐⭐ | 快速测试 |
| base | 74MB | ⭐⭐⭐⭐ | ⭐⭐⭐ | 日常使用 |
| small | 244MB | ⭐⭐⭐ | ⭐⭐⭐⭐ | 高质量需求 |
| medium | 769MB | ⭐⭐ | ⭐⭐⭐⭐⭐ | 专业用途 |
| large | 1550MB | ⭐ | ⭐⭐⭐⭐⭐ | 最高质量 |

### 超时设置

- 短视频（<5分钟）：60秒
- 中等视频（5-30分钟）：300秒
- 长视频（>30分钟）：600秒

## 🛠️ 安装指南

### 本地Whisper安装

```bash
# 安装Python依赖
pip install openai-whisper

# 安装系统依赖
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# 下载ffmpeg并添加到PATH

# 验证安装
whisper --help
```

### API服务配置

#### OpenAI API
```bash
export OPENAI_API_KEY="your-api-key"
```

#### Azure Speech Services
```bash
export AZURE_SPEECH_KEY="your-api-key"
export AZURE_SPEECH_REGION="your-region"
```

#### Google Speech-to-Text
```bash
export GOOGLE_APPLICATION_CREDENTIALS="path/to/credentials.json"
```

#### 阿里云语音识别
```bash
export ALIYUN_ACCESS_KEY_ID="your-access-key"
export ALIYUN_ACCESS_KEY_SECRET="your-secret-key"
export ALIYUN_SPEECH_APP_KEY="your-app-key"
```

## 🔄 迁移指南

### 从旧版本迁移

1. **更新导入语句**
```python
# 旧版本
from shared.utils.speech_recognizer import generate_subtitle_for_video

# 新版本
from shared.utils.speech_recognizer import (
    generate_subtitle_for_video, 
    SpeechRecognitionError,
    LanguageCode
)
```

2. **更新错误处理**
```python
# 旧版本
result = generate_subtitle_for_video(video_path)
if result is None:
    # 处理失败

# 新版本
try:
    result = generate_subtitle_for_video(video_path)
except SpeechRecognitionError as e:
    # 处理失败
```

3. **移除测试字幕相关代码**
```python
# 删除这些代码
if method == "simple":
    return recognizer.generate_subtitle_simple(video_path, output_path)
```

## 📈 监控和日志

### 日志记录

```python
import logging
logger = logging.getLogger(__name__)

# 语音识别开始
logger.info(f"开始语音识别: {video_path}")

# 语音识别成功
logger.info(f"语音识别成功: {output_path}")

# 语音识别失败
logger.error(f"语音识别失败: {error}")
```

### 性能监控

建议监控以下指标：
- 语音识别成功率
- 处理时间
- 错误类型分布
- 不同服务的使用情况

## 🎯 最佳实践

1. **生产环境建议**
   - 使用 `small` 或 `medium` 模型
   - 设置合理的超时时间
   - 配置错误重试机制

2. **多语言处理**
   - 优先使用自动语言检测
   - 对于特定语言内容，明确指定语言代码
   - 考虑使用专门的语音识别服务

3. **错误处理**
   - 实现优雅的错误处理
   - 提供用户友好的错误信息
   - 考虑降级策略

4. **性能优化**
   - 根据视频长度选择合适的模型
   - 使用GPU加速（如果可用）
   - 考虑并行处理多个视频

## 🔮 未来计划

1. **实现更多API服务**
   - 百度语音识别
   - 腾讯云语音识别
   - 华为云语音识别

2. **增强功能**
   - 说话人分离
   - 情感识别
   - 关键词提取

3. **性能优化**
   - 流式处理
   - 缓存机制
   - 分布式处理

## 📞 技术支持

如果遇到问题，请：

1. 检查日志文件中的错误信息
2. 验证语音识别服务是否正确安装
3. 确认配置文件是否正确
4. 查看API文档和安装指南

更多帮助请参考：
- [Whisper官方文档](https://github.com/openai/whisper)
- [OpenAI API文档](https://platform.openai.com/docs/api-reference)
- [Azure Speech Services文档](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/)
- [Google Speech-to-Text文档](https://cloud.google.com/speech-to-text/docs)
- [阿里云语音识别文档](https://help.aliyun.com/product/30413.html)

