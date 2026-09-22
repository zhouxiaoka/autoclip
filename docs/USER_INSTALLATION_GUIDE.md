# 安装与第一次出片

[English](USER_INSTALLATION_GUIDE.en.md) · [返回首页](../README.md) · [排错指南](FAQ.md)

## 选择使用方式

| 环境 | 建议方式 |
| --- | --- |
| macOS · Apple Silicon（M 系列） | [下载桌面版](https://github.com/zhouxiaoka/autoclip/releases/latest)，选择名称含 `aarch64` 的 `.dmg` |
| Windows 10 / 11 · x64 | [下载桌面版](https://github.com/zhouxiaoka/autoclip/releases/latest)，选择名称含 `x64-setup.exe` 的安装包 |
| Intel Mac / Linux / 自建服务 | [Docker](../DOCKER.md) 或 [CLI](CLI_AND_MCP.md) |

以 Release 页面实际提供的安装包和系统要求为准。不要把源码压缩包 `Source code` 当作安装包。桌面版内置 Python 和 FFmpeg；本地语言模型、语音转写组件和模型文件需要另外准备。

处理大文件和运行本地模型需要额外内存与磁盘空间。空间预算应包含原视频、转写模型、临时文件、切片与导出结果；不承诺固定处理速度或最低配置下的效果。

## 安装桌面版

### macOS

打开 `.dmg`，将 AutoClip Desktop 拖到“应用程序”，再从“应用程序”打开。若系统阻止未公证版本，先确认安装包来自本仓库的 Releases，再按该 Release 的首次启动说明操作。不要为此关闭系统全局安全检查。

### Windows

运行 `x64-setup.exe` 并按向导安装。安装包按用户安装，无需常规使用管理员权限；缺少 WebView2 时，安装器可能需要联网下载。若系统拦截未签名版本，先确认下载来源，再参考 Release 中的提示。

## 第一次使用

1. **先配置模型。** 打开“设置”，选择通义千问、OpenAI 兼容接口、Gemini、硅基流动或本地模型。云端服务填写自己的 API Key 和模型名，点击测试连接，再保存。本地模型先在 Ollama / LM Studio 启动服务并加载模型。
2. **准备字幕。** 有时间轴准确的 `.srt` 就与视频一起导入。没有字幕时，在设置中的语音识别区域完成本地 Whisper 组件与模型准备；首次安装和下载需要网络。
3. **自备短样片。** 准备一段你有权使用、对白清楚的 3–5 分钟视频，最好同时带上时间轴准确的 `.srt`。在首页用「文件导入」导入视频及可选 SRT，或用「链接导入」粘贴 B 站 / YouTube 链接。素材要求与示例见下方「自备短样片」。
4. **查看处理结果。** 在项目详情检查片段起止时间、标题和评分，预览内容是否完整。若失败，按页面提示定位字幕、分析或导出阶段，参见 [FAQ](FAQ.md)。
5. **导出成片。** 使用详情页的导出入口，按发布平台选择预设。竖屏导出可加入字幕和标题卡；导出后先播放检查，再自行发布。

AI 分析主要依赖字幕文本。访谈、播客、课程等以语言表达为主的视频更容易评估；纯视觉动作、音乐或无对白内容不应期待同样的高光识别效果。

## 自备短样片

AutoClip 不托管官方样片。Release 里没有样片压缩包，也不提供成片下载。请使用自己的短视频，或你有权使用的公开平台链接。

- 时长约 3–5 分钟，对白清楚。
- 尽量带上时间轴准确的 `.srt`。没有字幕时，先在设置中准备本地 Whisper，或换一条已有字幕的视频。
- 来源可以是本地文件、B 站或 YouTube。请确认你有权使用该媒体。

示例链接，非官方托管 / Example link, not hosted by AutoClip：

- <https://www.youtube.com/watch?v=0YNeyBANrTI> — 示例 · 约 3 分钟口播；在 YouTube 打开中文字幕后导入（或先下载字幕为 SRT）。非 AutoClip 托管。

也可自选任意带字幕的 3–5 分钟公开访谈或口播（B 站或 YouTube），请确认你有权使用；我们不提供成片下载。

第一次出片的常见卡点见 [讨论 #128](https://github.com/zhouxiaoka/autoclip/discussions/128)。

## 云端与本地模型

| 方式 | 准备事项 |
| --- | --- |
| 云端 API | 服务商账号、可用 API Key、对应的模型访问权限与网络；调用费用由服务商收取 |
| Ollama | 启动 Ollama，运行 `ollama pull qwen2.5:7b`，在 AutoClip 选择 Ollama |
| LM Studio | 下载并加载模型，启动 Local Server，再在 AutoClip 选择实际可用的模型 |

本地预设不需要云端 API Key；本地硬件仍需承担推理开销。Whisper 负责语音转文字，语言模型负责分析字幕，二者需要分别配置。

## 更新与备份

关闭正在处理的任务并退出应用，备份数据目录后，从 [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) 获取新版安装包。v1.3.0 及以前需先手动安装 v1.3.1。自 v1.3.1 起，可在「设置 → 应用 → 检查更新」获取后续版本；确认后下载安装并重启。自动检查最多每天一次，手动下载仍然可用。

默认桌面数据目录：

| 平台 | 目录 |
| --- | --- |
| macOS | `~/Library/Application Support/AutoClip` |
| Windows | `%APPDATA%\AutoClip` |
| Linux / CLI | `~/.local/share/AutoClip` |

使用 CLI 自定义 `--data-dir` / `AUTOCLIP_DATA_DIR` 时，以实际配置目录为准。日志通常在数据目录的 `logs` 中。备份应同时包含项目文件、数据库和配置；这些配置可能含 API Key，应妥善保存。不要把卸载、删除数据库或清空数据目录作为常规排错步骤，也不要假设已有自动备份。

## 获取帮助

先看 [常见问题](FAQ.md) 和 [已知问题](https://github.com/zhouxiaoka/autoclip/issues/96)。第一次出片卡住（模型、没有字幕、系统警告）请到 [第一次出片问答](https://github.com/zhouxiaoka/autoclip/discussions/128)。欢迎说明和分类见 [欢迎与分类](https://github.com/zhouxiaoka/autoclip/discussions/127)。仍无法解决时，邮件提供系统、应用版本、模型、失败阶段、复现步骤和已脱敏日志。

个人业余维护，回复时间不固定，不提供即时客服或一对一部署服务。

邮箱：[christine_zhouye@163.com](mailto:christine_zhouye@163.com)
