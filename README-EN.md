<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### Open-source AI highlight clipping

Turn long videos into moments worth sharing.

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily?language=Python" alt="AutoClip — Trendshift Python daily ranking" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily" alt="AutoClip — Trendshift daily ranking, all languages" width="250" height="55"></a>
</p>

**[Download desktop app](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [Quick start](#quick-start) · [Website](https://zhouxiaoka.github.io/autoclip_intro/) · [Documentation](#documentation) · [Report an issue](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

[简体中文](README.md) · **English** · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

</div>

AutoClip uses AI to analyze video transcripts, find highlights, write titles, and create clips and collections. Built for interviews, podcasts, courses, and livestream recordings, it offers a desktop app, a Docker web interface, and CLI / MCP access.

## See the interface

![Video import and project management](docs/images/home-v1.4.0.png)

<table>
  <tr>
    <td width="50%" align="center"><strong>AI-generated clips</strong></td>
    <td width="50%" align="center"><strong>Studio preview and editing</strong></td>
  </tr>
  <tr>
    <td><a href="docs/images/clips-v1.4.0.png"><img src="docs/images/clips-v1.4.0.png" alt="AI-generated clips" width="100%"></a></td>
    <td><a href="docs/images/studio-v1.4.0.png"><img src="docs/images/studio-v1.4.0.png" alt="Studio preview and editing" width="100%"></a></td>
  </tr>
</table>

<sub>Real v1.4.0 UI with subsequent Studio fixes: import videos, review actual generated clips, and edit in Studio. The UI is in Chinese; the sample transcript and generated titles remain in English.</sub>

[Screenshot version and sample source (Chinese)](docs/images/README.md)

## Special thanks ❤️

<table>
  <tr>
    <td align="center" width="140">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="88"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td>
      Thank you to <strong>88API Token Platform</strong> for sponsoring AutoClip! It brings together GPT, Claude, Gemini, Grok, DeepSeek, Kimi and GLM for transcript analysis, highlight selection and title generation.<br>
      🎨 <strong>Media capabilities</strong>: The platform offers image, video and audio models, including GPT-Image, Seedance, Veo, MiniMax Hailuo H3, Kling, Whisper and TTS. AutoClip uses compatible analysis, cover-image and transcription APIs.<br>
      🏷️ <strong>Service and billing</strong>: The partner reports overseas corporate operation, live support, invoices and a 1:1 top-up ratio; platform terms apply.<br>
      🎁 <strong>New-user offer</strong>: Receive trial credit to test models through our <a href="https://88api.ai/sign-up?aff=2PIc">referral registration link</a>, subject to promotion terms. <a href="docs/88API_SETUP.en.md">Setup guide</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="88"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar.cc</strong></a>
    </td>
    <td>
      Thank you to <strong>Infistar.cc</strong> for sponsoring AutoClip! Its multi-model API service can support long-video transcript analysis, highlight selection, and title generation.<br>
      ⚙️ <strong>Compatible setup</strong>: Choose the OpenAI-compatible provider in AutoClip and enter the Base URL, your API key, and an available model.<br>
      🧩 <strong>Model choice</strong>: The partner offers Claude, GPT, Gemini, DeepSeek, and other model families. Choose models that support the compatible endpoint to compare transcript analysis and highlight selection.<br>
      🏷️ <strong>Pricing and services</strong>: According to the partner, selected models cost as little as <strong>1% of official list prices</strong>, with RMB billing, invoices, and model authenticity verification. Check the platform for eligible models, current prices, and service terms.<br>
      🎁 <strong>AutoClip offer</strong>: New users can receive <strong>$5 in trial credit</strong> through our <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">referral registration link</a>, subject to the promotion terms. <a href="docs/INFISTAR_SETUP.en.md">Setup guide</a>
    </td>
  </tr>
</table>

## What you can do

Click any thumbnail to view the full image.

<table>
  <tr>
    <td width="50%" valign="top">
      <h4>Import footage</h4>
      <p>Use local videos, YouTube or Bilibili links, with optional SRT subtitles.</p>
      <a href="docs/images/feature-import.png"><img src="docs/images/feature-import.png" alt="Import footage" width="420"></a>
    </td>
    <td width="50%" valign="top">
      <h4>Find highlights</h4>
      <p>Extract outlines, topic timelines, highlight scores, and clip titles from transcripts.</p>
      <a href="docs/images/clips-v1.4.0.png"><img src="docs/images/clips-v1.4.0.png" alt="Find highlights" width="260"></a>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>Create clips and collections</h4>
      <p>Generate clips and suggested collections, then adjust their order manually.</p>
      <a href="docs/images/feature-collections.png"><img src="docs/images/feature-collections.png" alt="Create clips and collections" width="420"></a>
    </td>
    <td width="50%" valign="top">
      <h4>Export for publishing</h4>
      <p>Use presets for Douyin, Xiaohongshu, YouTube Shorts, and Bilibili, with burned-in subtitles and title cards.</p>
      <a href="docs/images/feature-export.png"><img src="docs/images/feature-export.png" alt="Export for publishing" width="420"></a>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>Covers and publishing</h4>
      <p>Since v1.3.2, generate covers and publish immediately or on a schedule. Connect overseas platforms through your Upload-Post account; configure Bilibili separately.</p>
      <a href="docs/images/feature-publish.png"><img src="docs/images/feature-publish.png" alt="Covers and publishing" width="200"></a>
      <a href="docs/images/feature-cover.png"><img src="docs/images/feature-cover.png" alt="Covers and publishing" width="200"></a>
      <p><sub>No publishing account is connected in this demo. These images show the publishing entry and cover settings, not completed posts.</sub></p>
    </td>
    <td width="50%" valign="top">
      <h4>Publishing management</h4>
      <p>Review publishing history and the calendar, manage pending posts, or simply download your clips.</p>
      <a href="docs/images/feature-calendar.png"><img src="docs/images/feature-calendar.png" alt="Publishing management" width="420"></a>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>Choose your models</h4>
      <p>Qwen, OpenAI-compatible APIs, Gemini and other cloud services, or local models through Ollama / LM Studio.</p>
      <a href="docs/images/feature-models.png"><img src="docs/images/feature-models.png" alt="Choose your models" width="420"></a>
    </td>
    <td width="50%" valign="top">
      <h4>Automate your workflow</h4>
      <p>Orchestrate runs with the CLI or call the same processing pipeline from an MCP client.</p>
      <a href="docs/images/feature-cli.png"><img src="docs/images/feature-cli.png" alt="Automate your workflow" width="420"></a>
      <p><sub>CLI / MCP has no GUI: this image captures a display page of actual command help output.</sub></p>
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center" valign="top">
      <h4>Multilingual interface</h4>
      <p>Since v1.3.1, the app, website and README support Chinese, English, Japanese, Korean, Spanish, Portuguese, Russian and French. Choose a language in the header or follow your system. Your media and generated content keep their original language.</p>
      <a href="docs/images/feature-languages.png"><img src="docs/images/feature-languages.png" alt="Multilingual interface" width="420"></a>
      <p><sub>English interface and language menu; media and generated content retain their original language.</sub></p>
    </td>
  </tr>
</table>

<details>
<summary>Platforms, account requirements, and export details</summary>

After clips are ready, open Publish on a clip. Available in **v1.3.2**. Overseas publishing uses platforms connected on your own Upload-Post account: TikTok, Instagram, YouTube, Facebook, LinkedIn, X, Threads, Pinterest, Bluesky, Discord, Telegram, and Google Business, as available on that account. Bilibili is one account: paste a Cookie once in Settings.

It must include SESSDATA, bili_jct, and DedeUserID. Publish now or on a schedule. Title and description are optional and default to the clip title. Burned-in captions default on, and the ~4s title card defaults on.

Visibility defaults to private / self where the platform supports it. AutoClip promises that only for TikTok, YouTube, and Bilibili. You can download without publishing. The project page shows publish history and a calendar, and can cancel a schedule that has not gone out.

“Plan this week” fills Monday, Wednesday, and Friday at 09:00 for overseas platforms only, not Bilibili. Vertical accounts render 9:16 without a 60-second cut. Bilibili alone renders landscape. LinkedIn or X alone keeps the original frame.

Vertical and Bilibili in the same batch are rendered separately.

When publishing, a cover can be generated automatically so Bilibili does not reject an empty cover. Default cover and title-card details follow that release’s installer notes. Available in **v1.3.2**.

</details>


> Import video → Subtitles / transcription → AI analysis and scoring → Clips and collections → Export

<a id="quick-start"></a>

## Quick start

| Your workflow | Recommended option | Requirements |
| --- | --- | --- |
| Edit on your computer | **Desktop app** | macOS Apple Silicon / Windows x64 |
| Self-host / Linux | **Docker** | Docker + Compose v2 |
| Batch processing / agents | **CLI / MCP** | Python 3.10+ (3.11 recommended) + FFmpeg |

### Desktop: your first clips

1. **Install.** Download the appropriate installer from [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest): `.dmg` for macOS Apple Silicon or `-setup.exe` for Windows 10 / 11 x64. Python and FFmpeg are bundled. Intel Mac / Linux users can use Docker or the CLI. Check the release for system requirements.
2. **Configure a model.** Select a provider in Settings, enter your API key and model, test the connection, and save. For local models, start Ollama or LM Studio first.
3. **Import a video.** Start with a 3–5 minute sample, optionally with SRT subtitles. Without subtitles, prepare the local Whisper components and speech model in Settings first.
4. **Preview and export.** Check clip boundaries, titles, and content, then select an export preset or connect an account to publish.

[Full installation guide](docs/USER_INSTALLATION_GUIDE.en.md) · [Troubleshooting](docs/FAQ.en.md)

<details>
<summary><strong>Docker / Web</strong></summary>

Requires Docker and Docker Compose v2. Run these commands from the repository root:

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
```

```bash
cp env.example .env
```

Before starting, edit `.env`: select `LLM_PROVIDER` and set the matching API key and model name. You can also configure the provider in Settings after startup.

```bash
mkdir -p data logs uploads
docker compose up -d --build
```

Open the [web interface](http://localhost:3000). [API documentation](http://localhost:8000/docs) is available once the backend starts. See the [Docker guide](docs/DOCKER.en.md) for deployment details.

On Linux, if bind-mounted directories cause permission errors, fix ownership of the project data directories with this command, then start the services again:

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

</details>

<details>
<summary><strong>CLI / MCP</strong></summary>

Requires Python 3.10+ (3.11 recommended) and FFmpeg on PATH. The installation example uses a macOS / Linux shell; on Windows PowerShell, activate with `venv\Scripts\Activate.ps1`. Local CLI processing does not require Redis.

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
```

Local model example: install and start Ollama, then download a model. Videos without subtitles require `faster-whisper`; the speech model is downloaded on first use. To supply existing subtitles, add `--srt talk.srt`.

```bash
ollama pull qwen2.5:7b
python -m pip install faster-whisper
autoclip doctor --provider ollama
autoclip run talk.mp4 --provider ollama --json
```

Replace `PROJECT_ID` with the project ID returned by processing to export for Shorts. Start the stdio MCP server with `autoclip mcp`:

```bash
autoclip export PROJECT_ID --preset shorts
autoclip mcp
```

In your MCP client, set `command` to the absolute path of `autoclip` in your virtual environment and `args` to `["mcp"]`. See the [CLI / MCP guide](docs/CLI_AND_MCP.md) and [Agent skill](skills/autoclip/SKILL.md) (both in Chinese).

</details>

## Model configuration

| Option | Configuration |
| --- | --- |
| Cloud models | Select a provider in Settings and enter your API key and model. OpenAI-compatible services also accept a custom Base URL. |
| Ollama | Default endpoint: `http://localhost:11434/v1`; default model: `qwen2.5:7b`. No API key required. |
| LM Studio | Load a model and start Local Server at `http://localhost:1234/v1` by default. Select a model actually served by your instance. |

Inside Docker, `localhost` refers to the container. To use a model on the host, configure an address reachable from the container; see the CLI / MCP guide. Video cutting runs locally; cloud model analysis sends transcript text to your selected provider. Video and model downloads still need internet access.

[Infistar · Setup guide](docs/INFISTAR_SETUP.en.md)

## Frequently asked questions

<details>
<summary>Is it free? Do I need an API key?</summary>

AutoClip itself stays free and open source under MIT. Cloud providers bill their own model usage and require your API key. Ollama / LM Studio presets need no cloud key, but require model files and suitable hardware. As of **v1.3.2**, overseas publishing needs your own [Upload-Post](https://www.upload-post.com) account. Free and paid tiers, and daily caps for TikTok, YouTube, Instagram, and other platforms, follow Upload-Post’s own pages. They are not AutoClip promises.

</details>

<details>
<summary>Are my videos uploaded?</summary>

Editing stays on your device. Cloud model analysis sends transcript text to your selected provider. The finished clip leaves the machine only after you click Publish, and only to the platforms you connected. You can also download it without publishing. That Publish page is available in **v1.3.2**. Analytics and error reporting depend on your version and settings; see the privacy notes.

</details>

<details>
<summary>Can I use videos without subtitles?</summary>

Yes, after preparing local Whisper components and a speech model. You can also import existing SRT subtitles. Accurate subtitles can reduce transcription time and recognition errors.

</details>

<details>
<summary>Why were no clips generated?</summary>

Check the failed stage: empty subtitles, model connection failures, an overly high score threshold, or FFmpeg/disk problems. You can try reducing the threshold from 0.7 to 0.5, but this does not guarantee clips.

</details>

<details>
<summary>What videos work best? How long does it take?</summary>

Analysis primarily uses transcripts, making interviews, podcasts, lectures, and spoken commentary suitable. Purely visual action or music may work less well. Time depends on duration, hardware, models, and export settings; start with a 3–5 minute clip you provide.

See the [first-clip guide](docs/USER_INSTALLATION_GUIDE.en.md) for sample preparation and public video examples.

</details>

[Full troubleshooting guide](docs/FAQ.en.md) · [Known issues](https://github.com/zhouxiaoka/autoclip/issues/96)

<a id="documentation"></a>

## Documentation

| Guide | Link |
| --- | --- |
| Getting started | [Installation](docs/USER_INSTALLATION_GUIDE.en.md) |
| Hosting and automation | [Docker](docs/DOCKER.en.md) · [CLI / MCP (Chinese)](docs/CLI_AND_MCP.md) · [Agent skill (Chinese)](skills/autoclip/SKILL.md) |
| Models and troubleshooting | [Model configuration (Chinese)](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [Troubleshooting](docs/FAQ.en.md) |
| Versions and privacy | [Changelog](CHANGELOG.md) · [Privacy](docs/PRIVACY.en.md) |
| Development and translation | [Contributing (Chinese)](CONTRIBUTING.md) · [Translation maintenance (Chinese)](docs/i18n.md) |
| Partner setup | [Infistar](docs/INFISTAR_SETUP.en.md) |

The README is available in eight languages. Installation, Docker, and troubleshooting guides are available in English; other detailed references are mainly in Chinese.

## Contribute and connect

Contributions, feedback, and translation improvements are welcome. For bug reports, include your OS, version, model, reproduction steps, and error logs with sensitive information removed.

Maintained by an individual in their spare time. Response times vary; live support and one-to-one deployment assistance are not provided. Please check the FAQ and known issues before contacting the maintainer.

Ideas, use cases, and model requests belong in [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions). Reproducible bugs use the [issue form](https://github.com/zhouxiaoka/autoclip/issues/new/choose). Board rules: [community board](docs/COMMUNITY_BOARD.md) (Chinese).

- [Welcome and categories](https://github.com/zhouxiaoka/autoclip/discussions/127)
- [First-clip Q&A](https://github.com/zhouxiaoka/autoclip/discussions/128)
- [Ideas](https://github.com/zhouxiaoka/autoclip/discussions/129)

- Email: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Thanks to FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper, and all contributors. Licensed under the [MIT License](LICENSE). If AutoClip helps you, consider giving the project a star.

<details>
<summary>Community recognition · Star History</summary>

These badges are provided by Trendshift. Click to view AutoClip’s recorded achievements. GitHub Trending and Trendshift are separate rankings; badges show recorded achievements, not a live position.

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)

</details>
