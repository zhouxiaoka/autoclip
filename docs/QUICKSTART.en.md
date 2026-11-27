# AutoClip Desktop — 2-Minute Quickstart

> AutoClip is a **free, open-source desktop app** for macOS and Windows. It runs locally on your computer (not a web clipper, no monthly subscription, no paid setup service needed). Follow these 3 steps to get your first ready-to-post clips in 2 minutes.

---

## Step 1: Download & Install the Desktop App

Go to **[GitHub Releases (Latest)](https://github.com/zhouxiaoka/autoclip/releases/latest)** (or the [AutoClip Website](https://zhouxiaoka.github.io/autoclip_intro/)) and download the installer for your OS:

| Your Computer | Installer File | How to Install |
| --- | --- | --- |
| **Windows 10 / 11 (64-bit)** | `AutoClip_*_x64-setup.exe` | Double-click to install |
| **macOS (Apple Silicon M1–M4)** | `AutoClip_*_aarch64.dmg` | Open `.dmg` and drag to **Applications** |

### Seeing an OS security prompt on first launch?
Because AutoClip is community-built open-source software, your OS may show a standard unsigned-app prompt on first launch:
- **Windows (SmartScreen)**: Click **More info** → **Run anyway**.
- **macOS (Gatekeeper)**: Click **Done**, then open **System Settings → Privacy & Security**, scroll to the bottom, and click **Open Anyway**.

---

## Step 2: Connect an AI Model in 30 Seconds

AutoClip itself is 100% free. You only need an LLM to find highlights and write titles/captions — either a low-cost cloud API (~$0.02–$0.05 per 1-hour video) or **free local Ollama**.

### Option A: Cloud API (Fastest, works on any laptop)
1. Create an API key from any supported provider:
   - **Google Gemini**: [aistudio.google.com/apikey](https://aistudio.google.com/apikey) (free tier available)
   - **OpenRouter**: [openrouter.ai/keys](https://openrouter.ai/keys) (one key for many models)
   - **OpenAI / DeepSeek / DashScope (Qwen)**: also built-in as presets
2. **Copy your API key and switch back to AutoClip**:
   - AutoClip detects the key in your clipboard and pops up a one-click **Fill into Provider** bar at the bottom. Confirm once and you're done.
   - Or open **Settings → AI Model**, choose your provider, paste the key, and click **Save / Test**.

### Option B: Local Ollama (100% Free & Offline)
Install [Ollama](https://ollama.com/), pull a model (e.g. `qwen2.5:7b`), and select **Ollama** in **Settings → AI Model**.

---

## Step 3: Import a Video & Export Clips

1. **Import**: Drag a local video (MP4 / MOV / MKV) into AutoClip, or paste a **YouTube / Bilibili / livestream VOD** link.
2. **Pick target platforms & template**:
   - **TikTok / Instagram Reels / YouTube Shorts**: Portrait 9:16 with automatic framing, animated captions, and cover/post copy. Toggle captions or brand outro on/off right from the import screen.
   - **YouTube Landscape (16:9)**: Keeps widescreen framing with title, cover, and description ready to publish.
3. **Generate & Export**:
   - AutoClip transcribes, selects the strongest moments, reframes, packages captions/covers, and renders clips locally.
   - Preview each clip, tweak titles or trim points if needed, and export straight to your folder.

---

## Top 4 New-User Questions

1. **Is AutoClip an online website?**
   No — it is a local desktop app. Don't paste YouTube URLs into GitHub Discussions; download the installer from [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) instead.
2. **Why do I need an API key? Does AutoClip charge me?**
   AutoClip is free and open-source. You pay your chosen model provider directly (or run Ollama locally for $0). We never charge for setup or subscriptions.
3. **What if a YouTube URL fails to download?**
   Some videos require browser cookies or hit regional limits. Enable browser cookie import in the URL dialog, or download the MP4 locally and drag it into AutoClip.
4. **Need more help?**
   Check the [FAQ](./FAQ.en.md) or open an issue on [GitHub Issues](https://github.com/zhouxiaoka/autoclip/issues/new/choose) with your AutoClip version and screenshot.
