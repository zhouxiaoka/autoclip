# 🎬 字幕下载故障排除指南

## 📋 概述

本指南帮助用户解决B站和YouTube视频字幕下载失败的问题。字幕下载失败是用户反馈最多的问题之一，主要涉及以下几个方面：

1. **B站字幕需要登录**
2. **YouTube字幕格式不兼容**
3. **语音识别备用方案配置问题**
4. **网络连接和权限问题**

## 🔍 问题诊断

### 使用诊断工具

我们提供了专门的诊断工具来帮助排查问题：

```bash
# 检查语音识别设置
python scripts/debug_subtitle_download.py --check-speech

# 诊断B站字幕下载
python scripts/debug_subtitle_download.py https://www.bilibili.com/video/BV1xx411c7mu chrome

# 诊断YouTube字幕下载
python scripts/debug_subtitle_download.py https://www.youtube.com/watch?v=dQw4w9WgXcQ chrome
```

### 常见错误信息

#### B站相关错误

1. **"Subtitles are only available when logged in"**
   - **原因**: B站的字幕（特别是AI字幕）需要登录才能下载
   - **解决方案**: 
     - 在浏览器中登录B站账号
     - 选择对应的浏览器（Chrome、Firefox、Safari等）
     - 确保浏览器中有B站的登录状态

2. **"未找到字幕文件"**
   - **原因**: 视频可能没有字幕或字幕下载失败
   - **解决方案**: 
     - 检查视频是否有字幕（在B站网页上查看）
     - 尝试不同的字幕语言
     - 使用语音识别生成字幕

#### YouTube相关错误

1. **"No subtitles available"**
   - **原因**: 视频没有字幕或自动生成字幕
   - **解决方案**: 
     - 检查视频是否有字幕轨道
     - 尝试下载自动生成的字幕
     - 使用语音识别生成字幕

2. **"VTT format not supported"**
   - **原因**: YouTube下载的是VTT格式字幕，需要转换为SRT
   - **解决方案**: 系统会自动转换，如果失败请检查文件权限

#### 语音识别相关错误

1. **"whisper: command not found"**
   - **原因**: 未安装Whisper语音识别工具
   - **解决方案**: 
     ```bash
     pip install openai-whisper
     ```

2. **"ffmpeg: command not found"**
   - **原因**: 未安装ffmpeg
   - **解决方案**: 
     ```bash
     # macOS
     brew install ffmpeg
     
     # Ubuntu/Debian
     sudo apt update && sudo apt install ffmpeg
     
     # Windows
     # 下载ffmpeg并添加到PATH环境变量
     ```

3. **"语音识别超时"**
   - **原因**: 视频太长或系统性能不足
   - **解决方案**: 
     - 使用更小的Whisper模型（tiny、base）
     - 增加超时时间
     - 检查系统内存和CPU使用情况

## 🛠️ 解决方案

### 1. B站字幕下载优化

#### 登录配置
```python
# 确保在浏览器中登录B站
# 选择正确的浏览器
browser = "chrome"  # 或 "firefox", "safari"
```

#### 多种字幕策略
系统会自动尝试以下策略：
1. **AI字幕优先**: 尝试下载AI生成的中文字幕
2. **多语言策略**: 尝试中文、英文等多种语言
3. **无cookies策略**: 尝试不使用cookies下载公开字幕

#### 手动配置
```python
# 在下载时指定字幕语言
ydl_opts = {
    'subtitleslangs': ['ai-zh', 'zh-Hans', 'zh', 'en'],
    'writeautomaticsub': True,
    'cookiesfrombrowser': ('chrome',)
}
```

### 2. YouTube字幕下载优化

#### 字幕格式支持
```python
# 支持多种字幕格式
formats = ['srt', 'vtt', 'json3']
languages = ['en', 'zh-Hans', 'zh', 'ja', 'ko']
```

#### 自动格式转换
系统会自动将VTT格式转换为SRT格式：
```python
# VTT到SRT转换
async def _convert_vtt_to_srt(vtt_path: str, srt_path: str):
    # 自动转换时间格式和字幕结构
```

