<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### 开源 AI 高光剪辑工具

导入长视频，AI 分析字幕、找出精彩片段，自动剪成短视频与合集。

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily?language=Python" alt="AutoClip — Trendshift Python daily ranking" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily" alt="AutoClip — Trendshift daily ranking, all languages" width="250" height="55"></a>
</p>

**[下载桌面版](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [快速开始](#快速开始) · [项目网站](https://zhouxiaoka.github.io/autoclip_intro/) · [使用文档](#文档) · [问题反馈](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

**简体中文** · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

</div>

适合访谈、播客、课程、口播与直播回放。提供桌面应用、Docker Web 界面和 CLI / MCP，可交互使用，也可批量处理。

## 界面预览

![导入视频与项目管理](docs/images/home-v1.4.0.png)

<table>
  <tr>
    <td width="50%" align="center"><strong>AI 切片结果</strong></td>
    <td width="50%" align="center"><strong>Studio 预览与修改</strong></td>
  </tr>
  <tr>
    <td><a href="docs/images/clips-v1.4.0.png"><img src="docs/images/clips-v1.4.0.png" alt="AI 切片结果" width="100%"></a></td>
    <td><a href="docs/images/studio-v1.4.0.png"><img src="docs/images/studio-v1.4.0.png" alt="Studio 预览与修改" width="100%"></a></td>
  </tr>
</table>

<sub>v1.4.0 界面实拍（含后续 Studio 修复）：导入视频、查看真实切片结果，再进入 Studio 修改成片。截图为中文界面，案例字幕与生成标题保留英文。</sub>

[截图版本与案例来源](docs/images/README.md)

## 特别感谢 ❤️

<table>
  <tr>
    <td align="center" width="140">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="88"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td>
      感谢 <strong>88API Token聚合平台</strong> 赞助 AutoClip！聚合 GPT、Claude、Gemini、Grok、DeepSeek、Kimi、GLM 等语言与编程模型，适合字幕分析、高光筛选与标题生成。<br>
      🎨 <strong>多媒体能力</strong>：平台提供 GPT-Image、Gemini、Grok 等图片模型，Seedance、Veo、MiniMax Hailuo H3、Kling、Grok 等视频模型，以及 Whisper、TTS 等语音能力；AutoClip 可接入兼容的分析、封面生图与字幕转写接口。<br>
      🏷️ <strong>服务与结算</strong>：据合作方介绍，由海外企业运营，提供人工客服、正规发票，充值比例 1:1；具体模型、服务与结算条件以平台页面为准。<br>
      🎁 <strong>新用户福利</strong>：通过 <a href="https://88api.ai/sign-up?aff=2PIc">专属推广链接注册</a>可获体验额度，用于测试模型能力，领取条件以活动页面为准。 <a href="docs/88API_SETUP.md">接入说明</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="88"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar.cc<br>无限星河</strong></a>
    </td>
    <td>
      感谢 <strong>Infistar.cc 无限星河</strong> 赞助 AutoClip！提供多模型 API 服务，适合长视频字幕分析、高光筛选与标题生成等工作流。<br>
      ⚙️ <strong>兼容接入</strong>：在 AutoClip 选择 OpenAI 兼容接口，填写 Base URL、API Key 和可用模型，即可配置使用。<br>
      🧩 <strong>多模型选择</strong>：合作方提供 Claude、GPT、Gemini、DeepSeek 等系列模型，可选择支持兼容接口的型号，对比字幕分析与高光筛选效果。<br>
      🏷️ <strong>价格与服务</strong>：据合作方介绍，部分模型低至官方定价的 <strong>0.1 折</strong>，支持人民币结算、开票及模型验真；具体型号、价格与服务条件以平台页面为准。<br>
      🎁 <strong>AutoClip 专属福利</strong>：通过 <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">专属推广链接注册</a>可领取 <strong>$5 体验额度</strong>，领取条件以活动页面为准。 <a href="docs/INFISTAR_SETUP.md">接入说明</a>
    </td>
  </tr>
</table>

## 功能特性

点击任意缩略图查看大图。

<table>
  <tr>
    <td width="50%" valign="top">
      <h4>多种导入方式</h4>
      <p>本地视频、YouTube 或 B 站链接，可附带 SRT 字幕；无字幕时可使用本地 Whisper 转写。</p>
      <a href="docs/images/feature-import.png"><img src="docs/images/feature-import.png" alt="多种导入方式" width="420"></a>
    </td>
    <td width="50%" valign="top">
      <h4>AI 内容分析</h4>
      <p>基于字幕生成大纲与话题时间线，为片段评分、提取标题。</p>
      <a href="docs/images/clips-v1.4.0.png"><img src="docs/images/clips-v1.4.0.png" alt="AI 内容分析" width="260"></a>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>片段与合集</h4>
      <p>自动生成切片，预览结果，并按需要调整合集顺序。</p>
      <a href="docs/images/feature-collections.png"><img src="docs/images/feature-collections.png" alt="片段与合集" width="420"></a>
    </td>
    <td width="50%" valign="top">
      <h4>多平台导出</h4>
      <p>提供抖音、小红书、YouTube Shorts 和 B 站预设，支持烧录字幕与标题卡。</p>
      <a href="docs/images/feature-export.png"><img src="docs/images/feature-export.png" alt="多平台导出" width="420"></a>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>封面与发布</h4>
      <p>自 v1.3.2 起支持自动封面、立即发布和定时发布；海外平台通过 Upload-Post 连接，B 站单独配置。</p>
      <a href="docs/images/feature-publish.png"><img src="docs/images/feature-publish.png" alt="封面与发布" width="200"></a>
      <a href="docs/images/feature-cover.png"><img src="docs/images/feature-cover.png" alt="封面与发布" width="200"></a>
      <p><sub>演示环境未连接发布账号；这里展示发布入口和封面设置，并非已发布结果。</sub></p>
    </td>
    <td width="50%" valign="top">
      <h4>发布管理</h4>
      <p>查看发布记录与月历，管理待发布任务；也可只下载成片。</p>
      <a href="docs/images/feature-calendar.png"><img src="docs/images/feature-calendar.png" alt="发布管理" width="420"></a>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>模型可选</h4>
      <p>支持通义千问、OpenAI 兼容接口、Gemini 等云端服务，以及 Ollama / LM Studio 本地模型。</p>
      <a href="docs/images/feature-models.png"><img src="docs/images/feature-models.png" alt="模型可选" width="420"></a>
    </td>
    <td width="50%" valign="top">
      <h4>批量与 Agent 工作流</h4>
      <p>用 CLI 编排批量任务，或通过 MCP 调用视频处理能力。</p>
      <a href="docs/images/feature-cli.png"><img src="docs/images/feature-cli.png" alt="批量与 Agent 工作流" width="420"></a>
      <p><sub>CLI / MCP 无图形界面：此图是实际命令帮助输出的展示页截图。</sub></p>
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center" valign="top">
      <h4>多语言界面</h4>
      <p>支持中、英、日、韩、西、葡、俄、法，可在顶栏切换或跟随系统；素材与生成内容保留原文。</p>
      <a href="docs/images/feature-languages.png"><img src="docs/images/feature-languages.png" alt="多语言界面" width="420"></a>
      <p><sub>英文界面与语言选择菜单；素材和生成内容保持原语言。</sub></p>
    </td>
  </tr>
</table>

<details>
<summary>查看发布平台、账号要求与导出细节</summary>

海外发布使用你自己的 Upload-Post 账号，支持平台以账号实际连接情况为准，包括 TikTok、Instagram、YouTube、Facebook、LinkedIn、X、Threads、Pinterest、Bluesky、Discord 和 Google Business。B 站在设置中单独填写 Cookie（包含 SESSDATA、bili_jct、DedeUserID），支持一个账号。

在切片页面打开发布，可立即发布或定时发布。标题和描述可不填，默认使用片段标题；字幕烧录和约 4 秒的片头标题卡默认开启。可见范围在平台支持时默认「仅自己」，其中 TikTok、YouTube、B 站支持 private / 仅自己。封面与标题卡行为以所用版本的 Release 说明为准。

竖屏账号导出为 9:16，不按 60 秒截断；只发 B 站用横屏，只有 LinkedIn、X 这类横屏账号时保留原画。竖屏平台与 B 站同次发布时分别渲染。

项目页提供发布记录和月历，可取消待发布排期。「排这一周」安排在周一、周三、周五 09:00，仅用于海外平台，不包含 B 站。

</details>


> 导入视频 → 字幕 / 语音转写 → AI 分析 → 片段与合集 → 导出 / 发布

## 快速开始

| 你的使用场景 | 建议方式 | 准备事项 |
| --- | --- | --- |
| 在电脑上剪辑视频 | **桌面版** | macOS Apple Silicon 或 Windows x64 |
| 自建 Web 服务 / Linux | **Docker** | Docker 与 Compose v2 |
| 批量处理 / 接入 Agent | **CLI / MCP** | Python 3.10+（建议 3.11）与 FFmpeg |

### 桌面版：第一次出片

1. **下载安装。** 前往 [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest)：macOS Apple Silicon 选 `.dmg`，Windows 10 / 11 x64 选 `-setup.exe`。桌面版内置 Python 和 FFmpeg；Intel Mac / Linux 可使用 Docker 或 CLI。实际系统要求以对应 Release 为准。
2. **配置模型。** 在设置中选择服务商，填写 API Key 与模型名，测试连接后保存；使用本地模型时，先启动 Ollama 或 LM Studio。
3. **导入视频。** 建议先用 3–5 分钟短样片，可同时导入 SRT。无字幕时先在设置中准备本地 Whisper 组件与语音模型。
4. **预览并导出。** 检查片段起止时间、标题和内容完整性，选择导出预设，或连接账号后发布。

[完整安装与首次使用指南](docs/USER_INSTALLATION_GUIDE.md) · [遇到问题？](docs/FAQ.md)

<details>
<summary><strong>Docker / Web 部署</strong></summary>

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

</details>

<details>
<summary><strong>CLI / MCP 安装与使用</strong></summary>

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

在 MCP 客户端中将 `command` 设为虚拟环境里 `autoclip` 的绝对路径，`args` 设为 `["mcp"]`。opencode 用户一条命令即可接入：`autoclip mcp install opencode`（见 [OpenCode 接入](docs/OPENCODE.md)）。详见 [CLI / MCP 指南](docs/CLI_AND_MCP.md)（中文）和 [Agent skill](skills/autoclip/SKILL.md)（中文）。

</details>

## 模型配置

| 方式 | 配置 |
| --- | --- |
| 云端 API | 在设置中选择服务商，填写自己的 API Key 和模型名。OpenAI 兼容服务还可配置 Base URL。 |
| Ollama | 默认地址 `http://localhost:11434/v1`，默认模型 `qwen2.5:7b`，无需 API Key。 |
| LM Studio | 加载模型并启动 Local Server，默认地址 `http://localhost:1234/v1`，选择服务实际提供的模型。 |

Docker 访问宿主机模型服务时，`localhost` 指向容器自身，需要改为容器可访问的宿主机地址。视频剪辑在本地进行；云端字幕分析会向所选服务商发送字幕文本，下载视频与模型仍需要网络。

[模型配置指南](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [本地模型与容器配置](docs/CLI_AND_MCP.md) · [Infistar 接入](docs/INFISTAR_SETUP.md)

## 常见问题

<details>
<summary>需要付费或 API Key 吗？</summary>

AutoClip 免费、开源（MIT）。云端模型由所选服务商计费，需要自己的 API Key；Ollama / LM Studio 本地预设无需云端 Key，但需要模型和相应硬件。自 **v1.3.2** 起，海外发布需要你自己的 [Upload-Post](https://www.upload-post.com) 账号。免费档、付费档，以及 TikTok、YouTube、Instagram 等的每日额度，以 Upload-Post 自己的页面为准，不是 AutoClip 的承诺。

</details>

<details>
<summary>我的视频会上传吗？</summary>

剪辑留在你的设备上。使用云端模型时，字幕文本会发送给该服务商。成片只有在你点「发布」之后才会离开这台机器，发到你已连接的平台；也可以只下载、不发布。统计与错误报告取决于版本和设置，详见隐私说明。

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

素材准备和公开链接示例见 [第一次出片指南](docs/USER_INSTALLATION_GUIDE.md#自备短样片)。

</details>

[完整排错指南](docs/FAQ.md) · [已知问题](https://github.com/zhouxiaoka/autoclip/issues/96)

## 文档

| 你想了解 | 文档 |
| --- | --- |
| 安装与首次出片 | [安装指南](docs/USER_INSTALLATION_GUIDE.md) |
| 自建服务与自动化 | [Docker 部署](DOCKER.md) · [CLI / MCP](docs/CLI_AND_MCP.md) · [Agent skill](skills/autoclip/SKILL.md) · [OpenCode 接入](docs/OPENCODE.md) |
| 配置模型与排错 | [模型配置](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [常见问题](docs/FAQ.md) |
| 版本与隐私 | [更新日志](CHANGELOG.md) · [隐私说明](docs/PRIVACY.md) |
| 参与开发与翻译 | [贡献指南](CONTRIBUTING.md) · [翻译维护](docs/i18n.md) |

README 提供八种语言，深入文档以中文为主；安装与排错指南另有英文版本。

## 参与贡献与联系

欢迎提交修复、使用反馈和翻译改进。如果 AutoClip 帮到了你，欢迎给项目一个 Star。

- **提问与交流**：[GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [第一次出片问答](https://github.com/zhouxiaoka/autoclip/discussions/128) · [分享想法](https://github.com/zhouxiaoka/autoclip/discussions/129)。
- **报告故障**：使用 [Issue 模板](https://github.com/zhouxiaoka/autoclip/issues/new/choose)，附上系统、版本、所选模型、复现步骤与已脱敏日志。
- **合作联系**：[christine_zhouye@163.com](mailto:christine_zhouye@163.com)。

个人业余维护，回复时间不固定，不提供即时客服或一对一部署服务。提问前请先查看 [FAQ](docs/FAQ.md) 与 [已知问题](https://github.com/zhouxiaoka/autoclip/issues/96)；社区分类见 [欢迎说明](https://github.com/zhouxiaoka/autoclip/discussions/127) 和 [社区看板](docs/COMMUNITY_BOARD.md)。

感谢 FastAPI、React、Tauri、FFmpeg、yt-dlp、Whisper，以及所有贡献者。项目采用 [MIT License](LICENSE)。

<details>
<summary>社区成就与 Star History</summary>

以下徽章由 Trendshift 提供，点击可查看 AutoClip 的上榜记录。GitHub Trending 与 Trendshift 是不同榜单；徽章展示平台记录的成就，不代表当前实时排名。

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)

</details>
