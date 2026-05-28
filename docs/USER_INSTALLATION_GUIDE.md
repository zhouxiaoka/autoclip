# 🚀 AutoClip Desktop 用户安装指南

## 📋 系统要求

### 支持的操作系统
- **macOS**: 10.13+ (支持Intel和Apple Silicon)
- **Windows**: Windows 10+ (64位)
- **Linux**: Ubuntu 18.04+, CentOS 7+, 或其他主流发行版

### 硬件要求
- **内存**: 最少4GB，推荐8GB+
- **存储**: 至少2GB可用空间
- **网络**: 用于下载AI模型和API调用

## 📦 安装步骤

### 1. 下载安装包

从 [Releases页面](https://github.com/autoclip/autoclip/releases) 下载对应平台的安装包：

- **macOS (Apple Silicon)**: `AutoClip-Desktop-1.0.0-arm64.dmg`
- **macOS (Intel)**: `AutoClip-Desktop-1.0.0-x64.dmg`
- **Windows**: `AutoClip-Desktop-1.0.0-x64.exe`
- **Linux**: `AutoClip-Desktop-1.0.0-x64.AppImage`

### 2. 安装应用

#### macOS
1. 双击下载的 `.dmg` 文件
2. 将 `AutoClip Desktop` 拖拽到 `Applications` 文件夹
3. 首次运行时，系统可能提示"无法验证开发者"，请：
   - 打开 `系统偏好设置` > `安全性与隐私`
   - 点击 `仍要打开` 按钮

#### Windows
1. 双击下载的 `.exe` 文件
2. 按照安装向导完成安装
3. 安装完成后，从开始菜单启动应用

#### Linux
1. 给AppImage文件添加执行权限：
   ```bash
   chmod +x AutoClip-Desktop-1.0.0-x64.AppImage
   ```
2. 双击运行，或从终端执行：
   ```bash
   ./AutoClip-Desktop-1.0.0-x64.AppImage
   ```

## 🎯 首次使用

### 1. 启动应用
- **macOS**: 从应用程序文件夹或Launchpad启动
- **Windows**: 从开始菜单或桌面快捷方式启动
- **Linux**: 双击AppImage文件或从应用程序菜单启动

### 2. 配置API密钥
1. 应用启动后，点击 `设置` 按钮
2. 在 `API配置` 标签页中，输入你的API密钥：
   - **通义千问**: 在阿里云控制台获取
   - **OpenAI**: 在OpenAI官网获取
   - **其他服务**: 根据提示配置
3. 点击 `测试连接` 验证配置
4. 点击 `保存配置`

### 3. 配置语音转写（可选）
1. 在设置页面，切换到 `语音转写配置` 标签
2. 选择语音识别服务：
   - **本地Whisper**: 免费，需要下载模型
   - **OpenAI API**: 准确度高，需要付费
   - **其他服务**: 根据需求选择
3. 配置相关参数并保存

## 🔧 故障排除

### 常见问题

#### 1. 应用无法启动
**症状**: 双击应用无反应或报错

**解决方案**:
- **macOS**: 检查系统版本是否满足要求，尝试右键点击应用选择"打开"
- **Windows**: 以管理员身份运行，检查Windows Defender是否阻止
- **Linux**: 检查是否有执行权限，尝试从终端运行查看错误信息

#### 2. 后端服务启动失败
**症状**: 应用启动但显示"后端服务未运行"

**解决方案**:
1. 检查端口8000是否被占用
2. 重启应用
3. 检查防火墙设置
4. 查看应用日志文件

#### 3. 视频处理失败
**症状**: 上传视频后处理失败

**解决方案**:
1. 检查视频格式是否支持（MP4、AVI、MOV等）
2. 确认API密钥配置正确
3. 检查网络连接
4. 尝试较小的视频文件

#### 4. 语音转写失败
**症状**: 字幕生成失败

**解决方案**:
1. 检查语音转写配置
2. 确认选择的模型已下载
3. 检查音频质量
4. 尝试不同的语音识别服务

### 日志文件位置

#### macOS
```
~/Library/Application Support/AutoClip/logs/
```

#### Windows
```
%APPDATA%/AutoClip/logs/
```

#### Linux
```
~/.local/share/AutoClip/logs/
```

### 获取帮助

如果遇到问题，请：

1. **查看日志文件**: 检查上述位置的日志文件
2. **重启应用**: 尝试完全关闭并重新启动
3. **检查系统要求**: 确认系统版本和硬件满足要求
4. **联系支持**: 在GitHub Issues中报告问题

## 📚 使用技巧

### 1. 性能优化
- 使用SSD存储提高处理速度
- 确保有足够的内存（推荐8GB+）
- 关闭其他占用资源的应用

### 2. 网络优化
- 使用稳定的网络连接
- 配置代理（如需要）
- 选择就近的API服务

### 3. 存储管理
- 定期清理临时文件
- 备份重要的项目数据
- 监控磁盘空间使用

## 🔄 更新应用

### 自动更新
应用会检查更新并提示用户下载新版本。

### 手动更新
1. 访问 [Releases页面](https://github.com/autoclip/autoclip/releases)
2. 下载最新版本的安装包
3. 按照安装步骤重新安装

## 📞 技术支持

- **GitHub Issues**: [报告问题](https://github.com/autoclip/autoclip/issues)
- **文档**: [查看完整文档](https://github.com/autoclip/autoclip/wiki)
- **社区**: [加入讨论](https://github.com/autoclip/autoclip/discussions)

---

**注意**: 本应用需要网络连接来使用AI功能。首次使用可能需要下载模型文件，请确保网络连接稳定。
