<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### Un enlace. Un clic.

Código abierto, gratis y en tu ordenador. Pega un enlace, gasta unos céntimos y recibe <b>más de 10 clips listos para publicar</b>,<br>
cada uno con portada, título, descripción y etiquetas para Douyin, Xiaohongshu, TikTok, Reels o YouTube Shorts.<br>
Sin editor. Sin idas y venidas con un chat de IA.

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

## Clips reales

![Clips verticales de AutoClip: entrevista Xiaohongshu, pódcast TikTok, entrevista Douyin, pódcast Shorts](docs/images/v2/demo-wall.webp)

Cada original fue un solo enlace. Cada clip de arriba es la salida cruda de AutoClip —selección, encuadre, traducción, empaquetado— sin retoque manual. **[Ver con audio en la biblioteca →](https://zhouxiaoka.github.io/autoclip_intro/cases/)**

Cada clip entrega el kit de publicación: vídeo vertical, portada, título, descripción y etiquetas. La biblioteca se actualiza; [envía los tuyos](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell).

Los derechos del original pertenecen a sus autores. Ejemplos: [Dwarkesh Patel — Dario Amodei](https://www.youtube.com/watch?v=n1E9IZfvGMA) · [Y Combinator — Sam Altman](https://www.youtube.com/watch?v=ZIaOBAjvc38) · [WIRED — Hideo Kojima](https://www.youtube.com/watch?v=02Ah5VQrzvA)

## Qué hace

### Pega un enlace y listo
Sin editor ni chat de IA. Elige la plataforma y genera en el formato correcto. Portada, título, descripción y etiquetas incluidos.

### El empaquetado va incluido
Estilo entrevista en Douyin / Xiaohongshu; estilo pódcast en TikTok / Reels / Shorts. El encuadre sigue a quien habla; el material extranjero recibe título local y subtítulos bilingües.

### Se queda en tu ordenador
Corte y render son locales. Eliges el modelo, abres el editor solo si quieres retocar, y usas CLI / MCP para lotes.

## Rápido y barato

Un enlace entra, **más de 10** clips listos salen, cada uno con portada, título, descripción y etiquetas.

| Versión | Original | Salida | Coste |
| --- | --- | ---: | ---: |
| **Nueva · con subtítulos** | Jensen · 1h43m (EN → Xiaohongshu) | **7,5 min / 10 clips** | **¥0,09** |
| Nueva · sin subtítulos | TIM × Luo Yonghao · 2h52m (ZH → Douyin) | 29,5 min / 10 clips | ¥0,20 |
| Anterior | MrBeast · 2h06m (EN → TikTok) | 65 min | ¥0,64 |

Una entrevista de 2–3 h suele costar ¥0,1–0,2. Sin subtítulos del autor, el reconocimiento de voz es local y tarda más; el vídeo no sale de tu máquina.

<details>
<summary>Cómo se midieron estos números</summary>

1 de octubre de 2026, el mismo Mac Apple Silicon, modelo de análisis qwen-plus (¥0,8 / ¥2 por millón de tokens de entrada / salida, precio de terceros Aliyun Bailian). El coste son solo llamadas al modelo.

Los 7,5 min de Jensen: ~1 min de descarga, sin ASR gracias a subtítulos del autor, 25 s de selección, ~2,5 min de corte / encuadre / empaquetado, ~3 min para renderizar 10. La versión anterior gastaba 35 min solo en seleccionar.

Esta versión hace cuatro cosas distintas: una sola pasada sobre la transcripción; llamadas en paralelo; omite ASR local si hay subtítulos del autor; renderiza solo los 10 mejores por defecto.

</details>

## Frente a herramientas cloud de suscripción

| | AutoClip | Herramientas cloud mensuales |
| --- | --- | --- |
| Coste | La app es gratis; el modelo se paga por uso, ~¥0,1–0,2 por 2–3 h | Suscripción mensual, por tiempo de proceso |
| Dónde se procesa el vídeo | Tu ordenador; el modelo en la nube solo ve el texto | Subida a la nube del proveedor |
| Modelos | Tú eliges, también locales | Los del proveedor |
| Plataformas chinas | Plantillas Douyin, Xiaohongshu, Bilibili | Sobre todo internacionales |
| Código | MIT, se puede cambiar y autohospedar | Cerrado |

La columna derecha sigue páginas públicas de productos similares en octubre de 2026; comprueba cada producto.

## Inicio rápido

| Quieres | Usa | Necesitas |
| --- | --- | --- |
| Hacer clips en este equipo | **Escritorio** | macOS Apple Silicon o Windows x64 |
| Autohospedar / Linux | **Docker** | Docker y Compose v2 |
| Lotes / agentes | **CLI / MCP** | Python 3.10+ (3.11 recomendado) y FFmpeg |

### Escritorio

1. **Instala.** Desde [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest). macOS Apple Silicon: `.dmg`. Windows 10 / 11 x64: `-setup.exe`. Python y FFmpeg van incluidos.
2. **Configura un modelo.** Elige proveedor en Ajustes y pon tu API Key; el modelo de análisis se elige solo. En local, arranca antes Ollama o LM Studio.
3. **Pega un enlace y elige plataforma.** Empieza con una entrevista o pódcast de 10–30 min con subtítulos. Sin ellos, prepara Whisper o SenseVoice en Ajustes.
4. **Recoge los clips.** Revisa los 10 mejores, edita si quieres, descarga o publica.

Los instaladores aún no tienen notarización de Apple ni firma de Windows. En macOS, primera apertura con clic derecho → Abrir. En Windows, Más información → Ejecutar de todos modos.

[Guía de instalación](docs/USER_INSTALLATION_GUIDE.en.md) · [Problemas](docs/FAQ.en.md)

**Docker / Web**

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env          # 选择 LLM_PROVIDER，填 API Key 和模型名；也可以启动后在设置页配置
mkdir -p data logs uploads
docker compose up -d --build
```

Abre la [UI web](http://localhost:3000). La [API](http://localhost:8000/docs) está al arrancar el backend. [Guía Docker](docs/DOCKER.en.md).

En Linux, si el montaje falla por permisos, corrige el dueño primero:

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

**CLI / MCP**

Hace falta Python 3.10+ (3.11 recomendado) y FFmpeg en el PATH. El CLI local no necesita Redis.

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
python3 -m venv venv && source venv/bin/activate   # Windows PowerShell：venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
```

```bash
ollama pull qwen2.5:7b
python -m pip install faster-whisper                # 无字幕视频需要；已有字幕可用 --srt talk.srt
autoclip doctor --provider ollama
autoclip run talk.mp4 --provider ollama --json
autoclip export PROJECT_ID --preset shorts
autoclip mcp                                        # stdio MCP 服务
autoclip mcp install opencode                       # opencode 一条命令接入
```

En el cliente MCP, `command` es la ruta absoluta de `autoclip` en el venv y `args` es `["mcp"]`. [CLI / MCP](docs/CLI_AND_MCP.md) (chino), [OpenCode](docs/OPENCODE.en.md), [Agent skill](skills/autoclip/SKILL.md) (chino).

## Modelos

| Opción | Configuración |
| --- | --- |
| API en la nube | Elige proveedor y API Key. Los compatibles con OpenAI aceptan Base URL. |
| Ollama | `http://localhost:11434/v1` por defecto, modelo `qwen2.5:7b`, sin clave. |
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
      Agregador de tokens: GPT, Claude, Gemini, Grok, DeepSeek, Kimi, GLM, más imagen, vídeo y voz. Soporte, factura, recarga 1:1. Crédito de prueba con el <a href="https://88api.ai/sign-up?aff=2PIc">enlace de referido</a>. <a href="docs/88API_SETUP.en.md">Guía</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="72"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar</strong></a>
    </td>
    <td valign="middle">
      API multimodelo: Claude, GPT, Gemini, DeepSeek y más; algunos al 1 % del precio oficial, RMB, factura y verificación. 5 USD de prueba con el <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">enlace de referido</a>. <a href="docs/INFISTAR_SETUP.en.md">Guía</a>
    </td>
  </tr>
</table>

Servicios, precios y ofertas los dan los socios; manda lo que diga su web.

## Preguntas frecuentes

<details>
<summary>¿Es gratis? ¿Hace falta API Key?</summary>

AutoClip es gratis y MIT. Los modelos en la nube los cobra el proveedor y necesitan tu clave; una entrevista de 1 h 43 min midió unos ¥0,09. Ollama / LM Studio no piden clave en la nube, pero sí hardware. Publicar fuera requiere tu cuenta [Upload-Post](https://www.upload-post.com).

</details>

<details>
<summary>¿Se suben mis vídeos?</summary>

Corte y render se quedan en el dispositivo. Los modelos en la nube reciben el texto. El clip solo sale al pulsar Publicar, hacia las plataformas que conectaste. Analítica e informes se pueden apagar. [Privacidad](docs/PRIVACY.en.md).

</details>

<details>
<summary>¿Qué vídeos funcionan mejor?</summary>

El análisis usa sobre todo la transcripción: entrevistas, pódcast, cursos y talking-head. Los subtítulos del autor son lo más rápido; si no hay, primero transcribe en local. Acción o música pura rinden poco.

</details>

<details>
<summary>¿Por qué no hay clips?</summary>

Mira la etapa fallida: subtítulos vacíos, conexión del modelo, FFmpeg o disco. Prueba un modelo más fuerte. Si sigue, añade tipo, duración y modelo en [problemas conocidos](https://github.com/zhouxiaoka/autoclip/issues/96).

</details>

[Guía de problemas](docs/FAQ.en.md) · [Problemas conocidos](https://github.com/zhouxiaoka/autoclip/issues/96)

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
