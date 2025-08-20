# 可选SRT文件上传功能指南

## 概述

AutoClip现在支持两种上传方式：
1. **视频 + 字幕文件**：用户同时上传视频和SRT字幕文件
2. **仅视频文件**：用户只上传视频文件，系统自动使用语音识别生成字幕

## 功能特性

### ✅ 智能上传模式
- **用户优先**：如果用户提供了字幕文件，优先使用用户的字幕
- **AI辅助**：如果用户只上传视频，自动调用语音识别生成字幕
- **错误处理**：语音识别失败时，清晰地向用户报告错误信息

### ✅ 多语言支持
- 支持15种语言的语音识别
- 根据视频分类智能选择识别语言：
  - 商业/知识类：优先使用中文识别
  - 娱乐类：自动检测语言
  - 其他：自动检测语言

### ✅ 多种语音识别方式
- 本地Whisper（推荐）
- OpenAI API
- Azure Speech Services
- Google Speech-to-Text
- 阿里云语音识别

## 使用方法

### 前端界面变化

1. **上传提示更新**
   - 原文：必须同时导入字幕文件(.srt)
   - 新文：可选择导入字幕文件(.srt)或使用AI自动生成

2. **智能提示**
   - 上传视频+字幕：显示两个文件
   - 仅上传视频：显示"将使用AI语音识别自动生成字幕文件"

3. **上传按钮逻辑**
   - 原来：需要视频+字幕+项目名称
   - 现在：只需要视频+项目名称

### API接口变化

#### 上传接口 `POST /api/v1/projects/upload`

**参数变化：**
```python
# 之前：srt_file是必需的
srt_file: UploadFile = File(...)

# 现在：srt_file是可选的
srt_file: Optional[UploadFile] = File(None)
```

**请求示例：**

1. **同时上传视频和字幕**
```python
files = {
    'video_file': ('video.mp4', video_content, 'video/mp4'),
    'srt_file': ('subtitle.srt', srt_content, 'application/x-subrip')
}
data = {
    'project_name': '我的项目',
    'video_category': 'knowledge'
}
```

2. **仅上传视频**
```python
files = {
    'video_file': ('video.mp4', video_content, 'video/mp4')
}
data = {
    'project_name': '我的项目',
    'video_category': 'knowledge'
}
```

**响应示例：**

成功响应保持不变，但项目描述会反映处理方式：
```json
{
    "id": "project-id",
    "name": "我的项目",
    "description": "Video: video.mp4 (Will generate subtitle using speech recognition)",
    "settings": {
        "auto_generate_subtitle": true,
        "video_category": "knowledge"
    }
}
```

**错误处理：**

语音识别失败时返回400错误：
```json
{
    "detail": "语音识别失败: 没有可用的语音识别服务，请安装whisper或配置API密钥。请手动上传字幕文件或检查语音识别服务配置。"
}
```

## 技术实现

### 后端实现

1. **参数验证**
   ```python
   # 视频文件验证（必需）
   if not video_file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
       raise HTTPException(status_code=400, detail="Invalid video file format")
   
   # 字幕文件验证（可选）
   if srt_file and not srt_file.filename.lower().endswith('.srt'):
       raise HTTPException(status_code=400, detail="Invalid subtitle file format")
   ```

2. **字幕处理逻辑**
   ```python
   if srt_file:
       # 保存用户提供的字幕文件
       srt_path = save_user_subtitle(srt_file)
   else:
       # 使用语音识别生成字幕
       srt_path = generate_subtitle_with_speech_recognition(video_path, language, model)
   ```

3. **语言选择策略**
   ```python
   # 根据视频分类确定语言
   language = "auto"  # 默认自动检测
   if video_category in ["business", "knowledge"]:
       language = "zh"  # 中文内容
   elif video_category == "entertainment":
       language = "auto"  # 娱乐内容可能是多语言
   ```

### 前端实现

1. **上传逻辑修改**
   ```typescript
   // 移除字幕文件必需验证
   if (!files.video) {
       message.error('请选择视频文件')
       return
   }
   // if (!files.srt) {  // 移除这个检查
   //     message.error('请同时导入字幕文件(.srt)')
   //     return
   // }
   ```

