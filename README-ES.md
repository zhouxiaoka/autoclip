<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### Un enlace. Un clic.

Código abierto, con corte y render en tu ordenador. Pega un enlace, elige plataforma y genera <b>vídeo, portada y texto</b>,<br>
para Douyin, Xiaohongshu, TikTok, Reels, YouTube Shorts, Bilibili o YouTube.<br>
La app es gratis; los modelos cloud cobran por uso. Puedes ajustar el resultado en el editor.

<p>
  <a href="https://github.com/zhouxiaoka/autoclip/releases/latest"><img src="https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square" alt="GitHub release"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/stargazers"><img src="https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square" alt="GitHub stars"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/releases"><img src="https://img.shields.io/github/downloads/zhouxiaoka/autoclip/total?style=flat-square" alt="Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License: MIT"></a>
</p>

<a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>

**[Descargar escritorio](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [Casos](https://zhouxiaoka.github.io/autoclip_intro/cases/) · [Inicio rápido](#inicio-rápido) · [Documentación](#documentación) · [Incidencia](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · **Español** · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

</div>

**[1.5.0 ya está publicado](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0)**, con escritorio, CLI y MCP actualizados. El [registro de cambios](CHANGELOG.md) detalla la producción automática, paginación de subtítulos, encuadre y cola de vídeos largos. Actualiza versiones anteriores.

## Clips reales

![Clips verticales de AutoClip: entrevista Xiaohongshu, pódcast TikTok, entrevista Douyin, pódcast Shorts](docs/images/v2/demo-wall.webp)

Ejemplos del formato entrevista y pódcast de AutoClip. Los vídeos completos y sus fuentes están en la **[biblioteca de casos →](https://zhouxiaoka.github.io/autoclip_intro/cases/)**.

Cada clip incluye vídeo, portada, título, descripción, hashtags y paquete ZIP para la plataforma. La biblioteca se actualiza; [envía tus clips](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell).

Los derechos del original pertenecen a sus autores. Ejemplos: [Dwarkesh Patel — Dario Amodei](https://www.youtube.com/watch?v=n1E9IZfvGMA) · [Y Combinator — Sam Altman](https://www.youtube.com/watch?v=ZIaOBAjvc38) · [WIRED — Hideo Kojima](https://www.youtube.com/watch?v=02Ah5VQrzvA)

## Qué hace

### Pega un enlace y listo

Genera según formato y duración de la plataforma. Cada plataforma produce automáticamente hasta 10 clips aptos mejor puntuados; el resto queda bajo demanda. Incluye portada, título, descripción, hashtags y paquete ZIP.

### El empaquetado va incluido

Douyin / Xiaohongshu usan entrevista por defecto; TikTok / Reels / Shorts, pódcast a pantalla completa. Puedes elegir el diseño vertical sin cambiar el idioma de subtítulos y texto de la plataforma. Bilibili / YouTube son horizontales. El encuadre sigue al hablante y conserva escenas sin personas. El cierre de marca está activo por defecto y se desactiva en Ajustes; el texto copiado no lleva firma AutoClip.

### Se queda en tu ordenador

Corte, encuadre y render son locales. Elige modelo de análisis y usa subtítulos del autor, Whisper / SenseVoice local o transcripción cloud configurada. CLI / MCP comparten el flujo de escritorio.

## Tiempo y coste con vídeos reales

Son tres fuentes distintas medidas durante el desarrollo, no una comparación controlada del mismo vídeo. Los costes estiman el uso de texto de qwen-plus de entonces y excluyen ASR cloud, imágenes AI y servicios de publicación. La factura depende del proveedor.

| Versión | Original | Salida | Coste estimado del modelo de texto (CNY) |
| --- | --- | ---: | ---: |
| **Nueva · con subtítulos** | Jensen · 1h43m (EN → Xiaohongshu) | **7,5 min / 10 clips** | **¥0,09** |
| Nueva · sin subtítulos | TIM × Luo Yonghao · 2h52m (ZH → Douyin) | 29,5 min / 10 clips | ¥0,20 |
| Anterior | MrBeast · 2h06m (EN → TikTok) | 65 min | ¥0,64 |

<details>
<summary>Condiciones y registros</summary>

1 de octubre de 2026, el mismo Mac Apple Silicon. Los dos casos nuevos generaron 10 clips; el anterior, 33. Cambian tanto la fuente como la cantidad. Jensen usó subtítulos del autor; TIM, Whisper base local.

Los subtítulos del autor evitan transcribir. Sin ellos, elige ASR local o cloud. Plataformas y clips adicionales aumentan tiempo y consumo. [Mediciones y cálculo](docs/COST_PER_VIDEO.md) (chino).

</details>

## Elige modelos y flujo de datos

Corte y render se realizan en tu ordenador. El análisis cloud envía subtítulos y texto relevante; la comprensión visual o generación con referencias envía fotogramas necesarios, y la transcripción cloud envía audio. El análisis y la transcripción locales no necesitan la API cloud correspondiente. Los clips se suben a plataformas conectadas cuando eliges publicar. Analítica e informes de error se desactivan en Ajustes. [Privacidad](docs/PRIVACY.en.md).

## Inicio rápido

| Quieres | Usa | Necesitas |
| --- | --- | --- |
| Hacer clips en este equipo | **Escritorio** | macOS Apple Silicon o Windows x64 |
| Autohospedar / Linux | **Docker** | Docker y Compose v2 |
| Lotes / agentes | **CLI / MCP** | Python 3.10+ (3.11 recomendado) y FFmpeg |

### Escritorio

1. **Instala.** Desde [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest). macOS Apple Silicon: `.dmg`. Windows 10 / 11 x64: `-setup.exe`. Python y FFmpeg van incluidos.
2. **Configura un modelo.** Elige proveedor e introduce la API Key; selecciona un modelo de análisis disponible, prueba la conexión y guarda. Para modelos locales, carga un modelo e inicia Ollama / LM Studio primero.
3. **Enlace y plataforma.** Empieza con una entrevista o pódcast con subtítulos y elige diseño vertical. Sin subtítulos, prepara Whisper / SenseVoice o configura transcripción cloud en Ajustes.
4. **Revisa y descarga.** Comprueba subtítulos, encuadre y contenido, y guarda el paquete o conecta una cuenta para publicar. Genera alternativas si necesitas más clips.

Intel Mac / Linux pueden usar Docker o CLI. Consulta [instalación](docs/USER_INSTALLATION_GUIDE.en.md) y [1.5.0 Release](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0) para requisitos, primer inicio y alcance de validación.

[Guía de instalación](docs/USER_INSTALLATION_GUIDE.en.md) · [Problemas](docs/FAQ.en.md)

**Docker / Web**

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env
mkdir -p data logs uploads
docker compose up -d --build
```

Abre la [UI web](http://localhost:3000). La [API](http://localhost:8000/docs) está al arrancar el backend. [Guía Docker](docs/DOCKER.en.md).

En Linux, si el montaje falla por permisos, corrige el dueño primero:

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

Para IP LAN o dominio propio, añade la dirección del frontend a `AUTOCLIP_ALLOWED_ORIGINS` en `.env` (separada por comas).

**CLI / MCP**

Python 3.10+ (3.11 recomendado), FFmpeg y FFprobe en PATH; no hace falta Redis. Descarga el [ZIP oficial CLI / MCP](https://github.com/zhouxiaoka/autoclip/releases/download/v1.5.0/autoclip-1.5.0-cli-mcp.zip), descomprímelo y ejecuta desde ese directorio:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --force-reinstall --no-deps autoclip-1.5.0-py3-none-any.whl
```

Los comandos anteriores son para macOS / Linux. En Windows, crea con `py -m venv venv` y activa con `.\venv\Scripts\Activate.ps1`; después usa los mismos comandos `python -m pip`.

Guarda primero la configuración del modelo: reutiliza la del escritorio o configura tu directorio con el ejemplo sin claves del ZIP. [Guía CLI / MCP](docs/CLI_AND_MCP.md) (chino). `produce` no usa la modificación temporal de `run --provider`. `--srt` evita transcribir.

```bash
autoclip --version
autoclip produce talk.mp4 --srt talk.srt --platform douyin --portrait-style podcast --json
autoclip outputs PROJECT_ID --export-kits
```

El cliente MCP inicia el servidor. Para depurar por separado, ejecuta `autoclip mcp` en otro terminal; OpenCode puede configurarse con `autoclip mcp install opencode`.

Sustituye `PROJECT_ID` por el ID devuelto. MCP usa `start_quick_output` / `get_quick_output_status`; `command` debe ser la ruta absoluta de `autoclip` en el venv y `args`, `["mcp"]`. Siguen disponibles `run` / `export` y herramientas anteriores. [CLI / MCP](docs/CLI_AND_MCP.md) (chino), [OpenCode](docs/OPENCODE.en.md), [Agent skill](skills/autoclip/SKILL.md) (chino).

## Modelos

| Opción | Configuración |
| --- | --- |
| API en la nube | Elige proveedor y API Key. Los compatibles con OpenAI aceptan Base URL. |
| Ollama | Dirección predeterminada `http://localhost:11434/v1`. Descarga e inicia un modelo local y selecciona uno ofrecido por el servidor. Sin API Key. |
| LM Studio | Carga un modelo y arranca Local Server, `http://localhost:1234/v1` por defecto. |

Dentro de Docker, `localhost` es el contenedor. Usa una dirección del host alcanzable.

[Modelos](docs/MULTI_LLM_PROVIDER_GUIDE.md) (chino) · [Local y contenedores](docs/CLI_AND_MCP.md) (chino)

## Patrocinadores

Gracias a estos socios. Ambos exponen API compatible con OpenAI: elígelos en Ajustes, pon la clave y aparecen los modelos.

<table>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="72"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td valign="middle">
      API multimodelo compatible con OpenAI. Modelos, precios y ofertas se consultan en el proveedor. <a href="https://88api.ai/sign-up?aff=2PIc">Detalles</a> · <a href="docs/88API_SETUP.en.md">Configuración</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="72"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar</strong></a>
    </td>
    <td valign="middle">
      API multimodelo compatible con OpenAI. Modelos, precios y ofertas se consultan en el proveedor. <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">Detalles</a> · <a href="docs/INFISTAR_SETUP.en.md">Configuración</a>
    </td>
  </tr>
</table>

Servicios, precios y ofertas los dan los socios; manda lo que diga su web.

## Preguntas frecuentes

<details>
<summary>¿Es gratis? ¿Necesito una API Key?</summary>

App gratuita y MIT. Análisis, transcripción e imágenes cloud usan tus credenciales y tarifas del proveedor; la portada automática no usa generación de pago por defecto. Ollama / LM Studio no necesitan clave cloud, pero sí hardware. Publicar requiere tu cuenta Bilibili o [Upload-Post](https://www.upload-post.com).

</details>

<details>
<summary>¿Se suben mis vídeos?</summary>

Corte y render se realizan en tu ordenador. El análisis cloud envía subtítulos y texto relevante; la comprensión visual o generación con referencias envía fotogramas necesarios, y la transcripción cloud envía audio. El análisis y la transcripción locales no necesitan la API cloud correspondiente. Los clips se suben a plataformas conectadas cuando eliges publicar. Analítica e informes de error se desactivan en Ajustes. [Privacidad](docs/PRIVACY.en.md).

</details>

<details>
<summary>¿Qué vídeos funcionan mejor?</summary>

Entrevistas, pódcast, cursos y vídeos hablados son los casos más validados. Los subtítulos del autor son más rápidos; si faltan, usa transcripción local/cloud. Para juegos o poco diálogo, activa comprensión visual con un modelo de imágenes y revisa los momentos elegidos.

</details>

<details>
<summary>¿Por qué no se generaron clips?</summary>

Revisa transcripción, conexión del modelo, FFmpeg, disco y reglas de plataforma. YouTube largo exige fragmentos completos de al menos 180 segundos; usa Shorts/Bilibili para fuentes cortas. Si falla, adjunta versión 1.5.0, OS, duración, modelo y logs sin secretos en [problemas conocidos](https://github.com/zhouxiaoka/autoclip/issues/96).

</details>

[Solución de problemas](docs/FAQ.en.md) · [Problemas conocidos](https://github.com/zhouxiaoka/autoclip/issues/96)

## Documentación

| Quieres | Docs |
| --- | --- |
| Instalar y primeros clips | [Instalación](docs/USER_INSTALLATION_GUIDE.en.md) |
| Autohospedar y automatizar | [Docker](docs/DOCKER.en.md) · [CLI / MCP](docs/CLI_AND_MCP.md) (chino) · [Agent skill](skills/autoclip/SKILL.md) (chino) · [OpenCode](docs/OPENCODE.en.md) |
| Modelos y fallos | [Modelos](docs/MULTI_LLM_PROVIDER_GUIDE.md) (chino) · [FAQ](docs/FAQ.en.md) |
| Versiones, hoja de ruta, privacidad | [Cambios](CHANGELOG.md) · [Hoja de ruta](ROADMAP.md) (chino) · [Tablero](docs/COMMUNITY_BOARD.md) (chino) · [Privacidad](docs/PRIVACY.en.md) |
| Contribuir y traducir | [Contribuir](CONTRIBUTING.md) (chino) · [Traducciones](docs/i18n.md) (chino) |

## Contribuir

Se aceptan arreglos, ejemplos, comentarios y traducciones. Si AutoClip te sirve, un star ayuda.

- **Hablar:** [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [Primer clip](https://github.com/zhouxiaoka/autoclip/discussions/128) · [Ideas](https://github.com/zhouxiaoka/autoclip/discussions/129)
- **Fallos:** [formulario](https://github.com/zhouxiaoka/autoclip/issues/new/choose) con SO, versión, modelo, pasos y registros sin secretos
- **Alianzas:** [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Lo mantiene una persona. No hay soporte en vivo ni despliegue uno a uno.

![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)

Gracias a FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper, FunASR y a quien contribuye. [MIT License](LICENSE).
