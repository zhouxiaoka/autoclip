<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="80" height="80">

# AutoClip

**Encuentra los mejores momentos de tus vídeos con IA y genera clips cortos en HD con un clic.**

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · **Español** · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/forks)
[![GitHub issues](https://img.shields.io/github/issues/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/issues)
[![License: MIT](https://img.shields.io/github/license/zhouxiaoka/autoclip?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — Trendshift" width="250" height="55"></a>
</p>

Gratis y de código abierto · Edición local · Modelos locales y en la nube

[Sitio web](https://zhouxiaoka.github.io/autoclip_intro/) · [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [Informar de un problema](https://github.com/zhouxiaoka/autoclip/issues)

**Instaladores de escritorio: [macOS · Apple Silicon](https://github.com/zhouxiaoka/autoclip/releases/latest) · [Windows · x64](https://github.com/zhouxiaoka/autoclip/releases/latest)**

[Instalación y primeros clips (English)](docs/USER_INSTALLATION_GUIDE.en.md) · [Guía completa de solución de problemas (inglés)](docs/FAQ.en.md)

</div>

Convierte entrevistas, pódcasts, cursos y grabaciones de directos en clips cortos. AutoClip encuentra momentos destacados, genera títulos y crea clips y recopilaciones que puedes ajustar y exportar.

## Vista previa

![Importación de vídeos en AutoClip](docs/images/import-local.jpg)

Importa un vídeo local y, si los tienes, subtítulos SRT. La captura muestra la interfaz en chino.

## Funciones

| Función | Descripción |
| --- | --- |
| Importar vídeos | Archivos locales y enlaces de YouTube o Bilibili. |
| Encontrar momentos destacados | Analiza subtítulos para identificar fragmentos, generar títulos y organizar temas en una línea de tiempo. |
| Editar clips | Crea clips y recopilaciones; ajusta los puntos de inicio y fin, el texto y la relación de aspecto. |
| Momentos de videojuegos | Detecta eventos en partidas grabadas. Requiere configurar un modelo visual y activar el análisis de juegos; el proveedor cobra las llamadas a la nube. [Configuración (chino)](docs/MULTI_LLM_PROVIDER_GUIDE.md). |
| Exportar y publicar | Vídeos verticales u horizontales con subtítulos y tarjetas de título, portadas automáticas y publicación inmediata o programada. [Guía de publicación (chino)](docs/PUBLISH_UPLOAD_POST.md). |
| Modelos y automatización | Modelos de Qwen, OpenAI, Gemini, DeepSeek y otros, o modelos locales con Ollama / LM Studio. Acceso mediante CLI y MCP. |

> Importar → Confirmar el tipo de vídeo → Análisis y edición con IA → Ajustar y exportar

## Primeros pasos

1. **Instala.** Descarga el `.dmg` para macOS Apple Silicon o el `-setup.exe` para Windows x64 desde [GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases/latest). Incluyen Python y FFmpeg.
2. **Configura un modelo.** En Ajustes, introduce tu API Key o conecta un modelo local, prueba la conexión y guarda.
3. **Crea clips.** Importa el vídeo y confirma su tipo para iniciar el análisis y la edición. Revisa el resultado, ajústalo y exporta.

La instalación, importación y guardado en un equipo Windows físico siguen pendientes de validación. En Intel Mac y Linux puedes usar Docker o la CLI.

[Instalación (inglés)](docs/USER_INSTALLATION_GUIDE.en.md) · [Resolución de problemas (inglés)](docs/FAQ.en.md)

<details>
<summary>Docker / Web, CLI y MCP</summary>

- **Docker / Web:** Aloja la interfaz web con la [guía de Docker (inglés)](docs/DOCKER.en.md).
- **CLI:** Procesamiento por lotes y scripts; consulta la [guía de CLI (chino)](docs/CLI_AND_MCP.md).
- **MCP:** Conecta un cliente siguiendo la misma guía o usa la [Agent skill (chino)](skills/autoclip/SKILL.md).

</details>

## Preguntas frecuentes

<details>
<summary>¿Cuánto cuesta?</summary>

AutoClip es gratuito y de código abierto, con licencia MIT. Los modelos en la nube requieren tu propia API Key y el proveedor cobra su uso. Los modelos locales de Ollama / LM Studio no necesitan una clave de nube. Publicar en plataformas internacionales requiere tu propia cuenta de [Upload-Post](https://www.upload-post.com); consulta sus precios y límites en su web.

</details>

<details>
<summary>¿Se sube mi vídeo?</summary>

La edición y el renderizado se ejecutan en tu equipo. El análisis de subtítulos en la nube envía el texto relevante; el análisis visual envía fotogramas seleccionados y el texto necesario. Al publicar se sube el vídeo final a las plataformas conectadas. También puedes exportar solo en local. [Privacidad (inglés)](docs/PRIVACY.en.md).

</details>

<details>
<summary>¿Puedo usar vídeos sin subtítulos?</summary>

Sí. Configura Whisper local y un modelo de voz para transcribir, o importa un SRT existente. Empieza con un vídeo corto subtitulado siguiendo la [guía de inicio (inglés)](docs/USER_INSTALLATION_GUIDE.en.md).

</details>

<details>
<summary>¿Qué vídeos funcionan mejor? ¿Se puede exportar en HD?</summary>

El análisis de subtítulos es adecuado para entrevistas, pódcasts, cursos y contenido hablado. Las partidas grabadas pueden usar análisis visual. Se admite exportación horizontal y vertical a 1080p; la calidad depende del original y de los ajustes. El tiempo de procesamiento depende de la duración, el modelo y el equipo.

</details>

## Apoya el proyecto

Aceptamos patrocinios de empresas y particulares para apoyar el desarrollo y mantenimiento de AutoClip. Las empresas patrocinadoras pueden presentar su marca y sus servicios en el README.

Consultas sobre patrocinios : [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

## Documentación y comunidad

- [Instalación (inglés)](docs/USER_INSTALLATION_GUIDE.en.md) · [Modelos (chino)](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [Ayuda (inglés)](docs/FAQ.en.md)
- [Cambios (chino)](CHANGELOG.md) · [Documentación (chino)](docs/README.md)
- Comparte preguntas e ideas en [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) e informa de errores en [Issues](https://github.com/zhouxiaoka/autoclip/issues/new/choose).
- Agradecemos contribuciones de código, documentación y traducción. [Guía de contribución (chino)](CONTRIBUTING.md).
- Contacto y patrocinios: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Gracias a quienes contribuyen y a proyectos como FastAPI, React, Tauri, FFmpeg, yt-dlp y Whisper. Si AutoClip te resulta útil, puedes apoyarlo con una Star.

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)