2. **UI提示更新**
   ```typescript
   // 智能提示
   {files.video && !files.srt && (
       <div>将使用AI语音识别自动生成字幕文件</div>
   )}
   ```

3. **API调用修改**
   ```typescript
   const formData = new FormData()
   formData.append('video_file', data.video_file)
   if (data.srt_file) {  // 只在有字幕文件时才添加
       formData.append('srt_file', data.srt_file)
   }
   ```

## 配置要求

### 语音识别服务配置

为了使用自动语音识别功能，需要配置至少一种语音识别服务：

#### 1. 本地Whisper（推荐）
```bash
# 安装Whisper
pip install openai-whisper

# 安装FFmpeg
# macOS
brew install ffmpeg
# Ubuntu/Debian
sudo apt install ffmpeg
```

#### 2. OpenAI API
```bash
export OPENAI_API_KEY="your-api-key"
```

#### 3. Azure Speech Services
```bash
export AZURE_SPEECH_KEY="your-api-key"
export AZURE_SPEECH_REGION="your-region"
```

#### 4. Google Speech-to-Text
```bash
export GOOGLE_APPLICATION_CREDENTIALS="path/to/credentials.json"
```

#### 5. 阿里云语音识别
```bash
export ALIYUN_ACCESS_KEY_ID="your-access-key"
export ALIYUN_ACCESS_KEY_SECRET="your-secret-key"
export ALIYUN_SPEECH_APP_KEY="your-app-key"
```

### 检查配置状态

可以通过新的API端点检查语音识别服务状态：

```bash
# 检查可用的语音识别方法
GET /api/v1/speech-recognition/status

# 响应示例
{
    "available_methods": {
        "whisper_local": true,
        "openai_api": false,
        "azure_speech": false,
        "google_speech": false,
        "aliyun_speech": false
    },
    "supported_languages": ["zh", "en", "ja", "ko", "fr", "de", ...],
    "whisper_models": ["tiny", "base", "small", "medium", "large"],
    "default_config": {
        "method": "whisper_local",
        "language": "auto",
        "model": "base",
        "timeout": 300
    }
}
```

## 最佳实践

### 1. 用户体验优化
- **清晰提示**：明确告知用户字幕文件是可选的
- **处理时间**：告知用户语音识别可能需要较长时间
- **错误恢复**：提供手动上传字幕的替代方案

### 2. 性能考虑
- **模型选择**：默认使用`base`模型平衡速度和准确性
- **语言优化**：根据内容类型选择合适的识别语言
- **超时设置**：合理设置语音识别超时时间（默认5分钟）

### 3. 错误处理
- **服务检查**：启动时检查语音识别服务可用性
- **降级策略**：优先级顺序尝试不同的语音识别服务
- **用户友好**：提供清晰的错误信息和解决建议

## 故障排除

### 常见问题

1. **"没有可用的语音识别服务"**
   - 检查是否安装了Whisper：`which whisper`
   - 检查是否配置了API密钥
   - 查看服务状态：`GET /api/v1/speech-recognition/status`

2. **"语音识别超时"**
   - 检查视频文件大小（建议<100MB）
   - 增加超时设置
   - 尝试使用更快的模型（tiny/base）

3. **"字幕文件不存在"**
   - 检查Whisper是否正确安装
   - 查看后端日志了解详细错误
   - 尝试手动运行Whisper命令测试

### 调试步骤

1. **检查服务状态**
   ```bash
   curl http://localhost:8000/api/v1/speech-recognition/status
   ```

2. **查看后端日志**
   ```bash
   tail -f backend/backend.log
   ```

3. **测试Whisper安装**
   ```bash
   whisper --help
   ffmpeg -version
   ```

## 更新日志

### v1.0.0
- ✅ 支持可选SRT文件上传
- ✅ 集成多种语音识别服务
- ✅ 智能语言选择
- ✅ 完善的错误处理
- ✅ 用户友好的界面提示

---

## 相关文档

- [语音识别重新设计文档](./SPEECH_RECOGNITION_REDESIGN.md)
- [语音识别设置指南](./SPEECH_RECOGNITION_SETUP.md)
- [后端架构文档](./BACKEND_ARCHITECTURE.md)

