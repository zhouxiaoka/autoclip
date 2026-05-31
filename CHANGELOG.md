# 更新日志

本文档记录了AutoClip项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 新增
- 添加视频标题编辑功能
- 支持B站多账号管理
- 添加账号健康状态监控
- 实现拖拽排序功能
- 添加视频分类支持
- 完善Docker部署支持
- 添加Docker管理脚本

### 开发中
- B站上传功能（预计下个版本发布）
- 字幕编辑功能（预计下个版本发布）

## [1.1.0] - 2026-05-31

> 让 macOS 桌面客户端真正可装、可用、能出片。

### 新增
- 🖥️ 桌面客户端零依赖安装：内置便携 Python 运行时 + 静态 ffmpeg/ffprobe，用户无需预装 Python/ffmpeg
- 🗣️ 本地字幕转写（按需安装）：无字幕视频可在「设置 → 语音转写」一键安装 faster-whisper 并自选模型

### 修复
- 修复桌面应用启动黑屏（前端 vendor chunk 加载顺序导致 React 未挂载）
- 修复项目列表一直「加载中」（运行时缺少 pytz 等依赖导致接口 500）
- 修复导入/重试时「重试失败 / 已开始重试」提示疯狂弹窗的循环
- 修复处理一直卡在 0%「初始化中」（桌面模式流水线改为本地执行，不再依赖 Redis）
- 修复换机后无法处理视频（内置 ffmpeg 改为静态自包含版本并正确接入后端）

### 改进
- AI 提供商 Gemini 迁移到官方新版 `google-genai` SDK
- CI 桌面构建统一为一条经过验证的流程（python-build-standalone）
- 仓库清理：移除大量历史脚本与一次性文档，整理项目结构

## [1.0.0] - 2024-01-15

### 新增
- 🎬 支持YouTube视频下载
- 🎬 支持B站视频下载
- 🎬 支持本地文件上传
- 🤖 AI智能视频分析
- ✂️ 自动视频切片
- 📚 智能合集生成
- 🎨 现代化Web界面
- 🚀 异步任务处理
- 📊 实时进度监控
- 🔐 B站账号管理
- 📱 响应式设计
- 🛠️ 一键启动脚本

### 技术特性
- FastAPI后端框架
- React + TypeScript前端
- Celery异步任务队列
- Redis消息代理
- SQLite数据库
- WebSocket实时通信
- 通义千问AI集成

## [0.9.0] - 2024-01-01

### 新增
- 基础项目架构
- 核心API接口
- 基础前端界面
- 视频处理流水线
- AI分析服务

### 技术栈
- Python 3.8+
- React 18
- FastAPI
- Celery
- Redis
- SQLite

---

## 版本说明

### 版本号格式

我们使用语义化版本控制 (SemVer)：

- **主版本号**: 不兼容的API修改
- **次版本号**: 向下兼容的功能性新增
- **修订号**: 向下兼容的问题修正

### 变更类型

- **新增**: 新功能
- **改进**: 现有功能的改进
- **修复**: Bug修复
- **移除**: 移除的功能
- **安全**: 安全相关的修复

### 链接

- [Unreleased]: https://github.com/your-username/autoclip/compare/v1.0.0...HEAD
- [1.0.0]: https://github.com/your-username/autoclip/releases/tag/v1.0.0
- [0.9.0]: https://github.com/your-username/autoclip/releases/tag/v0.9.0
