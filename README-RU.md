<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### Открытый инструмент для нарезки лучших моментов видео с помощью ИИ

Превращайте длинные видео в моменты, которыми хочется поделиться.

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily?language=Python" alt="AutoClip — Trendshift Python daily ranking" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily" alt="AutoClip — Trendshift daily ranking, all languages" width="250" height="55"></a>
</p>

**[Скачать приложение](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [Быстрый старт](#quick-start) · [Сайт](https://zhouxiaoka.github.io/autoclip_intro/) · [Документация](#documentation) · [Сообщить об ошибке](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · **Русский** · [Français](README-FR.md)

</div>

AutoClip с помощью ИИ анализирует субтитры, находит яркие моменты, придумывает заголовки и автоматически создаёт клипы и подборки. Подходит для интервью, подкастов, лекций и записей трансляций. Доступны настольное приложение, веб-интерфейс через Docker и CLI / MCP.

## Интерфейс приложения

![Импорт видео и управление проектами](docs/images/home-v1.4.0.png)

<table>
  <tr>
    <td width="50%" align="center"><strong>Клипы, созданные ИИ</strong></td>
    <td width="50%" align="center"><strong>Просмотр и редактирование в Studio</strong></td>
  </tr>
  <tr>
    <td><a href="docs/images/clips-v1.4.0.png"><img src="docs/images/clips-v1.4.0.png" alt="Клипы, созданные ИИ" width="100%"></a></td>
    <td><a href="docs/images/studio-v1.4.0.png"><img src="docs/images/studio-v1.4.0.png" alt="Просмотр и редактирование в Studio" width="100%"></a></td>
  </tr>
</table>

<sub>Реальный интерфейс v1.4.0 с последующими исправлениями Studio: импорт видео, просмотр действительно созданных клипов и редактирование в Studio. Интерфейс на китайском; субтитры и заголовки примера — на английском.</sub>

[Версия снимков и источник примера (кит.)](docs/images/README.md)

## Благодарим спонсоров ❤️

<table>
  <tr>
    <td align="center" width="140">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="88"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td>
      Благодарим <strong>88API</strong> за поддержку AutoClip! Платформа объединяет GPT, Claude, Gemini, Grok, DeepSeek, Kimi и GLM для анализа субтитров, выбора ярких моментов и создания заголовков.<br>
      🎨 <strong>Мультимедиа</strong>: Модели изображений, видео и аудио, включая GPT-Image, Seedance, Veo, MiniMax Hailuo H3, Kling, Whisper и TTS. AutoClip использует совместимые API анализа, создания обложек и транскрипции.<br>
      🏷️ <strong>Сервис и оплата</strong>: По информации партнёра, сервис управляется зарубежной компанией и предлагает поддержку операторов, счета и пополнение в соотношении 1:1; действуют условия платформы.<br>
      🎁 <strong>Новым пользователям</strong>: Получите пробный кредит для проверки моделей по <a href="https://88api.ai/sign-up?aff=2PIc">реферальной ссылке</a> на условиях акции. <a href="docs/88API_SETUP.en.md">Инструкция по настройке (англ.)</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="88"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar.cc</strong></a>
    </td>
    <td>
      Благодарим <strong>Infistar.cc</strong> за поддержку AutoClip! Сервис предоставляет API разных моделей для анализа субтитров длинных видео, выбора ярких моментов и создания заголовков.<br>
      ⚙️ <strong>Совместимый API</strong>: Выберите в AutoClip провайдера с поддержкой OpenAI-совместимого API и укажите Base URL, свой ключ API и доступную модель.<br>
      🧩 <strong>Выбор моделей</strong>: Партнёр предлагает Claude, GPT, Gemini, DeepSeek и другие семейства. Выбирайте модели, поддерживающие совместимую конечную точку, чтобы сравнивать анализ субтитров и подбор ярких моментов.<br>
      🏷️ <strong>Цены и услуги</strong>: По данным партнёра, некоторые модели доступны по цене <strong>от 1% официального тарифа</strong>, с оплатой в юанях, выставлением счетов и проверкой подлинности модели. Список моделей, действующие цены и условия уточняйте на платформе.<br>
      🎁 <strong>Предложение для AutoClip</strong>: Новые пользователи могут получить <strong>$5 пробного кредита</strong> при регистрации по <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">реферальной ссылке</a> на условиях акции. <a href="docs/INFISTAR_SETUP.en.md">Инструкция по настройке (англ.)</a>
    </td>
  </tr>
</table>

## Возможности

Нажмите на миниатюру, чтобы открыть полное изображение.

<table>
  <tr>
    <td width="50%" valign="top">
      <h4>Импорт видео</h4>
      <p>Локальные файлы, ссылки YouTube и Bilibili, а также необязательные субтитры SRT.</p>
      <a href="docs/images/feature-import.png"><img src="docs/images/feature-import.png" alt="Импорт видео" width="420"></a>
    </td>
    <td width="50%" valign="top">
      <h4>Поиск ярких моментов</h4>
      <p>Создание плана, временных интервалов по темам, оценок фрагментов и заголовков на основе субтитров.</p>
      <a href="docs/images/clips-v1.4.0.png"><img src="docs/images/clips-v1.4.0.png" alt="Поиск ярких моментов" width="260"></a>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>Клипы и подборки</h4>
      <p>Автоматическое создание клипов и рекомендуемых подборок с ручным изменением порядка.</p>
      <a href="docs/images/feature-collections.png"><img src="docs/images/feature-collections.png" alt="Клипы и подборки" width="420"></a>
    </td>
    <td width="50%" valign="top">
      <h4>Экспорт для публикации</h4>
      <p>Профили Douyin, Xiaohongshu, YouTube Shorts и Bilibili, вшитые субтитры и титульные карточки.</p>
      <a href="docs/images/feature-export.png"><img src="docs/images/feature-export.png" alt="Экспорт для публикации" width="420"></a>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>Обложки и публикация</h4>
      <p>Начиная с v1.3.2 доступны создание обложек, немедленная и отложенная публикация. Международные платформы подключаются через ваш аккаунт Upload-Post, Bilibili настраивается отдельно.</p>
      <a href="docs/images/feature-publish.png"><img src="docs/images/feature-publish.png" alt="Обложки и публикация" width="200"></a>
      <a href="docs/images/feature-cover.png"><img src="docs/images/feature-cover.png" alt="Обложки и публикация" width="200"></a>
      <p><sub>В демонстрации не подключён аккаунт для публикации. Показаны экран публикации и настройки обложки, а не результаты отправки.</sub></p>
    </td>
    <td width="50%" valign="top">
      <h4>Управление публикациями</h4>
      <p>Просматривайте историю и календарь, управляйте запланированными постами или просто скачивайте клипы.</p>
      <a href="docs/images/feature-calendar.png"><img src="docs/images/feature-calendar.png" alt="Управление публикациями" width="420"></a>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>Выбор моделей</h4>
      <p>Qwen, совместимые с OpenAI API, Gemini и другие облачные сервисы либо локальные модели через Ollama / LM Studio.</p>
      <a href="docs/images/feature-models.png"><img src="docs/images/feature-models.png" alt="Выбор моделей" width="420"></a>
    </td>
    <td width="50%" valign="top">
      <h4>Автоматизация</h4>
      <p>Организация запусков через CLI или вызов того же конвейера обработки из клиента MCP.</p>
      <a href="docs/images/feature-cli.png"><img src="docs/images/feature-cli.png" alt="Автоматизация" width="420"></a>
      <p><sub>У CLI / MCP нет GUI: это снимок страницы с реальным выводом справки команд.</sub></p>
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center" valign="top">
      <h4>Многоязычный интерфейс</h4>
      <p>Начиная с v1.3.1, приложение, сайт и README доступны на китайском, английском, японском, корейском, испанском, португальском, русском и французском языках. Выберите язык в верхней панели или используйте язык системы. Язык ваших материалов и созданного контента не меняется.</p>
      <a href="docs/images/feature-languages.png"><img src="docs/images/feature-languages.png" alt="Многоязычный интерфейс" width="420"></a>
      <p><sub>Интерфейс на английском и меню языков; материалы и созданный контент сохраняют исходный язык.</sub></p>
    </td>
  </tr>
</table>

<details>
<summary>Платформы, требования к аккаунтам и параметры экспорта</summary>

Когда клипы готовы, откройте «Публикация» у клипа. Доступно в **v1.3.2**. Зарубежные площадки — те, что подключены в вашем собственном аккаунте Upload-Post: TikTok, Instagram, YouTube, Facebook, LinkedIn, X, Threads, Pinterest, Bluesky, Discord, Telegram и Google Business, по факту подключения. Bilibili — один аккаунт: один раз вставьте Cookie в настройках.

Нужны SESSDATA, bili_jct и DedeUserID. Можно отправить сейчас или по расписанию. Заголовок и описание необязательны и по умолчанию берутся из названия клипа. Вшитые субтитры включены по умолчанию, как и титульная карточка примерно на 4 секунды.

Видимость по умолчанию — только я / private там, где площадка это поддерживает. AutoClip обещает это только для TikTok, YouTube и Bilibili. Файл можно скачать без публикации. На странице проекта есть история и календарь, а ещё отмена расписания, которое ещё не вышло. «Составить неделю» только для зарубежных площадок: понедельник, среда и пятница в 09:00, без Bilibili.

Вертикальные аккаунты рендерятся в 9:16 без обрезки до 60 секунд. Только Bilibili — альбомная ориентация. Только LinkedIn или X — исходный кадр. Вертикаль и Bilibili в одной отправке рендерятся по отдельности.

При публикации обложку можно создать автоматически, чтобы Bilibili не отклонил пустую обложку.

Подробности обложки и титульной карточки по умолчанию — в пояснении к установщику этого выпуска. Доступно в **v1.3.2**.

</details>


> Импорт видео → Субтитры / распознавание речи → Анализ и оценка ИИ → Клипы и подборки → Экспорт

<a id="quick-start"></a>

## Быстрый старт

| Задача | Рекомендуемый способ | Требования |
| --- | --- | --- |
| Монтаж на компьютере | **Приложение** | macOS Apple Silicon / Windows x64 |
| Свой сервер / Linux | **Docker** | Docker + Compose v2 |
| Пакетная обработка / агенты | **CLI / MCP** | Python 3.10+ (рекомендуется 3.11) + FFmpeg |

### Приложение: первые клипы

1. **Установка.** Скачайте из [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) файл `.dmg` для macOS Apple Silicon или `-setup.exe` для Windows 10 / 11 x64. Python и FFmpeg включены. Для Intel Mac / Linux используйте Docker или CLI. Системные требования указаны в описании выпуска.
2. **Настройка модели.** Выберите провайдера в настройках, введите ключ API и имя модели, проверьте соединение и сохраните. Для локальных моделей сначала запустите Ollama или LM Studio.
3. **Импорт видео.** Начните с фрагмента длиной 3–5 минут; можно добавить субтитры SRT. Если субтитров нет, сначала подготовьте локальные компоненты Whisper и речевую модель в настройках.
4. **Проверка и экспорт.** Проверьте границы клипов, заголовки и содержание, затем выберите профиль экспорта или подключите аккаунт для публикации.

[Полная инструкция по установке (англ.)](docs/USER_INSTALLATION_GUIDE.en.md) · [Решение проблем (англ.)](docs/FAQ.en.md)

<details>
<summary><strong>Docker / Web</strong></summary>

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

</details>

<details>
<summary><strong>CLI / MCP</strong></summary>

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

**Быстрое создание в версии 1.5** использует настройки моделей, сохранённые в настольном приложении, для создания видео под платформу, обложек, текстов публикаций и ZIP-пакетов:

```bash
autoclip --version
autoclip produce talk.mp4 --srt talk.srt --platform douyin --portrait-style podcast --json
autoclip outputs PROJECT_ID --export-kits
```

В MCP используйте `start_quick_output` + `get_quick_output_status` с теми же платформами и вертикальными макетами. Установка и совместное тестирование описаны в [отчёте о проверке версии 1.5](docs/RELEASE_1_5.md) (на китайском).

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

</details>

## Настройка моделей

| Вариант | Настройка |
| --- | --- |
| Облачные модели | Выберите провайдера в настройках и укажите свой ключ API и модель. Для совместимых с OpenAI сервисов можно задать Base URL. |
| Ollama | Адрес по умолчанию: `http://localhost:11434/v1`; модель: `qwen2.5:7b`. API-ключ не нужен. |
| LM Studio | Загрузите модель и запустите Local Server, по умолчанию на `http://localhost:1234/v1`. Выберите модель, доступную на вашем сервере. |

В Docker адрес `localhost` указывает на сам контейнер. Для доступа к модели на хосте задайте адрес, доступный из контейнера; см. руководство по CLI / MCP. Нарезка видео выполняется локально, но при анализе облачной моделью текст субтитров отправляется выбранному провайдеру. Для скачивания видео и моделей нужен интернет.

[Infistar · Инструкция по настройке (англ.)](docs/INFISTAR_SETUP.en.md)

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

Подготовка образцов и ссылки на общедоступные видео описаны в [руководстве по первым клипам (англ.)](docs/USER_INSTALLATION_GUIDE.en.md).

</details>

[Полное руководство по устранению неполадок (английский)](docs/FAQ.en.md) · [Известные проблемы](https://github.com/zhouxiaoka/autoclip/issues/96)

<a id="documentation"></a>

## Документация

| Тема | Документация |
| --- | --- |
| Начало работы | [Установка (англ.)](docs/USER_INSTALLATION_GUIDE.en.md) |
| Развёртывание и автоматизация | [Docker (англ.)](docs/DOCKER.en.md) · [CLI / MCP (кит.)](docs/CLI_AND_MCP.md) · [Agent skill (кит.)](skills/autoclip/SKILL.md) |
| Модели и решение проблем | [Настройка моделей (кит.)](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [Решение проблем (англ.)](docs/FAQ.en.md) |
| Версии и конфиденциальность | [История изменений](CHANGELOG.md) · [Конфиденциальность (англ.)](docs/PRIVACY.en.md) |
| Разработка и перевод | [Участие в разработке (кит.)](CONTRIBUTING.md) · [Поддержка переводов (кит.)](docs/i18n.md) |
| Настройка сервиса спонсора | [Infistar](docs/INFISTAR_SETUP.en.md) |

README доступен на восьми языках. Руководства по установке, Docker и решению проблем есть на английском; остальные подробные материалы преимущественно на китайском.

## Участие и обратная связь

Приветствуются исправления, отзывы и улучшения переводов. В сообщении об ошибке укажите ОС, версию, модель, шаги воспроизведения и журналы ошибок без конфиденциальных данных.

Проект поддерживает один человек в свободное время. Срок ответа не фиксирован; мгновенная поддержка и индивидуальная помощь с развёртыванием не предоставляются. Перед обращением прочитайте FAQ и список известных проблем.

Идеи, сценарии и запросы моделей публикуйте в [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions). Воспроизводимые ошибки оформляйте через [шаблон issue](https://github.com/zhouxiaoka/autoclip/issues/new/choose). Правила доски: [community board](docs/COMMUNITY_BOARD.md) (на китайском).

- [Приветствие и категории](https://github.com/zhouxiaoka/autoclip/discussions/127)
- [Вопросы о первом клипе](https://github.com/zhouxiaoka/autoclip/discussions/128)
- [Идеи](https://github.com/zhouxiaoka/autoclip/discussions/129)

- Электронная почта: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Спасибо проектам FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper и всем участникам. Проект распространяется по [лицензии MIT](LICENSE). Если AutoClip вам помогает, поддержите проект звездой.

<details>
<summary>Признание сообщества · Star History</summary>

Эти значки предоставляет Trendshift. Нажмите на них, чтобы посмотреть достижения AutoClip. GitHub Trending и Trendshift — разные рейтинги; значки показывают зафиксированные достижения, а не текущую позицию.

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)

</details>