### 3. 语音识别备用方案

#### 安装Whisper
```bash
# 安装Whisper
pip install openai-whisper

# 验证安装
whisper --help
```

#### 模型选择
```python
# 根据需求选择模型
models = {
    "tiny": "39MB, 最快，准确率较低",
    "base": "74MB, 较快，准确率中等（推荐）",
    "small": "244MB, 中等速度，准确率较高",
    "medium": "769MB, 较慢，准确率很高",
    "large": "1550MB, 最慢，准确率最高"
}
```

#### 语言配置
```python
# 指定语言提高准确率
languages = {
    "zh": "中文",
    "en": "英文",
    "ja": "日文",
    "ko": "韩文",
    "auto": "自动检测"
}
```

## 📊 性能优化建议

### 1. 网络优化
- 使用稳定的网络连接
- 避免在高峰时段下载
- 考虑使用代理或VPN

### 2. 系统优化
- 确保有足够的磁盘空间
- 关闭不必要的应用程序
- 使用SSD硬盘提高I/O性能

### 3. 配置优化
```python
# 优化下载配置
ydl_opts = {
    'format': 'best[ext=mp4]/best',  # 选择最佳质量
    'writesubtitles': True,
    'writeautomaticsub': True,
    'subtitleslangs': ['ai-zh', 'zh-Hans', 'en'],
    'subtitlesformat': 'srt',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': False,  # 显示警告信息
}
```

## 🔧 高级故障排除

### 1. 检查yt-dlp版本
```bash
# 更新到最新版本
pip install --upgrade yt-dlp

# 检查版本
yt-dlp --version
```

### 2. 检查浏览器cookies
```bash
# 确保浏览器中有正确的cookies
# 在浏览器中访问B站/YouTube并登录
# 检查cookies是否有效
```

### 3. 测试网络连接
```bash
# 测试网络连接
ping www.bilibili.com
ping www.youtube.com

# 测试DNS解析
nslookup www.bilibili.com
nslookup www.youtube.com
```

### 4. 检查文件权限
```bash
# 检查下载目录权限
ls -la /path/to/download/directory

# 确保有写入权限
chmod 755 /path/to/download/directory
```

## 📞 获取帮助

### 1. 查看日志
```bash
# 查看详细日志
tail -f backend.log

# 查看错误日志
grep "ERROR" backend.log
```

### 2. 使用诊断工具
```bash
# 完整诊断
python scripts/debug_subtitle_download.py <url> <browser>

# 检查语音识别
python scripts/debug_subtitle_download.py --check-speech
```

### 3. 常见问题FAQ

**Q: 为什么B站字幕下载总是失败？**
A: B站的字幕需要登录才能下载，请确保在浏览器中登录B站账号并选择正确的浏览器。

**Q: YouTube字幕下载失败怎么办？**
A: 尝试以下步骤：
1. 检查视频是否有字幕
2. 尝试不同的字幕语言
3. 使用语音识别生成字幕

**Q: 语音识别很慢怎么办？**
A: 可以：
1. 使用更小的模型（tiny或base）
2. 增加超时时间
3. 检查系统性能

**Q: 如何提高字幕下载成功率？**
A: 建议：
1. 确保网络连接稳定
2. 使用最新版本的yt-dlp
3. 正确配置浏览器cookies
4. 安装Whisper作为备用方案

## 🎯 最佳实践

### 1. 日常使用建议
- 优先使用B站/YouTube原生字幕
- 配置语音识别作为备用方案
- 定期更新yt-dlp和Whisper
- 保持浏览器登录状态

### 2. 批量处理建议
- 分批处理大量视频
- 监控系统资源使用
- 设置合理的超时时间
- 保存诊断结果以便分析

### 3. 错误处理建议
- 记录详细的错误信息
- 使用诊断工具分析问题
- 尝试多种解决方案
- 及时反馈问题给开发团队

---

通过以上指南，您应该能够解决大部分字幕下载问题。如果问题仍然存在，请使用诊断工具生成详细报告，并联系技术支持团队。

