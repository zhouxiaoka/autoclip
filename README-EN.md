<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### One link. One click.

Open source, free, and local. Paste a link, spend a few cents, and get <b>10+ ready-to-post clips</b>,<br>
each with a cover, title, description, and hashtags for Douyin, Xiaohongshu, TikTok, Reels, or YouTube Shorts.<br>
No editor. No back-and-forth with an AI chat.

<p>
  <a href="https://github.com/zhouxiaoka/autoclip/releases/latest"><img src="https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square" alt="GitHub release"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/stargazers"><img src="https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square" alt="GitHub stars"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/releases"><img src="https://img.shields.io/github/downloads/zhouxiaoka/autoclip/total?style=flat-square" alt="Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License: MIT"></a>
</p>

<a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>

**[Download desktop](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [Case library](https://zhouxiaoka.github.io/autoclip_intro/cases/) · [Quick start](#quick-start) · [Docs](#documentation) · [Report an issue](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

[简体中文](README.md) · **English** · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

</div>

## Real clips

![AutoClip vertical clips: Xiaohongshu interview, TikTok podcast, Douyin interview, Shorts podcast](docs/images/v2/demo-wall.webp)

Each source was one pasted link. Every clip above is AutoClip’s raw output — picking, framing, translation, packaging — with no manual edit. **[Watch with audio in the case library →](https://zhouxiaoka.github.io/autoclip_intro/cases/)**

Each clip ships a full publish kit for the target platform: vertical video, cover, title, description, and hashtags. The library is updated often; [submit your clips](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell).

Source copyright stays with the original authors, shown here as examples: [Dwarkesh Patel — Dario Amodei](https://www.youtube.com/watch?v=n1E9IZfvGMA) · [Y Combinator — Sam Altman](https://www.youtube.com/watch?v=ZIaOBAjvc38) · [WIRED — Hideo Kojima](https://www.youtube.com/watch?v=02Ah5VQrzvA)

## What it does

### Paste a link, get clips
No editor, no AI chat. Pick a platform and generate in the right frame. Every clip includes a cover, title, description, and hashtags.

### Packaging is built in
Interview style for Douyin / Xiaohongshu; podcast style for TikTok / Reels / Shorts. The frame follows the speaker; foreign-language sources get a local title and bilingual captions.

### It stays on your computer
Cutting and rendering run locally. Choose your model, open the editor only if you want to tweak, and batch with CLI / MCP.

## Fast, and cheap

One link in, **10+** ready-to-post clips out, each with a cover, title, description, and hashtags.

| Version | Source | Output | Cost |
| --- | --- | ---: | ---: |
| **New · with captions** | Jensen · 1h43m (EN → Xiaohongshu) | **7.5 min / 10 clips** | **¥0.09** |
| New · no captions | TIM × Luo Yonghao · 2h52m (ZH → Douyin) | 29.5 min / 10 clips | ¥0.20 |
| Previous | MrBeast · 2h06m (EN → TikTok) | 65 min | ¥0.64 |

A 2–3 hour interview is usually ¥0.1–0.2. Without creator captions, speech-to-text runs locally and takes longer; the video never leaves your machine.

<details>
<summary>How these numbers were measured</summary>

1 October 2026, same Apple Silicon Mac, analysis model qwen-plus (¥0.8 / ¥2 per million input / output tokens, third-party Aliyun Bailian list price). Cost is model calls only.

Jensen’s 7.5 minutes: ~1 min download, skip ASR via creator captions, 25 s highlight pick, ~2.5 min cut / frame / pack, ~3 min to render 10 clips. The previous build spent 35 minutes on highlight picking alone.

This version does four things differently: one-shot highlight pick on the full transcript; parallel model calls; skip local ASR when creator captions exist; render only the top 10 by default.

</details>

## Versus monthly cloud tools

| | AutoClip | Monthly cloud tools |
| --- | --- | --- |
| Cost | App is free; models are pay-as-you-go, about ¥0.1–0.2 for a 2–3 hour interview | Monthly subscription, billed by processing time |
| Where video is processed | Your computer; cloud models receive transcript text only | Uploaded to the vendor’s cloud |
| Models | Your choice, including local | Vendor-chosen |
| Chinese platforms | Douyin, Xiaohongshu, Bilibili templates | Mostly overseas platforms |
| Code | MIT, forkable, self-hostable | Closed source |

The right column follows public pages of similar cloud products as of October 2026; check each product for current terms.

<a id="quick-start"></a>

## Quick start

| You want to | Use | You need |
| --- | --- | --- |
| Make clips on this computer | **Desktop** | macOS Apple Silicon or Windows x64 |
| Self-host / Linux | **Docker** | Docker and Compose v2 |
| Batch / agents | **CLI / MCP** | Python 3.10+ (3.11 recommended) and FFmpeg |

### Desktop

1. **Install.** Download from [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest). macOS Apple Silicon: `.dmg`. Windows 10 / 11 x64: `-setup.exe`. Python and FFmpeg are bundled.
2. **Configure a model.** Pick a provider in Settings and enter your API key; the analysis model is selected for you. For local models, start Ollama or LM Studio first.
3. **Paste a link, pick a platform.** Start with a 10–30 minute interview or podcast that has captions. Without captions, prepare local Whisper or SenseVoice in Settings.
4. **Take the clips.** Review the top 10, edit if you want, then download or publish.

The installers are not Apple-notarized or Windows-signed yet. On macOS, first launch with right-click → Open. On Windows, choose More info → Run anyway in SmartScreen.

[Full installation guide](docs/USER_INSTALLATION_GUIDE.en.md) · [Troubleshooting](docs/FAQ.en.md)

**Docker / Web**

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env          # 选择 LLM_PROVIDER，填 API Key 和模型名；也可以启动后在设置页配置
mkdir -p data logs uploads
docker compose up -d --build
```

Open the [web UI](http://localhost:3000). [API docs](http://localhost:8000/docs) are available after the backend starts. See the [Docker guide](docs/DOCKER.en.md).

On Linux, if bind mounts fail on permissions, fix ownership first:

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

**CLI / MCP**

Needs Python 3.10+ (3.11 recommended) and FFmpeg on PATH. Local CLI processing does not need Redis.

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

In your MCP client, set `command` to the absolute path of `autoclip` in the virtualenv and `args` to `["mcp"]`. See the [CLI / MCP guide](docs/CLI_AND_MCP.md) (Chinese), [OpenCode](docs/OPENCODE.en.md), and [Agent skill](skills/autoclip/SKILL.md) (Chinese).

## Model setup

| Option | Setup |
| --- | --- |
| Cloud API | Pick a provider in Settings and enter your API key. OpenAI-compatible services also accept a Base URL. |
| Ollama | Default `http://localhost:11434/v1`, model `qwen2.5:7b`, no API key. |
| LM Studio | Load a model and start Local Server, default `http://localhost:1234/v1`. |

Inside Docker, `localhost` is the container. Point at a host address the container can reach.

[Model setup](docs/MULTI_LLM_PROVIDER_GUIDE.md) (Chinese) · [Local models and containers](docs/CLI_AND_MCP.md) (Chinese)

## Sponsors

Thanks to these partners for sponsoring AutoClip. Both expose an OpenAI-compatible API: pick them in Settings, enter a key, and available models are listed.

<table>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="72"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td valign="middle">
      Token aggregator for GPT, Claude, Gemini, Grok, DeepSeek, Kimi, GLM, plus image, video, and speech models. Live support, invoices, 1:1 top-up. Trial credit via the <a href="https://88api.ai/sign-up?aff=2PIc">referral link</a>. <a href="docs/88API_SETUP.en.md">Setup</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="72"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar</strong></a>
    </td>
    <td valign="middle">
      Multi-model API with Claude, GPT, Gemini, DeepSeek and others; some models as low as 1% of list price, RMB billing, invoices, and model verification. $5 trial credit via the <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">referral link</a>. <a href="docs/INFISTAR_SETUP.en.md">Setup</a>
    </td>
  </tr>
</table>

Services, prices, and offers are provided by the partners; the platform pages are authoritative.

## FAQ

<details>
<summary>Is it free? Do I need an API key?</summary>

AutoClip is free and open source (MIT). Cloud models are billed by the provider and need your API key; a 1h43m interview measured about ¥0.09. Ollama / LM Studio need no cloud key, but need the hardware. Overseas publishing needs your own [Upload-Post](https://www.upload-post.com) account.

</details>

<details>
<summary>Are my videos uploaded?</summary>

Cutting and rendering stay on your device. Cloud models receive transcript text. A finished clip leaves the machine only after you click Publish, and only to platforms you connected. Analytics and error reports can be turned off in Settings; see [privacy](docs/PRIVACY.en.md).

</details>

<details>
<summary>What videos work best?</summary>

Analysis is mainly from transcripts, so interviews, podcasts, courses, and talking-head videos work best. Creator captions are fastest; without them, local transcription runs first. Pure action or music is limited.

</details>

<details>
<summary>Why were no clips generated?</summary>

Check the failed stage: empty captions, model connection, FFmpeg, or disk. Try a stronger model. If it still fails, add video type, duration, and model on [known issues](https://github.com/zhouxiaoka/autoclip/issues/96).

</details>

[Full troubleshooting](docs/FAQ.en.md) · [Known issues](https://github.com/zhouxiaoka/autoclip/issues/96)

<a id="documentation"></a>

## Documentation

| You want | Docs |
| --- | --- |
| Install and first clips | [Installation](docs/USER_INSTALLATION_GUIDE.en.md) |
| Self-host and automation | [Docker](docs/DOCKER.en.md) · [CLI / MCP](docs/CLI_AND_MCP.md) (Chinese) · [Agent skill](skills/autoclip/SKILL.md) (Chinese) · [OpenCode](docs/OPENCODE.en.md) |
| Models and troubleshooting | [Model setup](docs/MULTI_LLM_PROVIDER_GUIDE.md) (Chinese) · [FAQ](docs/FAQ.en.md) |
| Versions, roadmap, privacy | [Changelog](CHANGELOG.md) · [Roadmap](ROADMAP.md) (Chinese) · [Community board](docs/COMMUNITY_BOARD.md) (Chinese) · [Privacy](docs/PRIVACY.en.md) |
| Contribute and translate | [Contributing](CONTRIBUTING.md) (Chinese) · [Translation maintenance](docs/i18n.md) (Chinese) |

## Contribute

Fixes, clip samples, feedback, and translation improvements are welcome. If AutoClip helps you, a star is appreciated.

- **Talk:** [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [First-clip Q&A](https://github.com/zhouxiaoka/autoclip/discussions/128) · [Ideas](https://github.com/zhouxiaoka/autoclip/discussions/129)
- **Bugs:** use the [issue form](https://github.com/zhouxiaoka/autoclip/issues/new/choose) with OS, version, model, steps, and redacted logs
- **Partnerships:** [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Maintained by one person. Replies are not instant; there is no live support or one-to-one deploy help.

![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)

Thanks to FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper, FunASR, and every contributor. [MIT License](LICENSE).
