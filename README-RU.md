<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="80" height="80">

# AutoClip

**Находите яркие моменты в видео с помощью ИИ и создавайте короткие HD-ролики в один клик.**

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · **Русский** · [Français](README-FR.md)

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/forks)
[![GitHub issues](https://img.shields.io/github/issues/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/issues)
[![License: MIT](https://img.shields.io/github/license/zhouxiaoka/autoclip?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — Trendshift" width="250" height="55"></a>
</p>

Бесплатно и с открытым кодом · Локальный монтаж · Облачные и локальные модели

[Сайт проекта](https://zhouxiaoka.github.io/autoclip_intro/) · [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [Сообщить о проблеме](https://github.com/zhouxiaoka/autoclip/issues)

**Установщики приложения: [macOS · Apple Silicon](https://github.com/zhouxiaoka/autoclip/releases/latest) · [Windows · x64](https://github.com/zhouxiaoka/autoclip/releases/latest)**

[Установка и первые клипы (English)](docs/USER_INSTALLATION_GUIDE.en.md) · [Полное руководство по устранению неполадок (английский)](docs/FAQ.en.md)

</div>

Превращайте интервью, подкасты, лекции и записи трансляций в короткие ролики. AutoClip находит интересные моменты, придумывает заголовки и создаёт клипы и подборки, которые можно отредактировать и экспортировать.

## Интерфейс

![Экран импорта видео AutoClip](docs/images/import-local.jpg)

Импортируйте локальное видео и при необходимости субтитры SRT. На скриншоте показан интерфейс на китайском языке.

## Возможности

| Функция | Описание |
| --- | --- |
| Импорт видео | Локальные файлы, ссылки YouTube и Bilibili. |
| Поиск ярких моментов | Анализ субтитров, подбор фрагментов, создание заголовков и хронологии тем. |
| Монтаж клипов | Создание клипов и подборок; настройка начала и конца, текста и соотношения сторон. |
| Игровые моменты | Поиск событий в записях игр. Требуется настроить визуальную модель и включить анализ игр; облачные вызовы оплачиваются провайдеру. [Настройка (китайский)](docs/MULTI_LLM_PROVIDER_GUIDE.md). |
| Экспорт и публикация | Горизонтальные и вертикальные видео, субтитры, титульные карточки, автоматические обложки, публикация сразу или по расписанию. [Руководство (китайский)](docs/PUBLISH_UPLOAD_POST.md). |
| Модели и автоматизация | Qwen, OpenAI, Gemini, DeepSeek и другие облачные модели, а также локальные модели через Ollama / LM Studio. Доступны CLI и MCP. |

> Импорт → Подтверждение типа видео → Анализ и монтаж с ИИ → Правки и экспорт

## Быстрый старт

1. **Установите приложение.** Скачайте `.dmg` для macOS Apple Silicon или `-setup.exe` для Windows x64 из [GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases/latest). Python и FFmpeg включены.
2. **Настройте модель.** В настройках укажите свой API Key или подключите локальную модель, проверьте соединение и сохраните.
3. **Создайте клипы.** Импортируйте видео и подтвердите его тип, чтобы запустить анализ и монтаж. Проверьте результат, внесите правки и экспортируйте.

Установка, импорт и сохранение на физическом компьютере с Windows ещё ожидают проверки. Для Intel Mac и Linux доступны Docker и CLI.

[Установка (английский)](docs/USER_INSTALLATION_GUIDE.en.md) · [Решение проблем (английский)](docs/FAQ.en.md)

<details>
<summary>Docker / Web, CLI и MCP</summary>

- **Docker / Web:** Разверните веб-интерфейс по [руководству Docker (английский)](docs/DOCKER.en.md).
- **CLI:** Пакетная обработка и скрипты описаны в [руководстве CLI (китайский)](docs/CLI_AND_MCP.md).
- **MCP:** Подключите клиент по тому же руководству или используйте [Agent skill (китайский)](skills/autoclip/SKILL.md).

</details>

## Частые вопросы

<details>
<summary>Сколько это стоит?</summary>

AutoClip — бесплатный проект с открытым кодом под лицензией MIT. Для облачных моделей нужен собственный API Key; оплату взимает провайдер. Локальные модели Ollama / LM Studio не требуют облачного ключа. Для публикации на международных платформах нужен свой аккаунт [Upload-Post](https://www.upload-post.com); тарифы и лимиты указаны на его сайте.

</details>

<details>
<summary>Загружается ли видео в облако?</summary>

Монтаж и рендеринг выполняются на вашем компьютере. При облачном анализе субтитров отправляется соответствующий текст, при визуальном анализе — выбранные кадры и необходимый текст. При публикации готовое видео загружается на подключённые платформы. Можно ограничиться локальным экспортом. [Конфиденциальность (английский)](docs/PRIVACY.en.md).

</details>

<details>
<summary>Можно ли работать без субтитров?</summary>

Да. Настройте локальный Whisper и речевую модель для расшифровки или импортируйте готовый SRT. Для начала попробуйте короткое видео с субтитрами по [руководству (английский)](docs/USER_INSTALLATION_GUIDE.en.md).

</details>

<details>
<summary>Какие видео подходят? Есть ли экспорт в HD?</summary>

Анализ субтитров подходит для интервью, подкастов, лекций и разговорных видео. Для записей игр доступен визуальный анализ. Поддерживается горизонтальный и вертикальный экспорт в 1080p; качество зависит от исходника и настроек. Время обработки зависит от длительности видео, модели и оборудования.

</details>

## Поддержать проект

Мы приветствуем спонсорскую поддержку от компаний и частных лиц для дальнейшей разработки и сопровождения AutoClip. Компании-спонсоры могут разместить в README информацию о своём бренде и услугах.

По вопросам спонсорства : [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

## Документация и сообщество

- [Установка (английский)](docs/USER_INSTALLATION_GUIDE.en.md) · [Модели (китайский)](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [Помощь (английский)](docs/FAQ.en.md)
- [История изменений (китайский)](CHANGELOG.md) · [Документация (китайский)](docs/README.md)
- Вопросы и идеи приветствуются в [Discussions](https://github.com/zhouxiaoka/autoclip/discussions), сообщения об ошибках — в [Issues](https://github.com/zhouxiaoka/autoclip/issues/new/choose).
- Приглашаем улучшать код, документацию и переводы. [Руководство для участников (китайский)](CONTRIBUTING.md).
- Контакты и спонсорство: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

Спасибо всем участникам и проектам FastAPI, React, Tauri, FFmpeg, yt-dlp и Whisper. Если AutoClip вам полезен, поддержите проект звездой.

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)
