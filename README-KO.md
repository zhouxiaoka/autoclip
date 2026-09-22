<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="80" height="80">

# AutoClip

**긴 영상에서 공유하고 싶은 순간을 찾아보세요.**

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · **한국어** · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/forks)
[![GitHub issues](https://img.shields.io/github/issues/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/issues)
[![License: MIT](https://img.shields.io/github/license/zhouxiaoka/autoclip?style=flat-square)](LICENSE)

[웹사이트](https://zhouxiaoka.github.io/autoclip_intro/) · [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [문제 신고](https://github.com/zhouxiaoka/autoclip/issues)

**데스크톱 설치 파일: [macOS · Apple Silicon](https://github.com/zhouxiaoka/autoclip/releases/latest) · [Windows · x64](https://github.com/zhouxiaoka/autoclip/releases/latest)**

[설치와 첫 클립 만들기 (English)](docs/USER_INSTALLATION_GUIDE.en.md) · [전체 문제 해결 가이드(영어)](docs/FAQ.en.md)

</div>

v1.3.1부터 앱, 웹사이트, README는 중국어, 영어, 일본어, 한국어, 스페인어, 포르투갈어, 러시아어, 프랑스어를 지원합니다. 상단에서 언어를 선택하거나 시스템 설정을 따를 수 있습니다. 원본 미디어와 생성 콘텐츠의 언어는 변경되지 않습니다.

AutoClip은 AI로 영상 자막을 분석하고 하이라이트를 찾아 제목, 클립, 모음 영상을 자동으로 만듭니다. 인터뷰, 팟캐스트, 강의, 라이브 방송 녹화에 적합하며 데스크톱 앱, Docker 웹 UI, CLI / MCP로 사용할 수 있습니다.

## 화면 미리보기

![AutoClip v1.3.0 — local video import](docs/images/import-local.jpg)

v1.3.0의 실제 웹 화면입니다. 파일 가져오기 영역에서 로컬 영상과 선택 사항인 SRT 자막을 추가할 수 있습니다.

## 커뮤니티 성과

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily?language=Python" alt="AutoClip — Trendshift Python daily ranking" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily" alt="AutoClip — Trendshift daily ranking, all languages" width="250" height="55"></a>
</p>

아래 배지는 Trendshift에서 제공합니다. 클릭하면 AutoClip의 순위 기록을 확인할 수 있습니다. GitHub Trending과 Trendshift는 서로 다른 순위이며, 배지는 현재 실시간 순위가 아닌 기록된 성과를 보여 줍니다.

## 주요 기능

| 기능 | 설명 |
| --- | --- |
| 영상 가져오기 | 로컬 영상, YouTube 및 Bilibili 링크를 지원하며 SRT 자막을 추가할 수 있습니다. |
| 하이라이트 찾기 | 자막에서 개요, 주제별 시간 구간, 하이라이트 점수, 클립 제목을 추출합니다. |
| 클립과 모음 영상 | 클립과 추천 모음 영상을 생성하고 순서를 직접 조정할 수 있습니다. |
| 게시용 내보내기 | Douyin, Xiaohongshu, YouTube Shorts, Bilibili 프리셋과 자막 삽입, 타이틀 카드를 지원합니다. |
| 모델 선택 | Qwen, OpenAI 호환 API, Gemini, SiliconFlow, Ollama / LM Studio의 로컬 모델을 사용할 수 있습니다. |
| 자동화 | CLI로 작업을 구성하거나 MCP 클라이언트에서 동일한 처리 파이프라인을 호출할 수 있습니다. |

> 영상 가져오기 → 자막 준비 / 음성 전사 → AI 분석 및 평가 → 클립과 모음 영상 생성 → 내보내기

## 빠른 시작

### 1. 데스크톱 앱

[GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases/latest)에서 운영체제에 맞는 설치 파일을 다운로드하세요.

| 플랫폼 | 설치 방법 |
| --- | --- |
| macOS · Apple Silicon | `.dmg` |
| Windows 10 / 11 · x64 | `-setup.exe` |
| Intel Mac / Linux | 아래의 Docker 또는 CLI 사용 |

데스크톱 설치 파일에는 Python과 FFmpeg가 포함됩니다. 지원 플랫폼과 첫 실행 방법은 해당 릴리스를 확인하세요. 설치 후 설정에서 모델 제공업체를 선택하고 연결 테스트와 저장을 마친 뒤 영상을 가져오세요.

### 2. Docker / Web

Docker와 Docker Compose v2가 필요합니다. 저장소 루트에서 실행하세요.

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
```

```bash
cp env.example .env
```

시작 전에 `.env`에서 `LLM_PROVIDER`, 해당 API 키와 모델 이름을 설정하세요. 실행 후 설정 화면에서도 구성할 수 있습니다.

```bash
mkdir -p data logs uploads
docker compose up -d --build
```

[웹 UI](http://localhost:3000)를 여세요. 백엔드가 시작되면 [API 문서](http://localhost:8000/docs)를 볼 수 있습니다. 자세한 내용은 [Docker 가이드](DOCKER.md)(중국어)를 참고하세요.

Linux에서 바인드 마운트 디렉터리의 권한 오류가 발생하면 아래 명령으로 프로젝트 데이터 디렉터리의 소유권을 수정한 뒤 서비스를 다시 시작하세요.

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

### 3. CLI / MCP

Python 3.10 이상(3.11 권장)과 PATH에 등록된 FFmpeg가 필요합니다. 아래 예시는 macOS / Linux 셸 기준입니다. Windows PowerShell에서는 `venv\Scripts\Activate.ps1`로 가상 환경을 활성화하세요. CLI 로컬 처리에는 Redis가 필요하지 않습니다.

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
```

로컬 모델 예시: Ollama를 설치하고 실행한 뒤 모델을 다운로드하세요. 자막이 없는 영상에는 `faster-whisper`가 필요하며 첫 전사 시 음성 모델을 다운로드합니다. 기존 자막을 사용하려면 `--srt talk.srt`를 추가하세요.

```bash
ollama pull qwen2.5:7b
python -m pip install faster-whisper
autoclip doctor --provider ollama
autoclip run talk.mp4 --provider ollama --json
```

`PROJECT_ID`를 처리 결과의 프로젝트 ID로 바꾸면 Shorts 형식으로 내보낼 수 있습니다. `autoclip mcp`는 stdio MCP 서버를 시작합니다.

```bash
autoclip export PROJECT_ID --preset shorts
autoclip mcp
```

MCP 클라이언트의 `command`에는 가상 환경 내 `autoclip`의 절대 경로를, `args`에는 `["mcp"]`를 설정하세요. [CLI / MCP 가이드](docs/CLI_AND_MCP.md)와 [Agent skill](skills/autoclip/SKILL.md)(중국어)을 참고하세요.

## 모델 설정

| 방식 | 설정 |
| --- | --- |
| 클라우드 모델 | 설정에서 Qwen, OpenAI 호환 API, Gemini 또는 SiliconFlow를 선택하고 API 키를 입력하세요. 호환 API는 Base URL을 변경할 수 있습니다. |
| Ollama | 기본 주소는 `http://localhost:11434/v1`, 모델은 `qwen2.5:7b`입니다. API 키가 필요하지 않습니다. |
| LM Studio | 모델을 로드하고 Local Server를 시작하세요. 기본 주소는 `http://localhost:1234/v1`이며 서버가 제공하는 모델을 선택해야 합니다. |

Docker 내부의 `localhost`는 컨테이너 자체를 가리킵니다. 호스트의 모델을 사용하려면 컨테이너에서 접근 가능한 주소를 설정하세요. 자세한 내용은 CLI / MCP 가이드에 있습니다. 영상 자르기는 로컬에서 수행하지만 클라우드 모델 분석은 선택한 제공업체에 자막 텍스트를 전송합니다. 영상과 모델 다운로드에는 인터넷이 필요합니다.

## 자주 묻는 질문

<details>
<summary>무료인가요? API 키가 필요한가요?</summary>

AutoClip은 MIT 라이선스의 무료 오픈 소스입니다. 클라우드 모델은 제공업체의 요금이 적용되며 본인의 API 키가 필요합니다. Ollama / LM Studio는 클라우드 키가 필요 없지만 모델 파일과 적절한 하드웨어가 필요합니다.

</details>

<details>
<summary>영상이 업로드되나요?</summary>

로컬 편집은 사용자 기기에서 수행됩니다. 클라우드 모델 분석에는 자막 텍스트를 전송합니다. 게시 / 업로드 기능을 사용하면 대상 플랫폼으로 영상이 전송됩니다. 통계와 오류 보고는 버전 및 설정에 따라 달라지므로 개인정보 안내를 확인하세요.

</details>

<details>
<summary>자막이 없어도 사용할 수 있나요?</summary>

네. 먼저 로컬 Whisper 구성 요소와 음성 모델을 준비하세요. 기존 SRT 자막을 함께 가져올 수도 있습니다. 정확한 자막이 있으면 전사 시간과 인식 오류를 줄일 수 있습니다.

</details>

<details>
<summary>클립이 생성되지 않는 이유는 무엇인가요?</summary>

실패한 단계에서 빈 자막, 모델 연결, 너무 높은 점수 기준, FFmpeg 및 디스크 상태를 확인하세요. 기준을 0.7에서 0.5로 낮춰 볼 수 있지만 클립 생성을 보장하지는 않습니다.

</details>

<details>
<summary>어떤 영상에 적합하며 얼마나 걸리나요?</summary>

주로 자막을 분석하므로 인터뷰, 팟캐스트, 강의, 해설 영상에 적합합니다. 시각적 동작이나 음악 중심 영상은 한계가 있을 수 있습니다. 영상 길이, 하드웨어, 모델, 내보내기 설정에 따라 시간이 달라지므로 짧은 영상부터 확인하세요.

</details>

[전체 문제 해결 가이드(영어)](docs/FAQ.en.md) · [알려진 문제](https://github.com/zhouxiaoka/autoclip/issues/96)

## 문서

README는 8개 언어로 제공되며 아래 상세 문서는 대부분 중국어입니다. README 번역 언어와 앱 UI 또는 전사 모델의 지원 언어는 별개입니다.

- [설치와 첫 클립 만들기 (English)](docs/USER_INSTALLATION_GUIDE.en.md)
- [Docker 배포(중국어)](DOCKER.md)
- [CLI, MCP 및 로컬 모델(중국어)](docs/CLI_AND_MCP.md)
- [모델 제공업체 설정(중국어)](docs/MULTI_LLM_PROVIDER_GUIDE.md)
- [자주 묻는 질문(중국어)](docs/FAQ.md)
- [기여 가이드(중국어)](CONTRIBUTING.md)
- [변경 기록](CHANGELOG.md)
- [개인정보 안내(중국어 / 영어)](docs/PRIVACY.en.md)
- [README 번역 및 배지 관리(중국어)](docs/i18n.md)

## 기여 및 연락처

코드 수정, 피드백, 번역 개선을 환영합니다. 버그를 신고할 때 OS, 버전, 모델, 재현 단계, 민감한 정보를 제거한 오류 로그를 함께 보내 주세요.

개인이 여가 시간에 유지 관리합니다. 답변 시점은 일정하지 않으며 실시간 지원이나 일대일 설치 지원은 제공하지 않습니다. 연락 전에 FAQ와 알려진 문제를 확인해 주세요.

기능 아이디어, 사용 사례, 모델 요청은 [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions)에 올려 주세요. 재현 가능한 버그는 [Issue 템플릿](https://github.com/zhouxiaoka/autoclip/issues/new/choose)을 사용합니다. 규칙은 [커뮤니티 보드](docs/COMMUNITY_BOARD.md)(중국어)에 있습니다.

- [안내와 분류](https://github.com/zhouxiaoka/autoclip/discussions/127)
- [첫 클립 Q&A](https://github.com/zhouxiaoka/autoclip/discussions/128)
- [아이디어](https://github.com/zhouxiaoka/autoclip/discussions/129)

- 이메일: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper와 모든 기여자에게 감사드립니다. [MIT License](LICENSE)로 배포됩니다. AutoClip이 도움이 되었다면 Star로 응원해 주세요.

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)
