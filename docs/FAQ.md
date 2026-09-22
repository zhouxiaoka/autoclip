# 常见问题与排错

[English](FAQ.en.md) · [安装指南](USER_INSTALLATION_GUIDE.md) · [返回首页](../README.md)

## 费用、模型与数据

### AutoClip 收费吗？必须有 API Key 吗？

AutoClip 本身免费、开源（MIT）。云端模型调用由你选择的服务商计费，价格、额度和可用模型以服务商为准。Ollama / LM Studio 本地预设无需云端 API Key，但需要下载模型并具备相应硬件；本地 Whisper 也需要单独安装组件和语音模型。

### 视频会上传吗？可以离线使用吗？

本地剪辑流程在你的设备上处理和保存视频。选择云端语言模型时，字幕文本会发送到该服务商；你主动使用发布上传功能时，视频会发送到所选平台。匿名使用统计和错误报告取决于版本、构建配置和设置，详见 [隐私说明](PRIVACY.md)。

准备好本地视频、语言模型及语音模型后，核心本地处理无需云端模型服务。视频下载、组件安装、模型下载和更新仍需要网络。不要把“本地处理”理解为所有功能都不联网。

### 哪些视频比较适合？

分析主要基于字幕，因此对白清楚的访谈、播客、课程、口播和直播回放比较合适。音乐、体育动作和其他主要依赖画面的内容，单靠字幕可能无法识别精彩点。没有固定出片数量或效果保证，建议先用短样本验证。

## 安装与启动

### 应该下载哪个文件？

[Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) 中，Apple Silicon Mac 选 `aarch64.dmg`，Windows x64 选 `x64-setup.exe`。Intel Mac / Linux 使用 Docker 或 CLI。以每次 Release 的实际资产为准，`Source code` 不是桌面安装包。

首次启动的系统提示请参考 [安装指南](USER_INSTALLATION_GUIDE.md) 和对应 Release。Windows 日常运行不需要管理员权限。

### 空白页、后端未启动或连接失败怎么办？

1. 完全退出后重新启动一次，保留数据目录。
2. 检查磁盘空间，记录界面上的具体错误和发生阶段。
3. 桌面后端端口由启动器管理，查看实际启动日志，不要假设一直是 8000。Docker 默认 Web 端口为 3000、API 端口为 8000。
4. Web 模式下若开启了浏览器网页翻译，先关闭翻译再刷新。
5. Docker 用户执行 `docker compose ps` 和 `docker compose logs --tail=100 autoclip celery-worker`，参见 [Docker 指南](../DOCKER.md)。

### 模型连接测试失败怎么办？

确认提供商、模型名、API Key、Base URL 与区域设置一致，账号拥有该模型权限。Ollama / LM Studio 要先启动服务并加载模型。本地服务默认地址分别是 `http://localhost:11434/v1` 和 `http://localhost:1234/v1`。

Docker 中的 `localhost` 是容器自己。宿主机模型服务的访问方式见 [Docker 指南](../DOCKER.md)。若出现代理、TLS 或超时错误，检查具体连接目标和网络配置；不要在反馈中粘贴完整 API Key。

## 字幕、分析与导出

### 没有字幕怎么办？支持什么字幕格式？

首页的本地上传入口支持可选 `.srt`。没有可用字幕时需要本地语音转写；先在设置中安装 Whisper 组件与模型。CLI 环境可安装 `faster-whisper`。其他字幕格式建议先转换为带正确时间轴的 SRT，不假设上传入口支持所有格式。

### 为什么没有生成片段？

先看项目错误提示，再按失败阶段排查：

| 阶段 | 优先检查 |
| --- | --- |
| 字幕 / SUBTITLE | 字幕是否为空、时间轴是否与视频对应、Whisper 是否就绪 |
| 分析 / ANALYZE | 模型连接是否成功、返回是否可解析、字幕是否有足够内容 |
| 评分 | 是否有候选片段、阈值是否过高；可尝试从 0.7 降到 0.5 后重新处理 |
| 导出 / EXPORT | FFmpeg 是否可用、磁盘是否充足、输出目录是否可写 |

CLI 可先检查环境，再用较低阈值验证：

```bash
autoclip doctor --provider ollama
autoclip run talk.mp4 --provider ollama --srt talk.srt --min-score 0.5 --json
```

把示例文件名和模型选项换成实际配置；没有 SRT 时去掉 `--srt talk.srt` 并确保转写已就绪。降低阈值只影响筛选，不保证一定有片段。

### 处理慢、内存不足怎么办？

先区分视频下载、转写、模型分析和 FFmpeg 导出哪个阶段慢。用短视频验证；关闭不必要的并发任务，尝试更小的本地模型，并检查可用内存与磁盘。转写模型首次下载可能耗时较长；重试前确认旧任务是否仍在运行。处理时间随硬件、时长、模型和导出设置变化，没有统一的“每小时视频几分钟”承诺。

### 下载 YouTube / B 站视频失败怎么办？

先确认链接可在浏览器打开、当前账号有权访问，必要时配置该平台的登录凭据。CLI / 源码环境可检查 yt-dlp 版本，桌面用户先检查新版本。也可以使用有权获取的本地文件继续处理。不要在 Issue 或邮件中发送 Cookies。

### 原始切片和发布导出有什么区别？

切片是根据时间范围从原视频生成的片段；发布导出会按预设进一步渲染，例如竖屏布局、烧录字幕和标题卡。生成切片后仍需执行导出，并播放检查结果。

```bash
autoclip export PROJECT_ID --preset shorts
```

`PROJECT_ID` 替换为真实项目 ID。其他预设包括 `douyin`、`xiaohongshu`、`bilibili` 和 `original`，详见 [CLI / MCP 指南](CLI_AND_MCP.md)。

## 更新、备份与反馈

### 数据存在哪里？如何备份？

桌面默认目录见 [安装指南](USER_INSTALLATION_GUIDE.md)。Docker 使用仓库下的 `data/`、`logs/`、`uploads/` 绑定目录。退出应用或停止服务后，备份数据库、项目文件与配置，避免运行中只复制 SQLite 主文件。不要依赖未经确认的自动备份，也不要为了排错删除原始数据。

### 哪里看已知问题？怎样联系？

先查 [已知问题](https://github.com/zhouxiaoka/autoclip/issues/96) 和 [版本记录](https://github.com/zhouxiaoka/autoclip/releases)。希望增加的能力、用法和模型发到 [Discussions](https://github.com/zhouxiaoka/autoclip/discussions)；能复现的故障开 Issue。规则见 [社区看板](COMMUNITY_BOARD.md)。仍需联系时，将以下信息一次性发到 [christine_zhouye@163.com](mailto:christine_zhouye@163.com)：

- 系统和 CPU 架构、AutoClip 版本、桌面 / Docker / CLI 使用方式。
- 模型提供商、模型名、视频来源与大致时长、是否提供字幕。
- 复现步骤、失败阶段、错误截图或最近的相关日志。
- 日志中移除 API Key、Cookies、私人路径和不希望公开的字幕内容。

个人业余维护，回复时间不固定，不提供即时客服或一对一部署服务。
