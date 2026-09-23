# FAQ and troubleshooting

[简体中文](FAQ.md) · [Installation](USER_INSTALLATION_GUIDE.en.md) · [README](../README-EN.md)

## Cost, models, and data

### Is AutoClip free? Do I need an API key?

AutoClip itself stays free and open source under MIT. Cloud model providers bill their own usage; consult your provider for pricing, quotas, and model availability. Ollama / LM Studio presets need no cloud API key, but require downloaded models and suitable hardware. Local Whisper needs separate speech components and model files.

As of **v1.3.2**, overseas publishing needs your own [Upload-Post](https://www.upload-post.com) account. Free and paid tiers, and daily caps for TikTok, YouTube, Instagram, and other platforms, follow Upload-Post’s own pages. They are not AutoClip promises.

### Are videos uploaded? Can I work offline?

Editing stays on your device, and the video stays there too. Cloud language models receive transcript text. The finished clip leaves the machine only after you click Publish, and only to the platforms you connected. You can also download it without publishing. Usage analytics and error reporting depend on the version, build configuration, and settings; see the [privacy notes](PRIVACY.en.md). The Publish page is available in **v1.3.2**.

Once you have local footage, a local language model, and any required speech model, core local processing does not need a cloud model service. Video downloads, component installation, model downloads, and updates still need internet access. Local processing does not mean that every feature is offline.

### What footage works best?

Analysis primarily uses transcripts, so interviews, podcasts, lectures, spoken commentary, and livestream recordings with clear speech are suitable. Music, sports action, and other primarily visual content may not have enough transcript information to identify highlights. There is no guaranteed clip count or quality.

For a first run, bring your own 3–5 minute clip with clear speech, preferably with an accurately timed `.srt`. Use a local file, Bilibili, or YouTube, and confirm that you have the right to use it. AutoClip does not host an official sample, and Releases do not include a sample zip or finished clips.

For a first clip, try [Jackie Dowling | Stanford Energy Fellow](https://www.youtube.com/watch?v=dtmjLzOtx8I) (Stanford ENERGY). 示例·非托管·自担使用权 (example link, not hosted by AutoClip; you are responsible for usage rights).

Other examples are optional. Dialogue is mostly English; official captions or your own SRT/Whisper are optional.

- [The State of Startups in 2026](https://www.youtube.com/watch?v=yslXlV2BP_Y) (Y Combinator). 示例·非托管·自担使用权.
- [Sam Altman on Astra, AGI, and the future of OpenAI](https://www.youtube.com/watch?v=VeizK1M7V7E). Sources Podcast, not an OpenAI channel. 示例·非托管·自担使用权.

Setup steps are in the [installation guide](USER_INSTALLATION_GUIDE.en.md#bring-your-own-short-clip); sticking points are in [Discussion #128](https://github.com/zhouxiaoka/autoclip/discussions/128).

## Installation and startup

### Which file should I download?

In [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest), choose `aarch64.dmg` for Apple Silicon Mac or `x64-setup.exe` for Windows x64. Use Docker or CLI for Intel Mac / Linux. Check the actual release assets; `Source code` is not a desktop installer. Releases do not include an official sample video or finished clips.

For first-launch system warnings, see the [installation guide](USER_INSTALLATION_GUIDE.en.md) and release notes. Routine Windows use does not require administrator privileges.

### What if the app is blank or cannot connect to the backend?

1. Exit fully and restart once, preserving your data directory.
2. Check free disk space and note the exact error and failed stage.
3. Desktop backend ports are managed by the launcher; inspect startup logs instead of assuming port 8000. Docker defaults to port 3000 for the web UI and 8000 for the API.
4. In web mode, disable browser page translation and refresh if it was enabled.
5. For Docker, run `docker compose ps` and `docker compose logs --tail=100 autoclip celery-worker`; see the [Docker guide](DOCKER.en.md).

### Why does the model connection test fail?

Check that the provider, model name, API key, Base URL, and region match, and that your account has access to the model. Start Ollama / LM Studio and load the model first. Default endpoints are `http://localhost:11434/v1` and `http://localhost:1234/v1` respectively.

Inside Docker, `localhost` refers to the container. See the [Docker guide](DOCKER.en.md) for host model access. For proxy, TLS, or timeout errors, check the actual destination and network configuration. Never include a full API key in a report.

## Subtitles, analysis, and export

### What if I have no subtitles? Which format can I import?

Local file import accepts an optional `.srt`. Without usable subtitles, you need speech transcription: install the Whisper components and model in Settings first. CLI users can install `faster-whisper`. Convert other subtitle formats to accurately timed SRT rather than assuming every format is accepted.

### What if installing Whisper on Windows still says mlx-whisper only supports Apple Silicon?

If Settings → Transcription → Install still shows the red error 「mlx-whisper 仅支持 Apple Silicon (macOS)」 on Windows or any other non-Mac system, update to the next installer that includes the [#145](https://github.com/zhouxiaoka/autoclip/pull/145) fix (newer than the released v1.3.2). On desktop, use Settings → Application → Check for updates, or download it from [Releases](https://github.com/zhouxiaoka/autoclip/releases). Older builds showed that message and blocked the install by mistake. After you update, use the same Install button. See [#141](https://github.com/zhouxiaoka/autoclip/issues/141).

### Why were no clips generated?

Read the project error first, then check the failed stage:

| Stage | Check first |
| --- | --- |
| SUBTITLE | Empty subtitles, timing mismatch, or missing Whisper components/model |
| ANALYZE | Model connectivity, parseable output, and sufficient transcript content |
| Scoring | Whether candidates exist and the threshold is too high; try reducing it from 0.7 to 0.5 and processing again |
| EXPORT | FFmpeg availability, free disk space, and write permission on the output directory |

Check the CLI environment, then try a lower threshold:

```bash
autoclip doctor --provider ollama
autoclip run talk.mp4 --provider ollama --srt talk.srt --min-score 0.5 --json
```

Replace the filenames and provider with your actual setup. Without SRT, remove `--srt talk.srt` and prepare transcription first. Lowering the threshold changes selection; it does not guarantee clips. For a first check, use a clip you provide, or try [Jackie Dowling | Stanford Energy Fellow](https://www.youtube.com/watch?v=dtmjLzOtx8I) above. You do not need to run every example. If usage is still unclear, continue in the [first-clip Q&A](https://github.com/zhouxiaoka/autoclip/discussions/128). Reproducible bugs still belong in Issues.

### Why is processing slow or using too much memory?

Identify whether downloading, transcription, model analysis, or FFmpeg export is slow. Try a short video, reduce concurrent jobs, try a smaller local model, and check free memory and disk space. Initial speech model downloads can take time. Before retrying, check whether the previous job is still running. There is no fixed processing time per hour of video.

### Why does a YouTube / Bilibili download fail?

Check that the link opens in your browser and that your account has access. Configure platform login credentials when necessary. CLI / source users can check their yt-dlp version; desktop users should check for a newer release. You can also import a local file you are authorized to obtain. Do not send Cookies in issues or email.

### How do source clips differ from publishing exports?

Clips are segments cut from the source video using time ranges. Publishing export applies a preset, such as vertical layout, burned-in subtitles, and title cards. After generating clips, run export and play the result to check it.

```bash
autoclip export PROJECT_ID --preset shorts
```

Replace `PROJECT_ID` with the actual project ID. Other presets include `douyin`, `xiaohongshu`, `bilibili`, and `original`; see the [CLI / MCP reference](CLI_AND_MCP.md) (Chinese).

### How does the v1.3.2 Publish page work?

Available in **v1.3.2**.

After clips are ready, open Publish on a clip. Overseas platforms and Bilibili share that page:

- Overseas platforms use your own Upload-Post account and the platforms you connected there: TikTok, Instagram, YouTube, Facebook, LinkedIn, X, Threads, Pinterest, Bluesky, Discord, Telegram, and Google Business, as available on that account.
- Bilibili is one account. Paste a Cookie once in Settings. It must include `SESSDATA`, `bili_jct`, and `DedeUserID`.

Publish now or on a schedule. A Bilibili schedule must be more than two hours ahead. Title and description are optional and default to the clip title. Burned-in captions default on. The title card, about four seconds at the start, defaults on. Visibility defaults to private / self where the platform supports it. AutoClip promises that only for TikTok, YouTube, and Bilibili. You can download the file without publishing.

The project page shows publish history and a calendar, and can cancel a schedule that has not gone out. “Plan this week” is overseas only: it fills unpublished clips into Monday, Wednesday, and Friday at 09:00. It does not include Bilibili.

Aspect follows the accounts you send to. Vertical accounts render 9:16 without a 60-second cut. Bilibili alone renders landscape. LinkedIn or X alone keeps the original frame. Vertical and Bilibili in the same batch are rendered separately.

When you publish, a cover can be generated automatically so Bilibili does not reject an empty cover. Default cover and title-card details follow that release’s installer notes. Available in **v1.3.2**.

## Updates, backups, and support

### Where is my data? How do I back it up?

See the [installation guide](USER_INSTALLATION_GUIDE.en.md) for desktop defaults. Docker uses the repository’s `data/`, `logs/`, and `uploads/` bind mounts. Exit the app or stop services before backing up the database, project files, and settings; do not copy only the main SQLite file while jobs are running. Do not assume automatic backups exist, or delete source data to troubleshoot.

### Where are known issues? How can I get help?

Check [known issues](https://github.com/zhouxiaoka/autoclip/issues/96) and [release notes](https://github.com/zhouxiaoka/autoclip/releases) first. Feature ideas and how you use AutoClip go to [Discussions](https://github.com/zhouxiaoka/autoclip/discussions): [welcome and categories](https://github.com/zhouxiaoka/autoclip/discussions/127), [first-clip Q&A](https://github.com/zhouxiaoka/autoclip/discussions/128), and [ideas](https://github.com/zhouxiaoka/autoclip/discussions/129). Reproducible bugs go to Issues. The board rules are in the [community board](COMMUNITY_BOARD.md) (Chinese). If needed, send one email to [christine_zhouye@163.com](mailto:christine_zhouye@163.com) with:

- OS and CPU architecture, AutoClip version, and desktop / Docker / CLI mode.
- Model provider and name, video source and approximate duration, and whether subtitles were supplied.
- Reproduction steps, failed stage, and an error screenshot or relevant recent logs.
- API keys, Cookies, private paths, and private transcript text removed from the logs.

Maintained by an individual in their spare time. Response times vary; live support and one-to-one deployment assistance are not provided.
