<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="80" height="80">

# AutoClip

**Convierte vídeos largos en momentos que merece la pena compartir.**

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · **Español** · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/forks)
[![GitHub issues](https://img.shields.io/github/issues/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/issues)
[![License: MIT](https://img.shields.io/github/license/zhouxiaoka/autoclip?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending #3" width="250" height="55"></a>
</p>

Edición en local · trae tu propia clave de modelo

Logro registrado por Trendshift; no es un puesto en tiempo real. GitHub Trending y Trendshift son clasificaciones distintas.

[Sitio web](https://zhouxiaoka.github.io/autoclip_intro/) · [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [Informar de un problema](https://github.com/zhouxiaoka/autoclip/issues)

**Instaladores de escritorio: [macOS · Apple Silicon](https://github.com/zhouxiaoka/autoclip/releases/latest) · [Windows · x64](https://github.com/zhouxiaoka/autoclip/releases/latest)**

[Instalación y primeros clips (English)](docs/USER_INSTALLATION_GUIDE.en.md) · [Guía completa de solución de problemas (inglés)](docs/FAQ.en.md)

</div>

Desde v1.3.1, la aplicación, el sitio web y el README admiten chino, inglés, japonés, coreano, español, portugués, ruso y francés. Elige el idioma en la cabecera o sigue el del sistema. Tus archivos y el contenido generado conservan su idioma original.

AutoClip utiliza IA para analizar los subtítulos de un vídeo, encontrar momentos destacados, crear títulos y generar clips y recopilaciones. Está pensado para entrevistas, pódcasts, cursos y grabaciones de directos, con una aplicación de escritorio, una interfaz web mediante Docker y acceso por CLI / MCP.

## Vista de la aplicación

![AutoClip v1.3.0 — local video import](docs/images/import-local.jpg)

Interfaz web real de v1.3.0: añade un vídeo local en el área de importación, con subtítulos SRT opcionales.

## Qué puedes hacer

| Función | Descripción |
| --- | --- |
| Importar vídeos | Usa archivos locales o enlaces de YouTube y Bilibili, con subtítulos SRT opcionales. |
| Encontrar momentos destacados | Extrae resúmenes, intervalos por tema, puntuaciones y títulos a partir de los subtítulos. |
| Crear clips y recopilaciones | Genera clips y recopilaciones sugeridas, y ajusta su orden manualmente. |
| Publicar (v1.3.2) | Desde la **v1.3.2**, cuando los clips estén listos, publícalos o prográmalos en la misma página. Las plataformas de fuera usan Upload-Post; para Bilibili, pega las cookies de inicio de sesión una vez en Ajustes. El valor predeterminado es tan privado como permita la plataforma; también puedes exportar sin publicar. Detalles: [guía de publicación (chino)](docs/PUBLISH_UPLOAD_POST.md). |
| Portada automática (v1.3.2) | Al publicar, se genera una portada automáticamente para que Bilibili no rechace una portada vacía; los valores por defecto siguen las notas del instalador. Disponible en **v1.3.2**. |
| Exportar para publicar | Usa ajustes para Douyin, Xiaohongshu, YouTube Shorts y Bilibili, con subtítulos incrustados y tarjetas de título. |
| Elegir modelos | Compatible con Qwen, OpenAI, Gemini, DeepSeek, Doubao Seed, Kimi, GLM, Grok y modelos locales mediante Ollama / LM Studio (trae tu propia clave de API). |
| Automatizar tareas | Organiza ejecuciones con la CLI o llama al mismo flujo de procesamiento desde un cliente MCP. |

> Importar vídeo → Subtítulos / transcripción → Análisis y puntuación con IA → Clips y recopilaciones → Exportación

## Inicio rápido

### 1. Aplicación de escritorio

Descarga el instalador adecuado desde [GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases/latest):

| Plataforma | Instalación |
| --- | --- |
| macOS · Apple Silicon | `.dmg` |
| Windows 10 / 11 · x64 | `-setup.exe` |
| Intel Mac / Linux | Usa Docker o la CLI, descritos abajo |

Los instaladores incluyen Python y FFmpeg. Consulta cada versión para conocer las plataformas disponibles y las instrucciones del primer inicio. Tras instalar, elige un proveedor de modelos en la configuración, prueba la conexión, guarda los cambios e importa un vídeo.

### 2. Docker / Web

Necesitas Docker y Docker Compose v2. Ejecuta estos comandos desde la raíz del repositorio:

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
```

```bash
cp env.example .env
```

Antes de iniciar, edita `.env`: selecciona `LLM_PROVIDER` e indica la clave de API y el modelo correspondientes. También puedes configurar el proveedor desde la aplicación después del inicio.

```bash
mkdir -p data logs uploads
docker compose up -d --build
```

Abre la [interfaz web](http://localhost:3000). La [documentación de la API](http://localhost:8000/docs) estará disponible cuando arranque el backend. Consulta la [guía de Docker](DOCKER.md) (en chino) para más detalles.

En Linux, si los directorios montados producen errores de permisos, corrige el propietario de los directorios de datos del proyecto con este comando y vuelve a iniciar los servicios:

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

### 3. CLI / MCP

Necesitas Python 3.10 o posterior (se recomienda 3.11) y FFmpeg en el PATH. El ejemplo usa una shell de macOS / Linux; en PowerShell de Windows, activa el entorno con `venv\Scripts\Activate.ps1`. El procesamiento local por CLI no necesita Redis.

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
```

Ejemplo con un modelo local: instala e inicia Ollama y descarga un modelo. Los vídeos sin subtítulos requieren `faster-whisper`; el modelo de voz se descarga en el primer uso. Para usar subtítulos existentes, añade `--srt talk.srt`.

```bash
ollama pull qwen2.5:7b
python -m pip install faster-whisper
autoclip doctor --provider ollama
autoclip run talk.mp4 --provider ollama --json
```

Sustituye `PROJECT_ID` por el ID del proyecto devuelto al procesar el vídeo para exportar en formato Shorts. Inicia el servidor MCP por stdio con `autoclip mcp`:

```bash
autoclip export PROJECT_ID --preset shorts
autoclip mcp
```

En el cliente MCP, configura `command` con la ruta absoluta a `autoclip` dentro del entorno virtual y `args` con `["mcp"]`. Consulta la [guía de CLI / MCP](docs/CLI_AND_MCP.md) y la [skill para agentes](skills/autoclip/SKILL.md) (ambas en chino).

## Configuración de modelos

| Opción | Configuración |
| --- | --- |
| Modelos en la nube | En Ajustes, elige Qwen, OpenAI, Gemini, DeepSeek, Doubao Seed, Kimi, GLM o Grok e introduce la clave de API. Los endpoints compatibles admiten una Base URL personalizada. |
| Ollama | Dirección predeterminada: `http://localhost:11434/v1`; modelo: `qwen2.5:7b`. No requiere clave de API. |
| LM Studio | Carga un modelo e inicia Local Server, por defecto en `http://localhost:1234/v1`. Selecciona un modelo disponible en tu servidor. |

Dentro de Docker, `localhost` apunta al contenedor. Para usar un modelo del equipo anfitrión, configura una dirección accesible desde el contenedor; consulta la guía de CLI / MCP. El corte del vídeo se realiza localmente; el análisis con modelos en la nube envía el texto de los subtítulos al proveedor elegido. La descarga de vídeos y modelos requiere conexión a internet.

## Preguntas frecuentes

<details>
<summary>¿Es gratuito? ¿Necesito una clave de API?</summary>

AutoClip sigue siendo gratuito y de código abierto bajo MIT. Los proveedores de modelos en la nube cobran por el uso y requieren tu propia clave de API. Ollama / LM Studio no necesitan clave de nube, pero sí modelos y hardware adecuado. Desde **v1.3.2**, publicar en el extranjero requiere tu propia cuenta de [Upload-Post](https://www.upload-post.com). Los planes gratuitos y de pago, y los cupos diarios de TikTok, YouTube, Instagram y otras plataformas, siguen las páginas de Upload-Post. No son promesas de AutoClip.

</details>

<details>
<summary>¿Se suben mis vídeos?</summary>

La edición permanece en tu dispositivo. El análisis con modelos en la nube envía el texto de los subtítulos al proveedor elegido. El clip terminado sale del equipo solo después de pulsar Publicar, y solo hacia las plataformas que conectaste. También puedes descargarlo sin publicar. Esa página Publicar está disponible en **v1.3.2**. Las estadísticas y los informes de errores dependen de la versión y los ajustes; consulta las notas de privacidad.

</details>

<details>
<summary>¿Puedo usar vídeos sin subtítulos?</summary>

Sí, tras preparar los componentes locales de Whisper y un modelo de voz. También puedes importar subtítulos SRT existentes. Unos subtítulos precisos pueden reducir la espera y los errores de transcripción.

</details>

<details>
<summary>¿Por qué no se generaron clips?</summary>

Revisa la fase que falló: subtítulos vacíos, conexión al modelo, umbral de puntuación demasiado alto o problemas de FFmpeg y disco. Puedes probar a reducir el umbral de 0.7 a 0.5, pero eso no garantiza clips.

</details>

<details>
<summary>¿Qué vídeos funcionan mejor y cuánto tarda?</summary>

El análisis se basa principalmente en los subtítulos: entrevistas, pódcasts, cursos y comentarios hablados son adecuados. La acción visual o la música pueden ofrecer peores resultados. El tiempo depende de la duración, el hardware, el modelo y la exportación; prueba primero con una muestra corta.

</details>

[Guía completa de solución de problemas (inglés)](docs/FAQ.en.md) · [Problemas conocidos](https://github.com/zhouxiaoka/autoclip/issues/96)

## Documentación

El README está disponible en ocho idiomas; la mayoría de las guías detalladas están en chino. Los idiomas del README no indican los idiomas que admiten la interfaz o los modelos de transcripción.

- [Instalación y primeros clips (English)](docs/USER_INSTALLATION_GUIDE.en.md)
- [Despliegue con Docker (chino)](DOCKER.md)
- [CLI, MCP y modelos locales (chino)](docs/CLI_AND_MCP.md)
- [Proveedores de modelos (chino)](docs/MULTI_LLM_PROVIDER_GUIDE.md)
- [Preguntas frecuentes (chino)](docs/FAQ.md)
- [Guía de contribución (chino)](CONTRIBUTING.md)
- [Registro de cambios](CHANGELOG.md)
- [Privacidad (chino / inglés)](docs/PRIVACY.en.md)
- [Traducción del README y mantenimiento de insignias (chino)](docs/i18n.md)

## Contribuir y contactar

Agradecemos las correcciones, los comentarios y las mejoras de traducción. Al informar de un fallo, incluye el sistema operativo, la versión, el modelo, los pasos para reproducirlo y los registros de error sin información confidencial.

Proyecto mantenido por una persona en su tiempo libre. Los tiempos de respuesta varían; no se ofrece asistencia inmediata ni ayuda individual de despliegue. Consulta las preguntas frecuentes y los problemas conocidos antes de escribir.

Las ideas, los usos y las peticiones de modelos van a [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions). Los fallos reproducibles usan la [plantilla de issue](https://github.com/zhouxiaoka/autoclip/issues/new/choose). Reglas del tablero: [community board](docs/COMMUNITY_BOARD.md) (chino).

- [Bienvenida y categorías](https://github.com/zhouxiaoka/autoclip/discussions/127)
- [Preguntas sobre el primer clip](https://github.com/zhouxiaoka/autoclip/discussions/128)
- [Ideas](https://github.com/zhouxiaoka/autoclip/discussions/129)

- Correo electrónico: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Gracias a FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper y a todas las personas que contribuyen. Distribuido bajo la [licencia MIT](LICENSE). Si AutoClip te resulta útil, puedes apoyar el proyecto con una estrella.

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)
