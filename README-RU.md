<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### Одна ссылка — один клик.

Открытый код, бесплатно, на вашем компьютере. Вставьте ссылку, потратьте несколько центов и получите <b>10+ готовых клипов</b>,<br>
каждый с обложкой, заголовком, описанием и хештегами для Douyin, Xiaohongshu, TikTok, Reels или YouTube Shorts.<br>
Без монтажки. Без долгого диалога с ИИ.

<p>
  <a href="https://github.com/zhouxiaoka/autoclip/releases/latest"><img src="https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square" alt="GitHub release"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/stargazers"><img src="https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square" alt="GitHub stars"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/releases"><img src="https://img.shields.io/github/downloads/zhouxiaoka/autoclip/total?style=flat-square" alt="Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License: MIT"></a>
</p>

<a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>

**[Скачать десктоп](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [Кейсы](https://zhouxiaoka.github.io/autoclip_intro/cases/) · [Быстрый старт](#быстрый-старт) · [Документация](#документация) · [Ошибка](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · **Русский** · [Français](README-FR.md)

</div>

## Настоящие клипы

![Вертикальные клипы AutoClip: интервью Xiaohongshu, подкаст TikTok, интервью Douyin, подкаст Shorts](docs/images/v2/demo-wall.webp)

Каждый исходник — одна вставленная ссылка. Каждый клип выше — сырой вывод AutoClip: выбор, кадр, перевод, упаковка, без ручной правки. **[Смотреть со звуком в библиотеке →](https://zhouxiaoka.github.io/autoclip_intro/cases/)**

Каждый клип — полный набор для площадки: вертикальное видео, обложка, заголовок, описание, хештеги. Библиотека обновляется; [пришлите свои](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell).

Права на исходник остаются у авторов. Примеры: [Dwarkesh Patel — Dario Amodei](https://www.youtube.com/watch?v=n1E9IZfvGMA) · [Y Combinator — Sam Altman](https://www.youtube.com/watch?v=ZIaOBAjvc38) · [WIRED — Hideo Kojima](https://www.youtube.com/watch?v=02Ah5VQrzvA)

## Что умеет

### Вставил ссылку — получил клипы
Без монтажки и чата с ИИ. Выберите площадку и получите нужный кадр. Обложка, заголовок, описание и хештеги уже внутри.

### Упаковка встроена
Интервью для Douyin / Xiaohongshu; подкаст для TikTok / Reels / Shorts. Кадр следит за говорящим; иностранный материал получает локальный заголовок и двуязычные субтитры.

### Остаётся на компьютере
Нарезка и рендер локальные. Модель выбираете сами, редактор — только если хотите поправить, пакеты — через CLI / MCP.

## Быстро и дёшево

Одна ссылка на входе, **10+** готовых клипов на выходе, каждый с обложкой, заголовком, описанием и хештегами.

| Версия | Исходник | Выход | Стоимость |
| --- | --- | ---: | ---: |
| **Новая · есть субтитры** | Jensen · 1ч43м (EN → Xiaohongshu) | **7,5 мин / 10 клипов** | **¥0,09** |
| Новая · без субтитров | TIM × Ло Юнхао · 2ч52м (ZH → Douyin) | 29,5 мин / 10 клипов | ¥0,20 |
| Старая | MrBeast · 2ч06м (EN → TikTok) | 65 мин | ¥0,64 |

Интервью на 2–3 часа обычно ¥0,1–0,2. Без авторских субтитров распознавание речи локальное и дольше; видео не покидает машину.

<details>
<summary>Как сняты эти цифры</summary>

1 октября 2026, тот же Mac Apple Silicon, модель анализа qwen-plus (¥0,8 / ¥2 за миллион входных / выходных токенов, сторонний прайс Aliyun Bailian). В стоимость входят только вызовы модели.

7,5 мин Jensen: ~1 мин скачивание, без ASR благодаря авторским субтитрам, 25 с отбор, ~2,5 мин нарезка / кадр / упаковка, ~3 мин рендер 10 штук. Старая сборка тратила 35 мин только на отбор.

В этой версии четыре отличия: один проход по всей расшифровке; параллельные вызовы; пропуск локального ASR при авторских субтитрах; по умолчанию рендерятся только топ-10.

</details>

## Сравнение с облачной подпиской

| | AutoClip | Облачные инструменты по подписке |
| --- | --- | --- |
| Стоимость | Приложение бесплатно; модель — по факту, ~¥0,1–0,2 за 2–3 ч | Ежемесячная подписка, по времени обработки |
| Где обрабатывается видео | Ваш компьютер; в облако уходит только текст | Загрузка в облако поставщика |
| Модели | Выбираете сами, в том числе локальные | Задаёт площадка |
| Китайские площадки | Шаблоны Douyin, Xiaohongshu, Bilibili | В основном зарубежные |
| Код | MIT, можно менять и хостить | Закрытый |

Правый столбец по открытым страницам похожих облачных продуктов на октябрь 2026; сверяйте актуальные условия.

## Быстрый старт

| Задача | Способ | Нужно |
| --- | --- | --- |
| Делать клипы на этом ПК | **Десктоп** | macOS Apple Silicon или Windows x64 |
| Свой веб / Linux | **Docker** | Docker и Compose v2 |
| Пакеты / агенты | **CLI / MCP** | Python 3.10+ (лучше 3.11) и FFmpeg |

### Десктоп

1. **Установка.** Из [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest). macOS Apple Silicon: `.dmg`. Windows 10 / 11 x64: `-setup.exe`. Python и FFmpeg уже внутри.
2. **Модель.** В настройках выберите провайдера и вставьте API Key; модель анализа подставится сама. Для локальных сначала запустите Ollama или LM Studio.
3. **Вставьте ссылку и выберите площадку.** Начните с интервью или подкаста на 10–30 мин с субтитрами. Без них подготовьте Whisper или SenseVoice в настройках.
4. **Заберите клипы.** Посмотрите топ-10, при необходимости поправьте, скачайте или опубликуйте.

Установщики ещё без нотаризации Apple и подписи Windows. На macOS первый запуск — правый клик → Открыть. На Windows в SmartScreen — Подробнее → Выполнить в любом случае.

[Установка](docs/USER_INSTALLATION_GUIDE.en.md) · [Неполадки](docs/FAQ.en.md)

**Docker / Web**

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env          # 选择 LLM_PROVIDER，填 API Key 和模型名；也可以启动后在设置页配置
mkdir -p data logs uploads
docker compose up -d --build
```

Откройте [веб-интерфейс](http://localhost:3000). [API](http://localhost:8000/docs) доступна после старта бэкенда. [Гид по Docker](docs/DOCKER.en.md).

В Linux при ошибке прав на bind сначала исправьте владельца:

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

**CLI / MCP**

Нужны Python 3.10+ (лучше 3.11) и FFmpeg в PATH. Локальному CLI Redis не нужен.

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

В MCP-клиенте `command` — абсолютный путь к `autoclip` в venv, `args` — `["mcp"]`. [CLI / MCP](docs/CLI_AND_MCP.md) (кит.), [OpenCode](docs/OPENCODE.en.md), [Agent skill](skills/autoclip/SKILL.md) (кит.).

## Модели

| Способ | Настройка |
| --- | --- |
| Облачный API | Провайдер и API Key в настройках. Совместимые с OpenAI принимают Base URL. |
| Ollama | По умолчанию `http://localhost:11434/v1`, модель `qwen2.5:7b`, ключ не нужен. |
| LM Studio | Загрузите модель и запустите Local Server, по умолчанию `http://localhost:1234/v1`. |

В Docker `localhost` — сам контейнер. Для модели на хосте укажите адрес, доступный из контейнера.

[Модели](docs/MULTI_LLM_PROVIDER_GUIDE.md) (кит.) · [Локально и контейнеры](docs/CLI_AND_MCP.md) (кит.)

## Спонсоры

Спасибо партнёрам. Оба дают API, совместимый с OpenAI: выберите в настройках, вставьте ключ — появятся модели.

<table>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="72"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td valign="middle">
      Агрегатор токенов: GPT, Claude, Gemini, Grok, DeepSeek, Kimi, GLM, плюс картинка, видео и речь. Поддержка, счета, пополнение 1:1. Пробный кредит по <a href="https://88api.ai/sign-up?aff=2PIc">реферальной ссылке</a>. <a href="docs/88API_SETUP.en.md">Настройка</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="72"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar</strong></a>
    </td>
    <td valign="middle">
      Мультимодельный API: Claude, GPT, Gemini, DeepSeek и другие; часть моделей до 1% от прайса, юани, счета, проверка. $5 пробных по <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">реферальной ссылке</a>. <a href="docs/INFISTAR_SETUP.en.md">Настройка</a>
    </td>
  </tr>
</table>

Услуги, цены и акции дают партнёры; смотрите их сайты.

## Частые вопросы

<details>
<summary>Это бесплатно? Нужен ли API Key?</summary>

AutoClip бесплатен и MIT. Облачные модели тарифицирует провайдер, нужен ваш ключ; интервью на 1 ч 43 мин вышло около ¥0,09. Ollama / LM Studio без облачного ключа, но нужно железо. Зарубежная публикация — свой аккаунт [Upload-Post](https://www.upload-post.com).

</details>

<details>
<summary>Видео куда-то уходит?</summary>

Нарезка и рендер на устройстве. В облако уходит только текст. Готовый клип уходит только после «Опубликовать», на подключённые площадки. Аналитику и отчёты об ошибках можно выключить. [Конфиденциальность](docs/PRIVACY.en.md).

</details>

<details>
<summary>Какие видео лучше всего?</summary>

Анализ в основном по расшифровке: интервью, подкасты, курсы, говорящая голова. Авторские субтитры быстрее всего; без них сначала локальная транскрипция. Чистый экшен или музыка — слабо.

</details>

<details>
<summary>Почему нет клипов?</summary>

Смотрите этап сбоя: пустые субтитры, связь с моделью, FFmpeg или диск. Попробуйте более сильную модель. Если не поможет — тип, длительность и модель в [известных проблемах](https://github.com/zhouxiaoka/autoclip/issues/96).

</details>

[Неполадки](docs/FAQ.en.md) · [Известные проблемы](https://github.com/zhouxiaoka/autoclip/issues/96)

## Документация

| Нужно | Документы |
| --- | --- |
| Установка и первые клипы | [Установка](docs/USER_INSTALLATION_GUIDE.en.md) |
| Свой хостинг и автоматизация | [Docker](docs/DOCKER.en.md) · [CLI / MCP](docs/CLI_AND_MCP.md) (кит.) · [Agent skill](skills/autoclip/SKILL.md) (кит.) · [OpenCode](docs/OPENCODE.en.md) |
| Модели и сбои | [Модели](docs/MULTI_LLM_PROVIDER_GUIDE.md) (кит.) · [FAQ](docs/FAQ.en.md) |
| Версии, план, приватность | [Changelog](CHANGELOG.md) · [План](ROADMAP.md) (кит.) · [Доска](docs/COMMUNITY_BOARD.md) (кит.) · [Приватность](docs/PRIVACY.en.md) |
| Участие и перевод | [Вклад](CONTRIBUTING.md) (кит.) · [Переводы](docs/i18n.md) (кит.) |

## Участие

Правки, примеры, отзывы и переводы приветствуются. Если AutoClip помог — звезда кстати.

- **Общение:** [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [Первый клип](https://github.com/zhouxiaoka/autoclip/discussions/128) · [Идеи](https://github.com/zhouxiaoka/autoclip/discussions/129)
- **Баги:** [форма](https://github.com/zhouxiaoka/autoclip/issues/new/choose) с ОС, версией, моделью, шагами и журналами без секретов
- **Партнёрство:** [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Ведёт один человек. Живой поддержки и личного деплоя нет.

![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)

Спасибо FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper, FunASR и всем, кто вкладывается. [MIT License](LICENSE).
