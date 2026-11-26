# Guía de AutoClip MCP y Agentes IA

[English](MCP.en.md) · [简体中文](CLI_AND_MCP.md) · [日本語](MCP.ja.md) · [한국어](MCP.ko.md) · **Español** · [Deutsch](MCP.de.md)

Conecta Claude Code, Cursor, Windsurf, OpenCode o cualquier cliente MCP a AutoClip para convertir podcasts, entrevistas o transmisiones en clips verticales listos para publicar. Usa exactamente el mismo motor local que la app de escritorio: sin suscripciones, sin marcas de agua y 100% en tu equipo.

---

## Instalación en una línea

### Claude Code
```bash
claude mcp add autoclip -- uvx autoclip-mcp
```

### Skill para agentes IA
```bash
npx skills add zhouxiaoka/autoclip
```

### Cursor / Windsurf / Cliente MCP (`mcp.json`)
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

> **Requisitos:** Python 3.10+ (3.11 recomendado), `uv` (`uvx`) y `ffmpeg` en tu `PATH`. Comprueba la versión instalada con `autoclip --version` o la herramienta MCP `get_version`.

---

## Herramientas MCP principales

| Herramienta | Función |
| :--- | :--- |
| `get_version` | Devuelve la versión instalada de AutoClip |
| `list_styles` | Lista los estilos disponibles (`editorial`, `street`, `news`, `cinema`, `classic` y plantillas en la nube) |
| `start_quick_output` | Inicia una tarea asíncrona de recorte, subtítulos y portada |
| `get_quick_output_status` | Consulta progreso (`progress`, `stage`, `eta`) y rutas finales de salida |
| `cancel_job` | Detiene con seguridad una tarea activa conservando los clips ya terminados |

### Ejemplo de `start_quick_output`
```json
{
  "source": "/absolute/path/talk.mp4",
  "platforms": ["tiktok", "youtube_shorts"],
  "portrait_style": "podcast",
  "template": "editorial"
}
```

- **Privacidad:** Las claves API nunca se envían como argumentos MCP; se leen de la configuración local o de `AUTOCLIP_API_KEY`. Compatible con modo 100% offline usando Ollama / LM Studio + Whisper.
- Consulta más detalles en [English Guide](MCP.en.md) o [Referencia CLI y MCP (ZH)](CLI_AND_MCP.md).
