# Installation and your first clips

[简体中文](USER_INSTALLATION_GUIDE.md) · [README](../README-EN.md) · [Troubleshooting](FAQ.en.md)

## Choose how to run AutoClip

| Environment | Recommended option |
| --- | --- |
| macOS · Apple Silicon (M series) | [Desktop download](https://github.com/zhouxiaoka/autoclip/releases/latest): choose the `.dmg` containing `aarch64` |
| Windows 10 / 11 · x64 | [Desktop download](https://github.com/zhouxiaoka/autoclip/releases/latest): choose the installer containing `x64-setup.exe` |
| Intel Mac / Linux / self-hosted server | No desktop build yet. Use [Docker](DOCKER.en.md) or the [CLI](CLI_AND_MCP.md) (CLI reference in Chinese) |

Check the actual assets and requirements on the release page. `Source code` archives are not application installers. Desktop installers include Python and FFmpeg; local language models, speech recognition components, and model files need separate setup.

Large files and local models need additional memory and disk space. Allow space for source videos, speech models, temporary files, clips, and exports. Processing speed depends on your hardware, models, and input.

## Install the desktop app

### macOS

Open the `.dmg`, drag AutoClip Desktop into Applications, and launch it from there. On macOS 15 and later, double-click once; if macOS blocks the app, open System Settings → Privacy & Security → Open Anyway ([Apple’s note](https://developer.apple.com/news/?id=saqachfa)). On older macOS, right-click the app and choose Open. Confirm the installer came from this repository’s Releases. Do not disable system-wide security checks.

### Windows

Run `x64-setup.exe` and follow the installer. Installation is per user; routine use does not require administrator privileges. If WebView2 is missing, the installer may need internet access to download it. If SmartScreen appears, choose More info → Run anyway. Confirm the installer came from this repository’s Releases.

## First run

1. **Configure a model.** Open Settings and choose Qwen, OpenAI, Gemini, DeepSeek, Doubao Seed, Kimi, GLM, Grok, or a local model. For cloud services, enter your own API key and model name, test the connection, and save. Compatible endpoints can set a Base URL. For Ollama / LM Studio, start the model service and load a model first. Subtitle analysis is the default. As of **v1.4.0**, game visual analysis is optional: it needs a multimodal model and an explicit enable of paid visual screening. Saving a model does not authorize every visual call.
2. **Prepare subtitles (default route).** Import an accurately timed `.srt` alongside your video when available. When the source has no subtitles, or local Whisper will not install or is too slow, open Settings → Default models → “Speech to subtitles” and switch to Bailian cloud transcription (`qwen-audio-3.1-asr-flash`, about 0.1 yuan per hour of audio; the Alibaba Cloud bill is the actual charge). The audio is uploaded to the cloud. If import is blocked, click “Use cloud transcription instead”. Get the API key in two steps: register or claim the offer with the author’s recommendation link (<https://www.aliyun.com/benefit?userCode=qmyj6jch>), then create the key at <https://bailian.console.aliyun.com/>. To stay on local Whisper: a video without subtitles has to download the local transcription component the first time (about 220 MB, about 15 minutes on a slow network).
3. **Import, then confirm.** Use a short video you are allowed to use. On the home screen, use file import for the video and optional SRT, or link import for a link you are allowed to use. Confirm the production type, and correct it by hand if needed. An unconfirmed import can be resumed. Understanding and cutting start only after confirmation. See [See the example, then use your own clip](#see-the-example-then-use-your-own-clip) below.
4. **Check the result in the shared editor.** Review boundaries, titles, and copy. You still need to check boundaries, crops, and copy yourself. If processing fails, identify whether subtitles, analysis, or export failed, then follow the [FAQ](FAQ.en.md).
5. **Export.** Use the export action and choose a platform preset. Vertical exports can include subtitles and title cards. Play the exported file before publishing it yourself.

Subtitle analysis is the default and suits interviews, podcasts, and courses. As of **v1.4.0**, gameplay recordings can use optional visual analysis, which needs a multimodal model and an explicit enable of paid visual screening. One sample game does not stand for every game. Review the output yourself. There is no claim about ad performance. v1.4.0 does not include CTA motion, generative brand end cards, or karaoke / word-level subtitles.

## See the example, then use your own clip

After install, when the home screen has no projects, click “用示例项目看看效果” (See an example project). The example is inside the installer (`source.mp4` and `source.srt`) and needs no API key.

Then use a short video you are allowed to use:

- About 3–5 minutes, with clear speech.
- Prefer an accurately timed `.srt`. When there are no subtitles, or local Whisper will not install or is too slow, switch to Bailian cloud transcription as described above. The audio is uploaded to the cloud.
- Use a local file or Bilibili. Confirm that you have the right to use the media.

Common sticking points on a first run are in [Discussion #128](https://github.com/zhouxiaoka/autoclip/discussions/128).

## Cloud and local models

| Option | What you need |
| --- | --- |
| Cloud API | A provider account, working API key, access to the selected model, and network access; the provider bills API usage |
| Ollama | Start Ollama, run `ollama pull qwen2.5:7b`, and select Ollama in AutoClip; for long videos raise the context to 16384 or more (`OLLAMA_CONTEXT_LENGTH` or `num_ctx`) |
| LM Studio | Download and load a model, start Local Server, and select an available model in AutoClip; for long videos set Context Length to 16384 or more when loading the model |

Local presets do not require a cloud API key, but inference uses your hardware. Whisper converts speech to text. The subtitle route uses a language model on subtitles or copy. The visual route needs a multimodal model and sends sampled frames only after you explicitly enable it. Configure each one separately.

## Updates and backups

Finish or stop active jobs and exit the app. Back up your data directory, then download the new installer from [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest). Users on v1.3.0 or earlier must install v1.3.1 manually. From v1.3.1 onward, use Settings → Application → Check for updates for future releases; installation and restart require your confirmation. Startup checks remind at most once a day for the same version and can be turned off in Settings or the reminder. Manual checks remain available.

Default desktop data directories:

| Platform | Directory |
| --- | --- |
| macOS | `~/Library/Application Support/AutoClip` |
| Windows | `%APPDATA%\AutoClip` |
| Linux / CLI | `~/.local/share/AutoClip` |

If you set `--data-dir` / `AUTOCLIP_DATA_DIR`, use that directory instead. Logs are usually in its `logs` subdirectory. Back up the project files, database, and settings together. Settings may contain API keys, so protect your backups. Do not uninstall, delete the database, or clear your data directory as a routine troubleshooting step. Do not assume an automatic backup exists. Uninstalling on Windows keeps the data directory by default; `%APPDATA%\AutoClip` is deleted only if you tick "Also delete my AutoClip data (projects, settings, API keys)" in the uninstaller, and upgrades never delete it.

## Help

Check the [FAQ](FAQ.en.md) and [known issues](https://github.com/zhouxiaoka/autoclip/issues/96) first. If the first clip is stuck (model, no subtitles, or OS warnings), continue in the [first-clip Q&A](https://github.com/zhouxiaoka/autoclip/discussions/128). See [welcome and categories](https://github.com/zhouxiaoka/autoclip/discussions/127). If the problem remains, email your OS, application version, model, failed stage, reproduction steps, and sanitized logs.

Maintained by an individual in their spare time. Response times vary; live support and one-to-one deployment assistance are not provided.

Email: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)
