# AutoClip MCP & AI Agent Guide

**English** · [简体中文](CLI_AND_MCP.md) · [日本語](MCP.ja.md) · [한국어](MCP.ko.md) · [Español](MCP.es.md) · [Deutsch](MCP.de.md)

Turn Claude Code, Cursor, Windsurf, OpenCode, or any MCP-compatible AI agent into an autonomous short-form video editor. AutoClip's MCP server reuses the exact same local-first pipeline, rendering engine, and model settings as the desktop app — zero subscriptions, no paywall, 100% local rendering.

---

## 1-Line Setup

### Claude Code
```bash
claude mcp add autoclip -- uvx autoclip-mcp
```

### Agent Skill (Claude Code / Cursor / Codex / OpenCode)
```bash
npx skills add zhouxiaoka/autoclip
```

### Cursor / Windsurf / Generic MCP Client (`mcp.json`)
```json
{
  "mcpServers": {
    "autoclip": {
      "command": "uvx",
      "args": ["autoclip-mcp"]
    }
  }
}
```

> **Requirements:** Python 3.10+ (3.11 recommended), `uv` (`uvx`), and `ffmpeg` in your `PATH`. Run `autoclip --version` or call MCP `get_version` to check the installed version.

---

## Example Prompts for Your AI Agent

Once connected, just ask your agent in natural language:

- *"Clip `/path/to/podcast.mp4` into vertical TikTok and YouTube Shorts using the `editorial` style, and export ready-to-post kits."*
- *"Download this YouTube interview URL, generate 9:16 Reels with burned-in English captions, and give me the output folder."*
- *"List all available AutoClip editing styles (`list_styles`) and re-render clip #2 in `street` style."*

---

## Core MCP Tools

| Tool | Purpose |
| :--- | :--- |
| `get_version` | Return the installed AutoClip package version |
| `list_styles` | List available packaging styles (`editorial`, `street`, `news`, `cinema`, `classic`, plus cloud templates) |
| `start_quick_output` | Start an async clipping + packaging job (accepts local path or HTTPS YouTube/Bilibili URL) |
| `get_quick_output_status` | Poll `progress`, `stage`, `eta`, `poll_after_sec`, and retrieve final `video_path`, `cover_path`, `post`, and `kit_path` |
| `cancel_job` | Safely terminate an active job's FFmpeg processes and keep any already-completed clips |

### Example `start_quick_output` Payload
```json
{
  "source": "/absolute/path/talk.mp4",
  "srt_path": "/absolute/path/talk.srt",
  "platforms": ["tiktok", "youtube_shorts"],
  "portrait_style": "podcast",
  "template": "editorial"
}
```

Supported platform IDs: `tiktok`, `youtube_shorts`, `instagram_reels`, `youtube_long` (≥180s), `douyin`, `xiaohongshu`, `bilibili`.

---

## Keys, Privacy & Local Models

- **API keys are never passed in MCP tool arguments.** AutoClip reads your saved desktop settings or the `AUTOCLIP_API_KEY` environment variable.
- **100% offline mode:** configure **Ollama** or **LM Studio** plus local **Whisper / SenseVoice** in AutoClip Settings — no cloud key required.
- **Isolated data directory:** set `AUTOCLIP_DATA_DIR=/path/to/demo-data` to keep agent runs separate from your main desktop library.

For full CLI flags and architecture details, see [CLI & MCP Reference (ZH)](CLI_AND_MCP.md) and [OpenCode Guide](OPENCODE.en.md).
