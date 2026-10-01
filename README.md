<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### 一个链接，一键出片

开源、免费、在你的电脑上运行。贴一个链接，花一两毛钱，拿到 <b>10+ 条高质量成片</b>，<br>每条都配好封面、标题、简介和话题，直接发抖音、小红书、TikTok、Reels、YouTube Shorts。<br>不用剪辑器，也不用跟 AI 来回对话。

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![Downloads](https://img.shields.io/github/downloads/zhouxiaoka/autoclip/total?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

**[下载桌面版](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [案例库](https://zhouxiaoka.github.io/autoclip_intro/cases/) · [快速开始](#快速开始) · [文档](#文档) · [问题反馈](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

**简体中文** · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

</div>

## 真实成片

<a href="https://zhouxiaoka.github.io/autoclip_intro/cases/"><img src="docs/images/v2/demo-wall.webp" alt="AutoClip 自动生成的竖屏成片：小红书访谈式、TikTok 播客式、抖音访谈式、Shorts 播客式" width="100%"></a>

每个原片只贴了一个链接。上面每一条都是 AutoClip 自动挑片、取景、翻译、包装后的原样输出，没有人工修改。**[到官网案例库带声音看 →](https://zhouxiaoka.github.io/autoclip_intro/cases/)**

每条成片按目标平台交付一整套：竖屏视频、封面、标题、简介和话题，可以直接发布。案例库持续更新，欢迎[投稿你的成片](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell)。

<sub>原片版权归原作者，仅作效果展示：[Dwarkesh Patel — Dario Amodei](https://www.youtube.com/watch?v=n1E9IZfvGMA) · [Y Combinator — Sam Altman](https://www.youtube.com/watch?v=ZIaOBAjvc38) · [WIRED — Hideo Kojima](https://www.youtube.com/watch?v=02Ah5VQrzvA)</sub>

## 又快，又便宜

一个链接进去，**10+ 条高质量成片**出来，每条都带封面、标题、简介和话题。一条 **1 小时 43 分钟**的访谈，从贴链接到 10 条成片用了 **7.5 分钟**，全部模型费用 **¥0.09**。2–3 小时的访谈，模型费用通常在 ¥0.1–0.2；多一条备选或多一个平台，大约再多 ¥0.005。

| 视频 | 流程 | 链接到出片 | 片段 → 自动出片 | 模型调用 | Tokens（入 / 出） | 模型费用 |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| MrBeast · 2h06m（英 → TikTok） | 旧版 | 65 分钟 | 33 → 33 | 194 | 53.1 万 / 10.6 万 | ¥0.64 |
| Karpathy · 2h26m（英 → 抖音） | 过渡版 | 34 分钟 | 25 → 25 | 53 | 14.3 万 / 2.5 万 | ¥0.16 |
| **Jensen Huang · 1h43m（英 → 小红书）** | **新版 · 作者字幕** | **7.5 分钟** | **21 → 10** | **34** | **7.7 万 / 1.2 万** | **¥0.09** |
| TIM × 罗永浩 · 2h52m（中 → 抖音） | 新版 · 无字幕 | 29.5 分钟 | 18 → 10 | 32 | 22.2 万 / 1.1 万 | ¥0.20 |

时间花在哪：旧版光挑片段就要 35 分钟（4 步、128 次调用依次执行），新版 25–40 秒。没有作者字幕的视频，语音识别在本地完成，用时会长一些（TIM 这条 23 分钟），视频同样不离开你的电脑。

<details>
<summary>测试条件与这一版改了什么</summary>

2026 年 10 月 1 日在同一台 Apple Silicon Mac 上实测，分析模型 qwen-plus（每百万 tokens 输入 ¥0.8、输出 ¥2，按阿里云百炼第三方汇总价估算，以官网为准），费用只含模型调用；语音识别为本地 Whisper base。四条是不同的视频。

Jensen 这条 7.5 分钟的构成：下载约 1 分钟；语音识别 0（直接用作者字幕）；挑片 25 秒、2 次调用；切点精修 + 取景 + 包装约 2.5 分钟；渲染 10 条约 3 分钟（每条约 18 秒，硬件编码）。

- **一次挑片**：整段字幕一次交给模型，直接返回片段、标题、理由和分数。原来按 5000 字分块、每块跑「大纲 → 时间线 → 评分 → 标题」四步，一条两小时视频要上百次调用。
- **并行调用**：各步骤的模型调用同时执行；包装也并行。
- **作者字幕直用**：YouTube 有作者上传的字幕时跳过本地语音识别。
- **硬件编码**：macOS VideoToolbox，Windows NVENC / QSV / AMF，CPU 占用约降到四分之一，不可用时自动改用软件编码。
- **按需渲染**：默认只做评分最高的 10 条，其余列为备选，点一下再做。

</details>

## 能做什么

- **一键出片，不用编辑器也不用对话**：贴一个链接，选好要发的平台（抖音、小红书、TikTok、Reels、YouTube Shorts、B 站、YouTube），按每个平台的画幅、时长和包装直接生成可发布成片。之后可以追加平台，失败的单条可以重试。
- **整套发布包**：每条成片附带按平台规则写好的标题、简介和话题，以及与视频风格一致的封面，可以一键复制文案或打包下载。
- **两套包装模板**：抖音 / 小红书用「访谈式」，上方两行标题、4:3 说话人窗口、中英双语字幕、名牌与编辑点评标签；TikTok / Reels / Shorts 用「播客式」，全屏跟随说话人、逐词高亮字幕、开头一句 hook。
- **外语素材自动翻译**：英文访谈发抖音，自动配中文标题和双语字幕；原片自带字幕时保留完整画面。
- **按内容情绪换风格**：模型判断每段的情绪（冷静、严肃、强观点、真诚、轻松），从 7 套配色和多种字幕动效里挑。
- **跟着说话人取景**：竖屏按镜头识别人物，主持人和嘉宾切换时画面跟着说话的人走；PPT、引用卡这类镜头自动改为完整画面。
- **切点自然**：片段从问题或观点的第一句开始，到回答讲完、说话人明显停顿时结束，不带进下一个问题。
- **还能自己改**：在编辑器里调整起止、文字和画幅，导出或直接发布到已连接的平台，也可以只下载。
- **模型自选，本地运行**：Qwen、DeepSeek、GPT、Gemini、Kimi、GLM 等云端模型，或本地 Ollama / LM Studio。剪辑和渲染都在你的电脑上。
- **CLI / MCP**：批量处理、接入脚本，或交给 Claude、Cursor、opencode 等 Agent 调用。

## 和云端订阅工具相比

| | AutoClip | 按月订阅的云端工具 |
| --- | --- | --- |
| 费用 | 软件免费；模型按量付费，一条 2–3 小时访谈 ¥0.1–0.2 | 按月订阅，按处理时长计额度 |
| 视频在哪处理 | 你的电脑；云端模型只收到字幕文本 | 上传到服务商的云端 |
| 模型 | 自选，或用本地模型 | 平台指定 |
| 中文平台 | 抖音、小红书、B 站专属模板 | 以海外平台为主 |
| 代码 | MIT 开源，可改、可自部署 | 闭源 |

<sub>右栏按同类云端产品 2026 年 10 月的公开页面整理，具体以各产品最新说明为准。</sub>

## 快速开始

| 你的使用场景 | 建议方式 | 准备事项 |
| --- | --- | --- |
| 在电脑上出片 | **桌面版** | macOS Apple Silicon 或 Windows x64 |
| 自建 Web 服务 / Linux | **Docker** | Docker 与 Compose v2 |
| 批量处理 / 接入 Agent | **CLI / MCP** | Python 3.10+（建议 3.11）与 FFmpeg |

### 桌面版

1. **下载安装**：在 [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) 下载。macOS Apple Silicon 选 `.dmg`，Windows 10 / 11 x64 选 `-setup.exe`。安装包自带 Python 和 FFmpeg。
2. **配置模型**：在设置里选一家服务商，填好 API Key，分析模型会自动选好；用本地模型时先启动 Ollama 或 LM Studio。
3. **贴链接，选平台**：建议先用一条 10–30 分钟、有字幕的访谈或播客。没有字幕时，在设置里准备本地 Whisper 或 SenseVoice。
4. **拿成片**：先看自动生成的 10 条，需要的话在编辑器里改，再下载或发布。

安装包还没有做 Apple 公证和 Windows 代码签名：macOS 第一次请右键应用选「打开」，Windows 在 SmartScreen 里选「更多信息 → 仍要运行」。

[完整安装与首次使用指南](docs/USER_INSTALLATION_GUIDE.md) · [遇到问题？](docs/FAQ.md)

<details>
<summary><strong>Docker / Web 部署</strong></summary>

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env          # 选择 LLM_PROVIDER，填 API Key 和模型名；也可以启动后在设置页配置
mkdir -p data logs uploads
docker compose up -d --build
```

打开 [Web 界面](http://localhost:3000)；[API 文档](http://localhost:8000/docs) 在后端启动后可用。部署细节见 [Docker 指南](DOCKER.md)。

Linux 上若绑定目录出现权限错误，先修正数据目录的归属再启动：

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

</details>

<details>
<summary><strong>CLI / MCP</strong></summary>

需要 Python 3.10+（建议 3.11）和 PATH 中可用的 FFmpeg。CLI 本地处理不需要 Redis。

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
python3 -m venv venv && source venv/bin/activate   # Windows PowerShell：venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
```

```bash
ollama pull qwen2.5:7b
python -m pip install faster-whisper                # 无字幕视频需要；已有字幕可用 --srt talk.srt
autoclip doctor --provider ollama
autoclip run talk.mp4 --provider ollama --json
autoclip export PROJECT_ID --preset shorts
autoclip mcp                                        # stdio MCP 服务
autoclip mcp install opencode                       # opencode 一条命令接入
```

在 MCP 客户端中把 `command` 设为虚拟环境里 `autoclip` 的绝对路径，`args` 设为 `["mcp"]`。详见 [CLI / MCP 指南](docs/CLI_AND_MCP.md)、[OpenCode 接入](docs/OPENCODE.md) 和 [Agent skill](skills/autoclip/SKILL.md)。

</details>

## 模型配置

| 方式 | 配置 |
| --- | --- |
| 云端 API | 在设置中选择服务商，填写自己的 API Key。OpenAI 兼容服务还可配置 Base URL。 |
| Ollama | 默认地址 `http://localhost:11434/v1`，默认模型 `qwen2.5:7b`，无需 API Key。 |
| LM Studio | 加载模型并启动 Local Server，默认地址 `http://localhost:1234/v1`。 |

Docker 访问宿主机模型服务时，`localhost` 指向容器自身，需要改为容器可访问的宿主机地址。

[模型配置指南](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [本地模型与容器配置](docs/CLI_AND_MCP.md)

## 赞助伙伴

感谢以下伙伴赞助 AutoClip。两家都提供 OpenAI 兼容接口，可在设置里直接选择，填好 Key 后自动列出可用模型。

<table>
  <tr>
    <td align="center" width="140">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="72"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td>
      Token 聚合平台，提供 GPT、Claude、Gemini、Grok、DeepSeek、Kimi、GLM 等模型，以及图片、视频与语音能力。人工客服、正规发票，充值 1:1。通过<a href="https://88api.ai/sign-up?aff=2PIc">专属链接注册</a>可获体验额度。<a href="docs/88API_SETUP.md">接入说明</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="72"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar 无限星河</strong></a>
    </td>
    <td>
      多模型 API 服务，提供 Claude、GPT、Gemini、DeepSeek 等系列，部分模型低至官方定价的 0.1 折，支持人民币结算、开票及模型验真。通过<a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">专属链接注册</a>可领 $5 体验额度。<a href="docs/INFISTAR_SETUP.md">接入说明</a>
    </td>
  </tr>
</table>

<sub>服务、价格与福利信息由合作方提供，以平台页面为准。</sub>

## 常见问题

<details>
<summary>需要付费或 API Key 吗？</summary>

AutoClip 免费、开源（MIT）。云端模型由所选服务商按量计费，需要自己的 API Key，实测一条 1 小时 43 分钟的访谈约 ¥0.09；Ollama / LM Studio 本地模型无需云端 Key，但需要相应硬件。海外发布需要你自己的 [Upload-Post](https://www.upload-post.com) 账号。

</details>

<details>
<summary>我的视频会上传吗？</summary>

剪辑与渲染留在你的设备上。使用云端模型时，字幕文本会发送给该服务商。成片只有在你点「发布」之后才会离开这台机器，发到你已连接的平台。统计与错误报告可在设置里关闭，详见[隐私说明](docs/PRIVACY.md)。

</details>

<details>
<summary>什么视频效果最好？</summary>

当前分析主要基于字幕，最适合访谈、播客、课程和口播。有作者字幕的视频最快；没有字幕的需要先在本地转写。纯画面动作或音乐类视频效果有限。

</details>

<details>
<summary>为什么没有生成片段？</summary>

先看失败阶段：字幕是否为空、模型连接是否成功、FFmpeg 和磁盘是否正常。可以换一个更强的模型再试。仍有问题请在[已知问题](https://github.com/zhouxiaoka/autoclip/issues/96)里附上视频类型、时长和模型。

</details>

[完整排错指南](docs/FAQ.md) · [已知问题](https://github.com/zhouxiaoka/autoclip/issues/96)

## 文档

| 你想了解 | 文档 |
| --- | --- |
| 安装与首次出片 | [安装指南](docs/USER_INSTALLATION_GUIDE.md) |
| 自建服务与自动化 | [Docker 部署](DOCKER.md) · [CLI / MCP](docs/CLI_AND_MCP.md) · [Agent skill](skills/autoclip/SKILL.md) · [OpenCode 接入](docs/OPENCODE.md) |
| 配置模型与排错 | [模型配置](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [常见问题](docs/FAQ.md) |
| 版本、路线图与隐私 | [更新日志](CHANGELOG.md) · [路线图](ROADMAP.md) · [社区看板](docs/COMMUNITY_BOARD.md) · [隐私说明](docs/PRIVACY.md) |
| 参与开发与翻译 | [贡献指南](CONTRIBUTING.md) · [翻译维护](docs/i18n.md) |

## 参与贡献

欢迎提交修复、出片样例、使用反馈和翻译改进。如果 AutoClip 帮到了你，欢迎给项目一个 Star。

- **提问与交流**：[GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [第一次出片问答](https://github.com/zhouxiaoka/autoclip/discussions/128) · [分享想法](https://github.com/zhouxiaoka/autoclip/discussions/129)
- **报告故障**：使用 [Issue 模板](https://github.com/zhouxiaoka/autoclip/issues/new/choose)，附上系统、版本、所选模型、复现步骤与已脱敏日志
- **合作联系**：[christine_zhouye@163.com](mailto:christine_zhouye@163.com)

个人维护，回复时间不固定，不提供即时客服或一对一部署服务。

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>
</p>

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)

感谢 FastAPI、React、Tauri、FFmpeg、yt-dlp、Whisper、FunASR，以及所有贡献者。项目采用 [MIT License](LICENSE)。
