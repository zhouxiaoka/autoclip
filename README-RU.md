<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="80" height="80">

# AutoClip

**Превращайте длинные видео в моменты, которыми хочется поделиться.**

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · **Русский** · [Français](README-FR.md)

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/forks)
[![GitHub issues](https://img.shields.io/github/issues/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/issues)
[![License: MIT](https://img.shields.io/github/license/zhouxiaoka/autoclip?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending #3" width="250" height="55"></a>
</p>

Локальный монтаж · свой ключ модели

Зафиксированное достижение Trendshift, а не текущая позиция. GitHub Trending и Trendshift — разные рейтинги.

[Сайт проекта](https://zhouxiaoka.github.io/autoclip_intro/) · [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [Сообщить о проблеме](https://github.com/zhouxiaoka/autoclip/issues)

**Установщики приложения: [macOS · Apple Silicon](https://github.com/zhouxiaoka/autoclip/releases/latest) · [Windows · x64](https://github.com/zhouxiaoka/autoclip/releases/latest)**

[Установка и первые клипы (English)](docs/USER_INSTALLATION_GUIDE.en.md) · [Полное руководство по устранению неполадок (английский)](docs/FAQ.en.md)

</div>

Начиная с v1.3.1, приложение, сайт и README доступны на китайском, английском, японском, корейском, испанском, португальском, русском и французском языках. Выберите язык в верхней панели или используйте язык системы. Язык ваших материалов и созданного контента не меняется.

AutoClip с помощью ИИ анализирует субтитры, находит яркие моменты, придумывает заголовки и автоматически создаёт клипы и подборки. Подходит для интервью, подкастов, лекций и записей трансляций. Доступны настольное приложение, веб-интерфейс через Docker и CLI / MCP.

## Интерфейс приложения

![AutoClip v1.3.0 — local video import](docs/images/import-local.jpg)

Реальный веб-интерфейс v1.3.0: добавьте локальное видео в области импорта и при необходимости субтитры SRT.

## Возможности

| Возможность | Описание |
| --- | --- |
| Импорт видео | Локальные файлы, ссылки YouTube и Bilibili, а также необязательные субтитры SRT. |
| Поиск ярких моментов | Создание плана, временных интервалов по темам, оценок фрагментов и заголовков на основе субтитров. |
| Клипы и подборки | Автоматическое создание клипов и рекомендуемых подборок с ручным изменением порядка. |
| Публикация (v1.3.2) | С **v1.3.2**, когда клипы готовы, их можно опубликовать или запланировать на той же странице. Зарубежные площадки идут через Upload-Post; для Bilibili один раз вставьте cookie входа в настройках. По умолчанию публикация настолько закрытая, насколько позволяет площадка; файл можно только экспортировать. Подробности: [руководство по публикации (китайский)](docs/PUBLISH_UPLOAD_POST.md). |
| Автообложка (v1.3.2) | При публикации обложка создаётся автоматически, чтобы Bilibili не отклонил пустую обложку; значения по умолчанию — в пояснении к установщику. Доступно в **v1.3.2**. |
| Экспорт для публикации | Профили Douyin, Xiaohongshu, YouTube Shorts и Bilibili, вшитые субтитры и титульные карточки. |
| Выбор моделей | Поддерживаются Qwen, OpenAI, Gemini, Claude, DeepSeek и локальные модели через Ollama / LM Studio (свой API-ключ). |
| Автоматизация | Организация запусков через CLI или вызов того же конвейера обработки из клиента MCP. |

> Импорт видео → Субтитры / распознавание речи → Анализ и оценка ИИ → Клипы и подборки → Экспорт

## Быстрый старт

### 1. Настольное приложение

Скачайте подходящий установщик из [GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases/latest):

| Платформа | Установка |
| --- | --- |
| macOS · Apple Silicon | `.dmg` |
| Windows 10 / 11 · x64 | `-setup.exe` |
| Intel Mac / Linux | Используйте Docker или CLI ниже |

Установщики включают Python и FFmpeg. Доступные платформы и порядок первого запуска указаны в соответствующем релизе. После установки выберите провайдера модели в настройках, проверьте соединение, сохраните настройки и импортируйте видео.

### 2. Docker / Web

Требуются Docker и Docker Compose v2. Выполняйте команды из корня репозитория:

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
```

```bash
cp env.example .env
```

Перед запуском отредактируйте `.env`: задайте `LLM_PROVIDER`, соответствующий API-ключ и имя модели. Провайдера также можно настроить в интерфейсе после запуска.

```bash
mkdir -p data logs uploads
docker compose up -d --build
```

Откройте [веб-интерфейс](http://localhost:3000). [Документация API](http://localhost:8000/docs) доступна после запуска сервера. Подробности — в [руководстве по Docker](DOCKER.md) на китайском языке.

Если в Linux возникают ошибки доступа к примонтированным каталогам, исправьте владельца каталогов данных проекта следующей командой и снова запустите сервисы:

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

### 3. CLI / MCP

Нужны Python 3.10+ (рекомендуется 3.11) и FFmpeg в PATH. Пример рассчитан на оболочку macOS / Linux; в Windows PowerShell активируйте окружение командой `venv\Scripts\Activate.ps1`. Для локальной обработки через CLI Redis не требуется.

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
```

Пример с локальной моделью: установите и запустите Ollama, затем скачайте модель. Для видео без субтитров нужен `faster-whisper`; речевая модель загружается при первом использовании. Для готовых субтитров добавьте `--srt talk.srt`.

```bash
ollama pull qwen2.5:7b
python -m pip install faster-whisper
autoclip doctor --provider ollama
autoclip run talk.mp4 --provider ollama --json
```

Замените `PROJECT_ID` на идентификатор проекта из результата обработки, чтобы экспортировать видео для Shorts. Команда `autoclip mcp` запускает MCP-сервер через stdio:

```bash
autoclip export PROJECT_ID --preset shorts
autoclip mcp
```

В клиенте MCP укажите абсолютный путь к `autoclip` в виртуальном окружении в поле `command`, а `["mcp"]` — в поле `args`. См. [руководство по CLI / MCP](docs/CLI_AND_MCP.md) и [навык для агентов](skills/autoclip/SKILL.md) на китайском языке.

## Настройка моделей

| Вариант | Настройка |
| --- | --- |
| Облачные модели | В настройках выберите Qwen, OpenAI, Gemini, Claude или DeepSeek и введите API-ключ. Совместимые адреса поддерживают свой Base URL. |
| Ollama | Адрес по умолчанию: `http://localhost:11434/v1`; модель: `qwen2.5:7b`. API-ключ не нужен. |
| LM Studio | Загрузите модель и запустите Local Server, по умолчанию на `http://localhost:1234/v1`. Выберите модель, доступную на вашем сервере. |

В Docker адрес `localhost` указывает на сам контейнер. Для доступа к модели на хосте задайте адрес, доступный из контейнера; см. руководство по CLI / MCP. Нарезка видео выполняется локально, но при анализе облачной моделью текст субтитров отправляется выбранному провайдеру. Для скачивания видео и моделей нужен интернет.

## Частые вопросы

<details>
<summary>Это бесплатно? Нужен API-ключ?</summary>

Сам AutoClip по-прежнему бесплатен и открыт по лицензии MIT. Облачные провайдеры взимают плату за использование моделей и требуют ваш API-ключ. Для Ollama / LM Studio облачный ключ не нужен, но необходимы модели и подходящее оборудование. С **v1.3.2** зарубежная отправка требует ваш собственный аккаунт [Upload-Post](https://www.upload-post.com). Бесплатные и платные тарифы, а также дневные лимиты TikTok, YouTube, Instagram и других площадок, берутся со страниц самого Upload-Post. Это не обещания AutoClip.

</details>

<details>
<summary>Мои видео загружаются на сервер?</summary>

Монтаж остаётся на вашем устройстве. Облачной модели отправляется текст субтитров. Готовый клип покидает компьютер только после нажатия «Публикация» и только на подключённые площадки. Его также можно скачать без публикации. Эта страница доступна в **v1.3.2**. Статистика и отчёты об ошибках зависят от версии и настроек; см. сведения о конфиденциальности.

</details>

<details>
<summary>Можно работать без субтитров?</summary>

Да, после установки локальных компонентов Whisper и речевой модели. Можно также импортировать готовый SRT. Точные субтитры помогают сократить ожидание и ошибки распознавания.

</details>

<details>
<summary>Почему клипы не созданы?</summary>

Проверьте этап сбоя: пустые субтитры, подключение к модели, слишком высокий порог оценки, FFmpeg и свободное место. Можно снизить порог с 0.7 до 0.5, но это не гарантирует создание клипов.

</details>

<details>
<summary>Какие видео подходят и сколько времени занимает обработка?</summary>

Анализ опирается на субтитры, поэтому подходят интервью, подкасты, лекции и речевые комментарии. Для визуального действия или музыки результат может быть ограничен. Время зависит от длительности, оборудования, модели и экспорта; начните с короткого образца.

</details>

[Полное руководство по устранению неполадок (английский)](docs/FAQ.en.md) · [Известные проблемы](https://github.com/zhouxiaoka/autoclip/issues/96)

## Документация

README доступен на восьми языках; подробные руководства ниже в основном написаны на китайском. Языки перевода README не определяют языки интерфейса приложения или моделей распознавания речи.

- [Установка и первые клипы (English)](docs/USER_INSTALLATION_GUIDE.en.md)
- [Развёртывание Docker (китайский)](DOCKER.md)
- [CLI, MCP и локальные модели (китайский)](docs/CLI_AND_MCP.md)
- [Провайдеры моделей (китайский)](docs/MULTI_LLM_PROVIDER_GUIDE.md)
- [Частые вопросы (китайский)](docs/FAQ.md)
- [Руководство для участников (китайский)](CONTRIBUTING.md)
- [История изменений](CHANGELOG.md)
- [Конфиденциальность (китайский / английский)](docs/PRIVACY.en.md)
- [Перевод README и обслуживание значков (китайский)](docs/i18n.md)

## Участие и обратная связь

Приветствуются исправления, отзывы и улучшения переводов. В сообщении об ошибке укажите ОС, версию, модель, шаги воспроизведения и журналы ошибок без конфиденциальных данных.

Проект поддерживает один человек в свободное время. Срок ответа не фиксирован; мгновенная поддержка и индивидуальная помощь с развёртыванием не предоставляются. Перед обращением прочитайте FAQ и список известных проблем.

Идеи, сценарии и запросы моделей публикуйте в [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions). Воспроизводимые ошибки оформляйте через [шаблон issue](https://github.com/zhouxiaoka/autoclip/issues/new/choose). Правила доски: [community board](docs/COMMUNITY_BOARD.md) (на китайском).

- [Приветствие и категории](https://github.com/zhouxiaoka/autoclip/discussions/127)
- [Вопросы о первом клипе](https://github.com/zhouxiaoka/autoclip/discussions/128)
- [Идеи](https://github.com/zhouxiaoka/autoclip/discussions/129)

- Электронная почта: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Спасибо проектам FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper и всем участникам. Проект распространяется по [лицензии MIT](LICENSE). Если AutoClip вам помогает, поддержите проект звездой.

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)
