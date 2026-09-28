<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="80" height="80">

# AutoClip

**利用 AI 自动提取视频中的精彩片段，一键生成高清短视频。**

**简体中文** · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/forks)
[![GitHub issues](https://img.shields.io/github/issues/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/issues)
[![License: MIT](https://img.shields.io/github/license/zhouxiaoka/autoclip?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — Trendshift" width="250" height="55"></a>
</p>

免费开源 · 本地剪辑 · 支持云端与本地模型

[项目网站](https://zhouxiaoka.github.io/autoclip_intro/) · [讨论](https://github.com/zhouxiaoka/autoclip/discussions) · [反馈问题](https://github.com/zhouxiaoka/autoclip/issues)

**桌面安装包: [macOS · Apple Silicon](https://github.com/zhouxiaoka/autoclip/releases/latest) · [Windows · x64](https://github.com/zhouxiaoka/autoclip/releases/latest)**

[安装与第一次出片](docs/USER_INSTALLATION_GUIDE.md) · [完整排错指南](docs/FAQ.md)

</div>

适合访谈、播客、课程和直播回放。导入视频后，AutoClip 帮你发现高光、生成标题、剪辑片段与合集，你也可以继续调整并导出。

## 界面预览

![AutoClip 视频导入界面](docs/images/import-local.jpg)

导入本地视频，也可同时添加 SRT 字幕。

## 你可以做什么

| 功能 | 说明 |
| --- | --- |
| 导入视频 | 支持本地文件、YouTube 与 B 站链接。 |
| 发现高光 | 根据字幕分析精彩片段，生成标题和话题时间线。 |
| 剪辑与编辑 | 生成片段与合集，调整起止时间、文字和画幅。 |
| 游戏高光 | 识别游戏录屏中的精彩事件。需配置视觉模型并开启游戏分析，云端调用由服务商计费。[配置指南](docs/MULTI_LLM_PROVIDER_GUIDE.md)。 |
| 导出与发布 | 支持竖屏、横屏、字幕和标题卡；自动生成封面，立即或定时发布。[发布指南](docs/PUBLISH_UPLOAD_POST.md)。 |
| 模型与自动化 | 支持 Qwen、OpenAI、Gemini、DeepSeek 等云端模型，以及 Ollama / LM Studio 本地模型；提供 CLI 与 MCP。 |

> 导入视频 → 确认制作类型 → AI 分析与剪辑 → 调整并导出

## 快速开始

1. **下载安装。** 前往 [GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases/latest)，下载 macOS Apple Silicon 的 `.dmg` 或 Windows x64 的 `-setup.exe`。桌面版内置 Python 和 FFmpeg。
2. **配置模型。** 在设置中选择模型，填写云端 API Key 或连接本地模型，测试连接并保存。
3. **开始剪辑。** 导入视频，确认制作类型后启动分析与剪辑。片段生成后，可以调整内容并导出。

Windows 安装包的安装、导入与保存仍待实机验证。Intel Mac / Linux 可使用 Docker 或 CLI。

[安装与第一次出片](docs/USER_INSTALLATION_GUIDE.md) · [常见问题](docs/FAQ.md)

<details>
<summary>Docker / Web、CLI 与 MCP</summary>

- **Docker / Web：** 自部署浏览器界面，按 [Docker 指南](DOCKER.md) 安装和配置。
- **CLI：** 批量处理与脚本编排，见 [CLI 使用指南](docs/CLI_AND_MCP.md)。
- **MCP：** 让支持 MCP 的客户端调用 AutoClip，配置见同一指南；也可使用 [Agent skill](skills/autoclip/SKILL.md)。

</details>

## 常见问题

<details>
<summary>需要付费吗？</summary>

AutoClip 免费开源，采用 MIT 许可证。云端模型需要自己的 API Key，费用由服务商收取；Ollama / LM Studio 本地模型无需云端 Key。海外发布需要自己的 [Upload-Post](https://www.upload-post.com) 账号，费用与额度请查看其官网。

</details>

<details>
<summary>视频会上传吗？</summary>

剪辑与渲染在本机完成。使用云端模型时，字幕分析会发送相关文字，视觉分析会发送抽样画面及必要文字。发布会将成片上传到你连接的平台，也可以只导出到本地。详见 [隐私说明](docs/PRIVACY.md)。

</details>

<details>
<summary>没有字幕可以用吗？</summary>

可以，先配置本地 Whisper 组件与语音模型进行转写；已有字幕可随视频导入 SRT。初次使用建议从一段带字幕的短视频开始，步骤见 [入门指南](docs/USER_INSTALLATION_GUIDE.md)。

</details>

<details>
<summary>适合什么视频？支持高清导出吗？</summary>

字幕分析适合访谈、播客、课程和口播；游戏录屏可开启视觉分析。支持 1080p 横屏与竖屏导出，实际画质取决于原素材和导出设置。处理时间取决于视频时长、模型与硬件。

</details>

## 支持项目

欢迎企业和个人赞助 AutoClip，支持项目的持续开发与维护。企业赞助可在 README 中展示品牌与服务介绍。

赞助合作： [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

## 文档与社区

- [安装指南](docs/USER_INSTALLATION_GUIDE.md) · [模型配置](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [排错指南](docs/FAQ.md)
- [更新日志](CHANGELOG.md) · [文档中心](docs/README.md)
- 使用交流与功能建议欢迎到 [Discussions](https://github.com/zhouxiaoka/autoclip/discussions)，问题反馈请提交 [Issue](https://github.com/zhouxiaoka/autoclip/issues/new/choose)。
- 欢迎贡献代码、文档和翻译，参与方式见 [贡献指南](CONTRIBUTING.md)。
- 联系与赞助合作：[christine_zhouye@163.com](mailto:christine_zhouye@163.com)

感谢所有贡献者，以及 FastAPI、React、Tauri、FFmpeg、yt-dlp、Whisper 等开源项目。如果 AutoClip 帮到了你，欢迎给项目一个 Star。

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)
