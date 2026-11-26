# AutoClip MCP- & KI-Agenten-Leitfaden

[English](MCP.en.md) · [简体中文](CLI_AND_MCP.md) · [日本語](MCP.ja.md) · [한국어](MCP.ko.md) · [Español](MCP.es.md) · **Deutsch**

Verbinde Claude Code, Cursor, Windsurf, OpenCode oder jeden MCP-fähigen KI-Agenten direkt mit AutoClip, um aus Podcasts, Interviews und Streams automatisch fertige Kurzvideos zu schneiden. Der MCP-Server nutzt dieselbe lokale Pipeline wie die Desktop-App – kostenlos, ohne Wasserzeichen und 100 % lokal gerendert.

---

## Einrichtung in einer Zeile

### Claude Code
```bash
claude mcp add autoclip -- uvx autoclip-mcp
```

### Agenten-Skill installieren
```bash
npx skills add zhouxiaoka/autoclip
```

### Cursor / Windsurf / MCP-Client (`mcp.json`)
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

> **Voraussetzungen:** Python 3.10+ (3.11 empfohlen), `uv` (`uvx`) und `ffmpeg` im `PATH`. Prüfe die installierte Version mit `autoclip --version` oder dem MCP-Tool `get_version`.

---

## Zentrale MCP-Tools

| Tool | Zweck |
| :--- | :--- |
| `get_version` | Gibt die installierte AutoClip-Version zurück |
| `list_styles` | Listet verfügbare Schnittstile (`editorial`, `street`, `news`, `cinema`, `classic` sowie Cloud-Vorlagen) |
| `start_quick_output` | Startet einen asynchronen Schnitt-, Untertitel- und Cover-Job |
| `get_quick_output_status` | Fragt Fortschritt (`progress`, `stage`, `eta`) sowie Ausgabepfade ab |
| `cancel_job` | Beendet laufende FFmpeg-Prozesse sicher und behält fertige Clips |

### Beispiel für `start_quick_output`
```json
{
  "source": "/absolute/path/talk.mp4",
  "platforms": ["tiktok", "youtube_shorts"],
  "portrait_style": "podcast",
  "template": "editorial"
}
```

- **Datenschutz:** API-Schlüssel werden niemals als MCP-Parameter übergeben, sondern lokal aus den Desktop-Einstellungen oder `AUTOCLIP_API_KEY` gelesen. Vollständiger Offline-Betrieb mit Ollama / LM Studio + Whisper wird unterstützt.
- Weitere Details im [English Guide](MCP.en.md) oder in der [CLI- & MCP-Referenz (ZH)](CLI_AND_MCP.md).
