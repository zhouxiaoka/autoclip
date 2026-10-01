<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### 一个链接，一键出片

开源，在你的电脑上剪辑与渲染。贴一个链接，选好平台，生成 <b>视频、封面和发布文案</b>，<br>
适配抖音、小红书、TikTok、Reels、YouTube Shorts、B 站与 YouTube。<br>
软件免费，云端模型按量计费；需要调整时可进入编辑器。

<p>
  <a href="https://github.com/zhouxiaoka/autoclip/releases/latest"><img src="https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square" alt="GitHub release"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/stargazers"><img src="https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square" alt="GitHub stars"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/releases"><img src="https://img.shields.io/github/downloads/zhouxiaoka/autoclip/total?style=flat-square" alt="Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License: MIT"></a>
</p>

<a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>

**[下载桌面版](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [案例库](https://zhouxiaoka.github.io/autoclip_intro/cases/) · [快速开始](#快速开始) · [文档](#文档) · [问题反馈](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

**简体中文** · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

</div>

**[1.5.0 已正式发布](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0)**，桌面、CLI 与 MCP 同步更新。一键出片、字幕分页、人物取景与长视频队列修复见 [更新日志](CHANGELOG.md)。旧版用户请升级。

## 真实成片

![AutoClip 自动生成的竖屏成片：小红书访谈式、TikTok 播客式、抖音访谈式、Shorts 播客式](docs/images/v2/demo-wall.webp)

图中展示 AutoClip 自动包装的访谈式与播客式成片。完整视频与原片来源见 **[官网案例库 →](https://zhouxiaoka.github.io/autoclip_intro/cases/)**。

每条成片按目标平台交付视频、封面、标题、简介、话题和 ZIP 发布包。案例库持续更新，欢迎[投稿你的成片](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell)。

原片版权归原作者，仅作效果展示：[Dwarkesh Patel — Dario Amodei](https://www.youtube.com/watch?v=n1E9IZfvGMA) · [Y Combinator — Sam Altman](https://www.youtube.com/watch?v=ZIaOBAjvc38) · [WIRED — Hideo Kojima](https://www.youtube.com/watch?v=02Ah5VQrzvA)

## 能做什么

### 贴链接就出片

选好平台，按平台的画幅与时长要求自动生成。每个平台按评分自动生成至多 10 条合格片段，其余列为备选，点「生成这条」再制作。每条都带封面、标题、简介、话题和 ZIP 发布包。

### 成片自己会包装

抖音 / 小红书默认访谈式，TikTok / Reels / Shorts 默认满屏播客式；竖版也可自行选择两种版式。字幕和文案语言仍按平台，B 站 / YouTube 为横版。画面跟随说话人，无人镜头保留完整画面。自动品牌片尾默认开启，可在设置中关闭；复制发布文案不附 AutoClip 署名。

### 还在你的电脑上

剪辑、取景与渲染在本机完成。分析模型自选，字幕可用作者字幕、本地 Whisper / SenseVoice 或已配置的云端转写。CLI / MCP 与桌面共用同一条一键出片链路。

## 真实素材的耗时与费用

以下是开发期间三条不同素材的实测，不是同一输入的速度对照。费用按当时 qwen-plus 的文字模型用量估算，不含云端语音识别、AI 生图或投稿服务费用；实际账单以所选服务商为准。

| 版本 | 原片 | 出片 | 文字模型费用估算（人民币） |
| --- | --- | ---: | ---: |
| **新版 · 有字幕** | Jensen · 1h43m（英 → 小红书） | **7.5 分钟 / 10 条** | **¥0.09** |
| 新版 · 无字幕 | TIM × 罗永浩 · 2h52m（中 → 抖音） | 29.5 分钟 / 10 条 | ¥0.20 |
| 旧版 | MrBeast · 2h06m（英 → TikTok） | 65 分钟 | ¥0.64 |

<details>
<summary>测试条件与记录</summary>

2026-10-01，同一台 Apple Silicon Mac。前两条为新链路、自动生成 10 条；旧链路生成 33 条，素材与输出数量不同。Jensen 使用作者字幕，TIM 使用本地 Whisper base。

已有作者字幕时跳过转写；没有字幕时可选本地或云端转写。追加平台和制作备选会增加处理时间与用量。完整阶段记录与估算口径见 [成本与时间](docs/COST_PER_VIDEO.md)。

</details>

## 模型与数据由你选择

剪辑和渲染在你的电脑上完成。使用云端分析会发送相关字幕与文案；画面理解或参考帧生图会发送所需抽样画面，云端转写会发送音频。使用本地分析与本地转写时不需要对应云端 API。成片只有选择投稿后才上传到已连接的平台；匿名统计与错误报告可在设置中关闭。详见 [隐私说明](docs/PRIVACY.md)。

## 快速开始

| 你的使用场景            | 建议方式          | 准备事项                              |
| ----------------- | ------------- | --------------------------------- |
| 在电脑上出片            | **桌面版**       | macOS Apple Silicon 或 Windows x64 |
| 自建 Web 服务 / Linux | **Docker**    | Docker 与 Compose v2               |
| 批量处理 / 接入 Agent   | **CLI / MCP** | Python 3.10+（建议 3.11）与 FFmpeg     |

### 桌面版

1. **下载安装**：在 [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) 下载。macOS Apple Silicon 选 `.dmg`，Windows 10 / 11 x64 选 `-setup.exe`。安装包自带 Python 和 FFmpeg。
2. **配置模型**：在设置里选择服务商、填写 API Key，选择可用的分析模型，测试连接并保存；本地模型先在 Ollama / LM Studio 启动服务并加载模型。
3. **贴链接，选平台**：先试一条有字幕的访谈或播客，可选择竖版版式；无字幕时在设置中准备 Whisper / SenseVoice，或配置云端转写。
4. **检查并下载**：预览自动成片，检查字幕、取景与内容完整性，再下载发布包或连接账号投稿；需要更多片段时生成备选。

Intel Mac / Linux 可使用 Docker 或 CLI。安装要求、系统首次启动提示和本次发布的验收范围见 [安装指南](docs/USER_INSTALLATION_GUIDE.md) 与 [1.5.0 Release](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0)。

[完整安装与首次使用指南](docs/USER_INSTALLATION_GUIDE.md) · [遇到问题？](docs/FAQ.md)

**Docker / Web 部署**

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env
mkdir -p data logs uploads
docker compose up -d --build
```

打开 [Web 界面](http://localhost:3000)；[API 文档](http://localhost:8000/docs) 在后端启动后可用。部署细节见 [Docker 指南](DOCKER.md)。

Linux 上若绑定目录出现权限错误，先修正数据目录的归属再启动：

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

从局域网 IP 或自定义域名打开时，在 `.env` 的 `AUTOCLIP_ALLOWED_ORIGINS` 填入前端地址（可逗号分隔）。

**CLI / MCP**

需要 Python 3.10+（建议 3.11），FFmpeg 与 FFprobe 在 PATH 中可用；本地 CLI 不需要 Redis。下载 [正式 CLI / MCP ZIP](https://github.com/zhouxiaoka/autoclip/releases/download/v1.5.0/autoclip-1.5.0-cli-mcp.zip)，解压后在该目录执行：

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --force-reinstall --no-deps autoclip-1.5.0-py3-none-any.whl
```

以上命令用于 macOS / Linux。Windows 用 `py -m venv venv` 创建环境、`.\venv\Scripts\Activate.ps1` 激活；随后使用相同的 `python -m pip` 安装命令。

先保存模型配置：可复用桌面设置；独立使用时按 ZIP 的无密钥示例配置自己的数据目录，详见 [CLI / MCP 指南](docs/CLI_AND_MCP.md)。`produce` 不使用旧 `run --provider` 的临时覆盖。已有字幕可用 `--srt` 跳过转写。

```bash
autoclip --version
autoclip produce talk.mp4 --srt talk.srt --platform douyin --portrait-style podcast --json
autoclip outputs PROJECT_ID --export-kits
```

MCP 服务由客户端启动。需要单独调试时，在另一个终端运行 `autoclip mcp`；使用 OpenCode 可执行 `autoclip mcp install opencode` 写入客户端配置。

把 `PROJECT_ID` 换成制作结果中的项目 ID。MCP 新入口为 `start_quick_output` / `get_quick_output_status`；客户端 `command` 指向虚拟环境中的 `autoclip` 绝对路径，`args` 为 `["mcp"]`。旧 `run` / `export` 和旧切片工具继续兼容。详见 [CLI / MCP](docs/CLI_AND_MCP.md)、[OpenCode 接入](docs/OPENCODE.md) 与 [Agent skill](skills/autoclip/SKILL.md)。

## 模型配置

| 方式        | 配置                                                             |
| --------- | -------------------------------------------------------------- |
| 云端 API    | 在设置中选择服务商，填写自己的 API Key。OpenAI 兼容服务还可配置 Base URL。              |
| Ollama | 默认地址 `http://localhost:11434/v1`；先拉取并启动本地模型，再选择服务实际提供的模型，无需 API Key。 |
| LM Studio | 加载模型并启动 Local Server，默认地址 `http://localhost:1234/v1`。          |

Docker 访问宿主机模型服务时，`localhost` 指向容器自身，需要改为容器可访问的宿主机地址。

[模型配置指南](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [本地模型与容器配置](docs/CLI_AND_MCP.md)

## 赞助伙伴

感谢以下伙伴赞助 AutoClip。两家都提供 OpenAI 兼容接口，可在设置里直接选择，填好 Key 后自动列出可用模型。

<table>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="72"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td valign="middle">
      提供 OpenAI 兼容的多模型 API；可用模型、价格与活动以服务商页面为准。 <a href="https://88api.ai/sign-up?aff=2PIc">了解详情</a> · <a href="docs/88API_SETUP.md">接入说明</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="72"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar 无限星河</strong></a>
    </td>
    <td valign="middle">
      提供 OpenAI 兼容的多模型 API；可用模型、价格与活动以服务商页面为准。 <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">了解详情</a> · <a href="docs/INFISTAR_SETUP.md">接入说明</a>
    </td>
  </tr>
</table>

服务、价格与福利信息由合作方提供，以平台页面为准。

## 常见问题

<details>
<summary>需要付费或 API Key 吗？</summary>

软件免费、MIT 开源。云端分析、转写与 AI 生图按所选服务商计费，需自己的凭据；自动设计封面默认不调用付费生图。Ollama / LM Studio 本地分析不需要云端 Key，但需相应硬件。直接投稿还需自己的 B 站或 [Upload-Post](https://www.upload-post.com) 账号。

</details>

<details>
<summary>我的视频会上传吗？</summary>

剪辑和渲染在你的电脑上完成。使用云端分析会发送相关字幕与文案；画面理解或参考帧生图会发送所需抽样画面，云端转写会发送音频。使用本地分析与本地转写时不需要对应云端 API。成片只有选择投稿后才上传到已连接的平台；匿名统计与错误报告可在设置中关闭。详见 [隐私说明](docs/PRIVACY.md)。

</details>

<details>
<summary>什么视频效果最好？</summary>

访谈、播客、课程和口播是主要验证场景，有作者字幕时最快。缺字幕可用本地或云端转写；游戏录屏、口播较少的素材可启用画面识别并选择支持图片的模型，仍需检查实际选段。

</details>

<details>
<summary>为什么没有生成片段？</summary>

先看具体失败阶段：字幕/转写是否成功、模型连接、FFmpeg 与磁盘是否正常，以及候选是否满足目标平台规则。YouTube 长视频要求完整片段至少 180 秒，短素材可选 Shorts 或 B 站。仍失败请附 1.5.0 版本、系统、素材时长、模型和脱敏日志，见 [已知问题](https://github.com/zhouxiaoka/autoclip/issues/96)。

</details>

[完整排错指南](docs/FAQ.md) · [已知问题](https://github.com/zhouxiaoka/autoclip/issues/96)

## 文档

| 你想了解      | 文档                                                                                                                                    |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| 安装与首次出片   | [安装指南](docs/USER_INSTALLATION_GUIDE.md)                                                                                               |
| 自建服务与自动化  | [Docker 部署](DOCKER.md) · [CLI / MCP](docs/CLI_AND_MCP.md) · [Agent skill](skills/autoclip/SKILL.md) · [OpenCode 接入](docs/OPENCODE.md) |
| 配置模型与排错   | [模型配置](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [常见问题](docs/FAQ.md)                                                                        |
| 版本、路线图与隐私 | [更新日志](CHANGELOG.md) · [路线图](ROADMAP.md) · [社区看板](docs/COMMUNITY_BOARD.md) · [隐私说明](docs/PRIVACY.md)                                  |
| 参与开发与翻译   | [贡献指南](CONTRIBUTING.md) · [翻译维护](docs/i18n.md)                                                                                        |

## 参与贡献

欢迎提交修复、出片样例、使用反馈和翻译改进。如果 AutoClip 帮到了你，欢迎给项目一个 Star。

- **提问与交流**：[GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [第一次出片问答](https://github.com/zhouxiaoka/autoclip/discussions/128) · [分享想法](https://github.com/zhouxiaoka/autoclip/discussions/129)
- **报告故障**：使用 [Issue 模板](https://github.com/zhouxiaoka/autoclip/issues/new/choose)，附上系统、版本、所选模型、复现步骤与已脱敏日志
- **合作联系**：[christine_zhouye@163.com](mailto:christine_zhouye@163.com)

个人维护，回复时间不固定，不提供即时客服或一对一部署服务。

![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)

感谢 FastAPI、React、Tauri、FFmpeg、yt-dlp、Whisper、FunASR，以及所有贡献者。项目采用 [MIT License](LICENSE)。
