# Installation and your first clips

[简体中文](USER_INSTALLATION_GUIDE.md) · [README](../README-EN.md) · [Troubleshooting](FAQ.en.md)

## Choose how to run AutoClip

| Environment | Recommended option |
| --- | --- |
| macOS · Apple Silicon (M series) | [Desktop download](https://github.com/zhouxiaoka/autoclip/releases/latest): choose the `.dmg` containing `aarch64` |
| Windows 10 / 11 · x64 | [Desktop download](https://github.com/zhouxiaoka/autoclip/releases/latest): choose the installer containing `x64-setup.exe` |
| Intel Mac / Linux / self-hosted server | [Docker](DOCKER.en.md) or [CLI](CLI_AND_MCP.md) (CLI reference in Chinese) |

Check the actual assets and requirements on the release page. `Source code` archives are not application installers. Desktop installers include Python and FFmpeg; local language models, speech recognition components, and model files need separate setup.

Large files and local models need additional memory and disk space. Allow space for source videos, speech models, temporary files, clips, and exports. Processing speed depends on your hardware, models, and input.

## Install the desktop app

### macOS

Open the `.dmg`, drag AutoClip Desktop into Applications, and launch it from there. If macOS blocks an unnotarized build, verify that it came from this repository’s Releases, then follow that release’s first-launch instructions. Do not disable system-wide security checks.

### Windows

Run `x64-setup.exe` and follow the installer. Installation is per user; routine use does not require administrator privileges. If WebView2 is missing, the installer may need internet access to download it. If Windows blocks an unsigned build, verify its source and consult the release notes.

## First run

1. **Configure a model.** Open Settings and choose Qwen, OpenAI, Gemini, DeepSeek, Doubao Seed, Kimi, GLM, or a local model. For cloud services, enter your own API key and model name, test the connection, and save. Compatible endpoints can set a Base URL. For Ollama / LM Studio, start the model service and load a model first.
2. **Prepare subtitles.** Import an accurately timed `.srt` alongside your video when available. Otherwise, prepare the local Whisper components and model in the speech recognition settings. Initial installation and downloads require internet access.
3. **Bring your own short clip.** Use a 3–5 minute video you are allowed to use, with clear speech and, preferably, an accurately timed `.srt`. On the home screen, use file import for the video and optional SRT, or link import for a Bilibili or YouTube URL. Requirements and an example are in [Bring your own short clip](#bring-your-own-short-clip) below.
4. **Review the results.** Check the clip boundaries, titles, and scores in the project details. Preview each clip for completeness. If processing fails, identify whether subtitles, analysis, or export failed, then follow the [FAQ](FAQ.en.md).
5. **Export.** Use the export action in the project details and choose a platform preset. Vertical exports can include subtitles and title cards. Play the exported file before publishing it yourself.

Highlight analysis primarily uses transcript text. Interviews, podcasts, and courses are easier to assess this way; do not expect the same results for purely visual action, music, or videos without speech.

## Bring your own short clip

AutoClip does not host an official sample video. Releases do not include a sample zip or finished clips for download. Use your own short video, or a public platform link you are allowed to use.

- About 3–5 minutes, with clear speech.
- Prefer an accurately timed `.srt`. Without subtitles, prepare local Whisper in Settings first, or choose a video that already has captions.
- Sources: a local file, Bilibili, or YouTube. Confirm that you have the right to use the media.

For a first clip, try this one: [Jackie Dowling | Stanford Energy Fellow](https://www.youtube.com/watch?v=dtmjLzOtx8I) (Stanford ENERGY). 示例·非托管·自担使用权 (example link, not hosted by AutoClip; you are responsible for usage rights).

Two other examples are below. You do not need to try both. Dialogue is mostly English; official captions or your own SRT/Whisper are optional. AutoClip does not provide a finished-file download.

- [The State of Startups in 2026](https://www.youtube.com/watch?v=yslXlV2BP_Y) (Y Combinator). 示例·非托管·自担使用权.
- [Sam Altman on Astra, AGI, and the future of OpenAI](https://www.youtube.com/watch?v=VeizK1M7V7E). Sources Podcast, not an OpenAI channel. 示例·非托管·自担使用权.

You can also use your own clip.

Common sticking points on a first run are in [Discussion #128](https://github.com/zhouxiaoka/autoclip/discussions/128).

## Cloud and local models

| Option | What you need |
| --- | --- |
| Cloud API | A provider account, working API key, access to the selected model, and network access; the provider bills API usage |
| Ollama | Start Ollama, run `ollama pull qwen2.5:7b`, and select Ollama in AutoClip |
| LM Studio | Download and load a model, start Local Server, and select an available model in AutoClip |

Local presets do not require a cloud API key, but inference uses your hardware. Whisper converts speech to text; the language model analyzes that text. Configure them separately.

## Updates and backups

Finish or stop active jobs and exit the app. Back up your data directory, then download the new installer from [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest). Users on v1.3.0 or earlier must install v1.3.1 manually. From v1.3.1 onward, use Settings → Application → Check for updates for future releases; installation and restart require your confirmation. Automatic checks run at most once a day. Manual downloads remain available.

Default desktop data directories:

| Platform | Directory |
| --- | --- |
| macOS | `~/Library/Application Support/AutoClip` |
| Windows | `%APPDATA%\AutoClip` |
| Linux / CLI | `~/.local/share/AutoClip` |

If you set `--data-dir` / `AUTOCLIP_DATA_DIR`, use that directory instead. Logs are usually in its `logs` subdirectory. Back up the project files, database, and settings together. Settings may contain API keys, so protect your backups. Do not uninstall, delete the database, or clear your data directory as a routine troubleshooting step. Do not assume an automatic backup exists.

## Help

Check the [FAQ](FAQ.en.md) and [known issues](https://github.com/zhouxiaoka/autoclip/issues/96) first. If the first clip is stuck (model, no subtitles, or OS warnings), continue in the [first-clip Q&A](https://github.com/zhouxiaoka/autoclip/discussions/128). See [welcome and categories](https://github.com/zhouxiaoka/autoclip/discussions/127). If the problem remains, email your OS, application version, model, failed stage, reproduction steps, and sanitized logs.

Maintained by an individual in their spare time. Response times vary; live support and one-to-one deployment assistance are not provided.

Email: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)
