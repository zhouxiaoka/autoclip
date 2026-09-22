<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="80" height="80">

# AutoClip

**把长视频变成值得分享的精彩片段。**

**简体中文** · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/forks)
[![GitHub issues](https://img.shields.io/github/issues/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/issues)
[![License: MIT](https://img.shields.io/github/license/zhouxiaoka/autoclip?style=flat-square)](LICENSE)

[项目网站](https://zhouxiaoka.github.io/autoclip_intro/) · [讨论](https://github.com/zhouxiaoka/autoclip/discussions) · [反馈问题](https://github.com/zhouxiaoka/autoclip/issues)

**桌面安装包: [macOS · Apple Silicon](https://github.com/zhouxiaoka/autoclip/releases/latest) · [Windows · x64](https://github.com/zhouxiaoka/autoclip/releases/latest)**

[安装与第一次出片](docs/USER_INSTALLATION_GUIDE.md) · [完整排错指南](docs/FAQ.md)

</div>

自 v1.3.1 起，产品界面、官网和 README 均支持中、英、日、韩、西、葡、俄、法。顶栏可切换界面语言或跟随系统；用户素材和生成内容保留原文。

AutoClip 用 AI 分析视频字幕、定位高光、生成标题，并自动剪出片段与合集。适合访谈、播客、课程和直播回放，提供桌面应用、Docker Web 界面和 CLI / MCP 三种使用方式。

## 界面预览

![AutoClip v1.3.0 — local video import](docs/images/import-local.jpg)

v1.3.0 真实 Web 界面：在文件导入区添加本地视频，可同时提供 SRT 字幕。

## 社区成就

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily?language=Python" alt="AutoClip — Trendshift Python daily ranking" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily" alt="AutoClip — Trendshift daily ranking, all languages" width="250" height="55"></a>
</p>

以下徽章由 Trendshift 提供，点击可查看 AutoClip 的上榜记录。GitHub Trending 与 Trendshift 是不同榜单；徽章展示平台记录的成就，不代表当前实时排名。

## 你可以做什么

| 能力 | 说明 |
| --- | --- |
| 导入素材 | 支持本地视频、YouTube 与 B 站链接，可附带 SRT 字幕。 |
| 发现高光 | 从字幕提取大纲、话题时间线、精彩度评分和片段标题。 |
| 剪辑与合集 | 自动生成视频切片，组合推荐合集，也可手动调整顺序。 |
| 发布导出 | 提供抖音、小红书、YouTube Shorts 和 B 站导出预设，支持烧录字幕与标题卡。 |
| 自由选择模型 | 支持通义千问、OpenAI 兼容接口、Gemini、硅基流动，以及 Ollama / LM Studio 本地模型。 |
| 接入自动化 | 通过 CLI 批量编排，或让支持 MCP 的客户端调用同一条处理流水线。 |

> 导入视频 → 准备字幕 / 语音转写 → AI 分析与评分 → 生成切片与合集 → 导出成片

## 快速开始

### 1. 桌面版

从 [GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) 下载适合你的安装包：

| 平台 | 安装方式 |
| --- | --- |
| macOS · Apple Silicon | `.dmg` |
| Windows 10 / 11 · x64 | `-setup.exe` |
| Intel Mac / Linux | 使用下方 Docker 或 CLI |

桌面安装包内置 Python 和 FFmpeg。实际支持的平台与首次启动说明以对应 Release 为准。安装后先在设置中选择模型提供商、测试连接并保存，再导入视频。

### 2. Docker / Web

需要 Docker 和 Docker Compose v2。以下命令在仓库根目录执行：

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
```

```bash
cp env.example .env
```

启动前编辑 `.env`：选择 `LLM_PROVIDER`，填写对应服务的 API Key 和模型名；也可以启动后在设置页配置。

```bash
mkdir -p data logs uploads
docker compose up -d --build
```

打开 [Web 界面](http://localhost:3000)；[API 文档](http://localhost:8000/docs) 在后端启动后可用。部署细节见 [Docker 指南](DOCKER.md)（中文）。

Linux 上若绑定目录出现权限错误，先执行以下命令修正项目数据目录的归属，再重新启动服务：

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

### 3. CLI / MCP

需要 Python 3.10+（建议 3.11）和 PATH 中可用的 FFmpeg。以下安装示例使用 macOS / Linux shell；Windows PowerShell 用 `venv\Scripts\Activate.ps1` 激活虚拟环境。CLI 本地处理不需要 Redis。

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
```

本地模型示例：先安装并启动 Ollama，再下载模型。无字幕视频需要 `faster-whisper`，首次转写会下载语音模型；已有字幕可用 `--srt talk.srt`。

```bash
ollama pull qwen2.5:7b
python -m pip install faster-whisper
autoclip doctor --provider ollama
autoclip run talk.mp4 --provider ollama --json
```

把 `PROJECT_ID` 替换为处理结果中的项目 ID，即可导出 Shorts 格式；用 `autoclip mcp` 启动 stdio MCP 服务：

```bash
autoclip export PROJECT_ID --preset shorts
autoclip mcp
```

在 MCP 客户端中将 `command` 设为虚拟环境里 `autoclip` 的绝对路径，`args` 设为 `["mcp"]`。详见 [CLI / MCP 指南](docs/CLI_AND_MCP.md)（中文）和 [Agent skill](skills/autoclip/SKILL.md)（中文）。

## 模型配置

| 方式 | 配置 |
| --- | --- |
| 云端模型 | 在设置中选择通义千问、OpenAI 兼容接口、Gemini 或硅基流动，填写 API Key；兼容接口可配置 Base URL。 |
| Ollama | 服务地址默认为 `http://localhost:11434/v1`，默认模型 `qwen2.5:7b`，无需 API Key。 |
| LM Studio | 加载模型并启动 Local Server，默认地址 `http://localhost:1234/v1`，选择服务实际提供的模型。 |

Docker 访问宿主机模型服务时，`localhost` 指向容器自身；需配置容器能访问的宿主机地址。详见 CLI / MCP 指南。视频剪辑在本地进行，云端模型分析会向所选服务发送字幕文本；下载视频与模型仍需要网络。

## 常见问题

<details>
<summary>需要付费或 API Key 吗？</summary>

AutoClip 本身免费、开源（MIT）。云端模型由所选服务商计费，需要自己的 API Key；Ollama / LM Studio 本地预设无需云端 Key，但需要模型和相应硬件。

</details>

<details>
<summary>我的视频会上传吗？</summary>

本地剪辑在你的设备上完成；使用云端模型时，字幕文本会发送给该服务商。主动使用发布上传功能时，视频会发送到目标平台。统计与错误报告取决于版本和设置，详见隐私说明。

</details>

<details>
<summary>没有字幕也能使用吗？</summary>

可以，需要先准备本地 Whisper 组件和语音模型。已有字幕时可同时导入 SRT；准确字幕通常能减少转写等待和识别错误。

</details>

<details>
<summary>为什么没有生成片段？</summary>

先检查失败阶段：字幕是否为空、模型连接是否成功、评分阈值是否过高，以及 FFmpeg 和磁盘是否正常。可以尝试把评分阈值从 0.7 降到 0.5，但不保证一定有片段。

</details>

<details>
<summary>什么视频更适合？处理要多久？</summary>

当前分析主要基于字幕，适合访谈、播客、课程和口播。纯视觉动作或音乐类视频效果可能有限。耗时取决于时长、硬件、模型与导出设置，建议先用自备的 3–5 分钟短样片验证。

也可以任选下面一条，不必三条都跑。多为英语对白，可开官方字幕或自备 SRT/Whisper。示例·非托管·自担使用权。10 分钟以内的冷启动优先整段使用 Stanford 短访谈。

- 近期访谈：[Sam Altman on Astra, AGI, and the future of OpenAI](https://www.youtube.com/watch?v=VeizK1M7V7E)。第三方访谈（Sources Podcast，非 OpenAI 官方频道）；约 68 分钟（2026-09）。第一次只导前 5–8 分钟。多为英语对白，可开官方字幕或自备 SRT/Whisper。示例·非托管·自担使用权。
- 冷启动优先：[Stanford ENERGY · Jackie Dowling | Stanford Energy Fellow](https://www.youtube.com/watch?v=dtmjLzOtx8I)（约 3 分 47 秒，可整段导入）
- 播客：[YC · The State of Startups in 2026](https://www.youtube.com/watch?v=yslXlV2BP_Y)（Y Combinator 官方，约 36 分钟，2026-09）。第一次只导前 5–8 分钟。

</details>

[完整排错指南](docs/FAQ.md) · [已知问题](https://github.com/zhouxiaoka/autoclip/issues/96)

## 文档

README 提供八种语言；以下深入文档目前以中文为主。README 翻译语言不代表应用界面或转写模型支持的语言范围。

- [安装与第一次出片](docs/USER_INSTALLATION_GUIDE.md)
- [Docker 部署（中文）](DOCKER.md)
- [CLI、MCP 与本地模型（中文）](docs/CLI_AND_MCP.md)
- [模型提供商配置（中文）](docs/MULTI_LLM_PROVIDER_GUIDE.md)
- [常见问题（中文）](docs/FAQ.md)
- [贡献指南（中文）](CONTRIBUTING.md)
- [更新日志](CHANGELOG.md)
- [隐私说明（中文 / English）](docs/PRIVACY.en.md)
- [README 翻译与徽章维护（中文）](docs/i18n.md)

## 参与贡献与联系

欢迎提交修复、使用反馈和翻译改进。报告问题时请附上系统、版本、所选模型、复现步骤及已脱敏的错误日志。

个人业余维护，回复时间不固定，不提供即时客服或一对一部署服务。联系前请先查看常见问题与已知问题。

想法、用法和模型讨论走 [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions)，不要为此开 Issue。能复现的故障用 [Issue 模板](https://github.com/zhouxiaoka/autoclip/issues/new/choose)。看板规则见 [社区看板](docs/COMMUNITY_BOARD.md)。

- [欢迎与分类](https://github.com/zhouxiaoka/autoclip/discussions/127)
- [第一次出片问答](https://github.com/zhouxiaoka/autoclip/discussions/128)
- [想法](https://github.com/zhouxiaoka/autoclip/discussions/129)

- 邮箱: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

感谢 FastAPI、React、Tauri、FFmpeg、yt-dlp、Whisper，以及所有贡献者。项目采用 [MIT License](LICENSE)。如果 AutoClip 帮到了你，欢迎给项目一个 Star。

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)
