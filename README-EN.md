<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="80" height="80">

# AutoClip

**Find the best moments in your videos with AI and generate HD short clips in one click.**

[简体中文](README.md) · **English** · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/forks)
[![GitHub issues](https://img.shields.io/github/issues/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/issues)
[![License: MIT](https://img.shields.io/github/license/zhouxiaoka/autoclip?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — Trendshift" width="250" height="55"></a>
</p>

Free and open source · Local editing · Cloud and local models

[Website](https://zhouxiaoka.github.io/autoclip_intro/) · [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [Report an issue](https://github.com/zhouxiaoka/autoclip/issues)

**Desktop installers: [macOS · Apple Silicon](https://github.com/zhouxiaoka/autoclip/releases/latest) · [Windows · x64](https://github.com/zhouxiaoka/autoclip/releases/latest)**

[Installation and your first clips](docs/USER_INSTALLATION_GUIDE.en.md) · [Full troubleshooting guide](docs/FAQ.en.md)

</div>

Turn interviews, podcasts, courses, and livestream recordings into short clips. AutoClip finds highlights, writes titles, and creates clips and collections that you can adjust and export.

## Preview

![AutoClip video import screen](docs/images/import-local.jpg)

Import a local video with optional SRT subtitles. The screenshot shows the Chinese interface.

## Features

| Feature | What you can do |
| --- | --- |
| Import videos | Use local files, YouTube links, or Bilibili links. |
| Find highlights | Analyze transcripts to find interesting moments, generate titles, and build topic timelines. |
| Edit clips | Create clips and collections; adjust timing, text, and aspect ratio. |
| Gameplay highlights | Find events in gameplay recordings. Configure a vision model and enable gameplay analysis; cloud calls are billed by your provider. [Configuration guide (Chinese)](docs/MULTI_LLM_PROVIDER_GUIDE.md). |
| Export and publish | Export landscape or portrait videos with captions and title cards; generate covers and publish now or on a schedule. [Publishing guide (Chinese)](docs/PUBLISH_UPLOAD_POST.md). |
| Models and automation | Use cloud models including Qwen, OpenAI, Gemini, and DeepSeek, or local models through Ollama / LM Studio. CLI and MCP access are available. |

> Import → Confirm the video type → AI analysis and editing → Adjust and export

## Quick start

1. **Install.** Download the macOS Apple Silicon `.dmg` or Windows x64 `-setup.exe` from [GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases/latest). Desktop installers include Python and FFmpeg.
2. **Set up a model.** Choose a provider in Settings, enter your cloud API key or connect a local model, test the connection, and save.
3. **Create clips.** Import a video and confirm its type to start analysis and clipping. Review the results, make adjustments, and export.

Windows installation, import, and saving still await validation on a physical Windows machine. Intel Mac and Linux users can use Docker or the CLI.

[Installation and your first clips](docs/USER_INSTALLATION_GUIDE.en.md) · [Troubleshooting](docs/FAQ.en.md)

<details>
<summary>Docker / Web, CLI, and MCP</summary>

- **Docker / Web:** Self-host the browser interface using the [Docker guide](docs/DOCKER.en.md).
- **CLI:** Batch processing and scripting; see the [CLI guide (Chinese)](docs/CLI_AND_MCP.md).
- **MCP:** Connect an MCP client using the same guide, or use the [Agent skill (Chinese)](skills/autoclip/SKILL.md).

</details>

## FAQ

<details>
<summary>Does it cost anything?</summary>

AutoClip is free and open source under the MIT license. Cloud models require your own API key and are billed by the provider. Local models through Ollama / LM Studio need no cloud key. Overseas publishing requires your own [Upload-Post](https://www.upload-post.com) account; check its website for pricing and limits.

</details>

<details>
<summary>Is my video uploaded?</summary>

Editing and rendering run on your machine. Cloud transcript analysis sends relevant text; cloud vision analysis sends sampled frames and necessary text. Publishing uploads the finished video to your connected platforms. You can also export locally. See the [privacy notice](docs/PRIVACY.en.md).

</details>

<details>
<summary>Can I use videos without subtitles?</summary>

Yes. Set up local Whisper components and a speech model for transcription, or import an existing SRT file. For your first run, try a short video with subtitles using the [getting started guide](docs/USER_INSTALLATION_GUIDE.en.md).

</details>

<details>
<summary>Which videos work best? Can I export in HD?</summary>

Transcript analysis suits interviews, podcasts, courses, and spoken content. Gameplay recordings can use vision analysis. Landscape and portrait exports support 1080p; image quality depends on the source and export settings. Processing time varies with video length, model, and hardware.

</details>

## Documentation and community

- [Installation](docs/USER_INSTALLATION_GUIDE.en.md) · [Model configuration (Chinese)](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [Troubleshooting](docs/FAQ.en.md)
- [Changelog (Chinese)](CHANGELOG.md) · [Documentation (Chinese)](docs/README.md)
- Share ideas and ask questions in [Discussions](https://github.com/zhouxiaoka/autoclip/discussions), or report bugs through [Issues](https://github.com/zhouxiaoka/autoclip/issues/new/choose).
- Code, documentation, and translation contributions are welcome. See the [contribution guide (Chinese)](CONTRIBUTING.md).
- Contact and sponsorship: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Thanks to all contributors and open-source projects including FastAPI, React, Tauri, FFmpeg, yt-dlp, and Whisper. If AutoClip helps you, consider giving it a Star.

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)
