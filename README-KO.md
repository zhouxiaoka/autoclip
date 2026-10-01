<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### 링크 하나, 클릭 한 번.

오픈 소스. 자르기와 렌더는 내 컴퓨터에서. 링크와 플랫폼을 고르면 <b>영상·표지·게시 문구</b>를 만듭니다.<br>
抖音·小红书·TikTok·Reels·YouTube Shorts·Bilibili·YouTube에 맞춰 줍니다.<br>
앱은 무료, 클라우드 모델은 사용량 과금. 필요할 때 편집기로 조정하세요.

<p>
  <a href="https://github.com/zhouxiaoka/autoclip/releases/latest"><img src="https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square" alt="GitHub release"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/stargazers"><img src="https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square" alt="GitHub stars"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/releases"><img src="https://img.shields.io/github/downloads/zhouxiaoka/autoclip/total?style=flat-square" alt="Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License: MIT"></a>
</p>

<a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>

**[데스크톱 받기](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [사례](https://zhouxiaoka.github.io/autoclip_intro/cases/) · [빠른 시작](#빠른-시작) · [문서](#문서) · [이슈](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · **한국어** · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

</div>

**[1.5.0 정식 출시](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0)**. 데스크톱·CLI·MCP를 함께 업데이트했습니다. 자동 제작, 자막 페이지 분할, 인물 구도, 긴 영상 대기열 수정은 [변경 기록](CHANGELOG.md)을 확인하고 이전 버전에서 업그레이드하세요.

## 실제 완성 클립

![AutoClip 세로 클립: 小红书 인터뷰, TikTok 팟캐스트, 抖音 인터뷰, Shorts 팟캐스트](docs/images/v2/demo-wall.webp)

원본은 링크 하나뿐입니다. 위 클립은 AutoClip이 고르고, 구도를 잡고, 번역하고, 포장한 원본 출력입니다. 손 편집 없음. **[사례 라이브러리에서 소리와 함께 보기 →](https://zhouxiaoka.github.io/autoclip_intro/cases/)**

플랫폼별 영상·표지·제목·설명·해시태그·ZIP 게시 패키지를 제공합니다. 사례는 계속 추가하며 [완성 클립 제출](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell)을 환영합니다.

원본 저작권은 원작자에게 있습니다. 효과 시연: [Dwarkesh Patel — Dario Amodei](https://www.youtube.com/watch?v=n1E9IZfvGMA) · [Y Combinator — Sam Altman](https://www.youtube.com/watch?v=ZIaOBAjvc38) · [WIRED — Hideo Kojima](https://www.youtube.com/watch?v=02Ah5VQrzvA)

## 무엇을 하나요

### 링크만 붙이면 됩니다

플랫폼의 화면 비율과 길이 조건에 맞춰 제작합니다. 각 플랫폼에서 조건을 만족하는 상위 최대 10개를 자동 생성하고 나머지는 요청 시 제작합니다. 표지·제목·설명·해시태그·ZIP 게시 패키지를 포함합니다.

### 포장은 자동

抖音 / 小红书 기본은 인터뷰형, TikTok / Reels / Shorts는 전체 화면 팟캐스트형. 세로 레이아웃은 선택할 수 있으며 자막과 문구 언어는 플랫폼을 따릅니다. Bilibili / YouTube는 가로형. 인물을 따라가고 인물이 없는 장면은 전체를 보존합니다. 브랜드 엔딩은 기본 켜짐, 설정에서 끌 수 있습니다. 복사한 게시 문구에 AutoClip 서명은 없습니다.

### 내 컴퓨터에서

자르기·구도·렌더는 로컬에서. 분석 모델을 선택하고 제작자 자막, 로컬 Whisper / SenseVoice, 설정한 클라우드 전사를 사용하세요. CLI / MCP도 데스크톱과 같은 자동 제작 흐름입니다.

## 실제 영상의 시간과 비용

개발 중 서로 다른 세 영상으로 측정했으며 동일 입력의 통제 비교가 아닙니다. 당시 qwen-plus 텍스트 모델 사용량 추정치로, 클라우드 ASR·AI 이미지·게시 서비스 비용은 제외합니다. 실제 청구는 제공자 기준입니다.

| 버전 | 원본 | 결과 | 텍스트 모델 추정 비용 (CNY) |
| --- | --- | ---: | ---: |
| **신판 · 자막 있음** | Jensen · 1h43m (영 → 小红书) | **7.5분 / 10개** | **¥0.09** |
| 신판 · 자막 없음 | TIM × 뤄융하오 · 2h52m (중 → 抖音) | 29.5분 / 10개 | ¥0.20 |
| 구판 | MrBeast · 2h06m (영 → TikTok) | 65분 | ¥0.64 |

<details>
<summary>측정 조건과 기록</summary>

2026-10-01, 같은 Apple Silicon Mac. 신규 흐름 두 건은 10개, 이전 흐름은 33개로 소재와 개수가 다릅니다. Jensen은 제작자 자막, TIM은 로컬 Whisper base를 사용했습니다.

제작자 자막이 있으면 전사를 생략합니다. 없으면 로컬 또는 클라우드 ASR을 선택하세요. 플랫폼과 추가 클립이 늘면 시간·사용량도 늘어납니다. [측정 기록](docs/COST_PER_VIDEO.md)(중국어).

</details>

## 모델과 데이터 흐름을 선택하세요

자르기와 렌더는 기기에서 실행합니다. 클라우드 분석에는 관련 자막·문구, 화면 이해나 참조 이미지 생성에는 필요한 샘플 프레임, 클라우드 전사에는 오디오를 보냅니다. 로컬 분석·전사에는 해당 클라우드 API가 필요 없습니다. 게시를 선택하면 완성 영상을 연결한 플랫폼으로 업로드합니다. 통계·오류 보고는 설정에서 끌 수 있습니다. [개인정보](docs/PRIVACY.en.md).

## 빠른 시작

| 하고 싶은 일 | 추천 | 준비물 |
| --- | --- | --- |
| 이 컴퓨터에서 만들기 | **데스크톱** | macOS Apple Silicon 또는 Windows x64 |
| 자체 웹 / Linux | **Docker** | Docker와 Compose v2 |
| 대량 / Agent | **CLI / MCP** | Python 3.10+ (3.11 권장)와 FFmpeg |

### 데스크톱

1. **설치.** [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest)에서. macOS Apple Silicon은 `.dmg`, Windows 10 / 11 x64는 `-setup.exe`. Python과 FFmpeg 포함.
2. **모델.** 설정에서 제공자를 고르고 API Key를 넣으면 분석 모델은 자동. 로컬이면 먼저 Ollama 또는 LM Studio 실행.
3. **링크와 플랫폼 선택.** 자막이 있는 인터뷰나 팟캐스트로 시작하고 세로 레이아웃을 고르세요. 자막이 없으면 설정에서 Whisper / SenseVoice를 준비하거나 클라우드 전사를 설정하세요.
4. **확인 후 저장.** 자막·구도·내용의 완결성을 확인하고 게시 패키지를 저장하거나 계정을 연결해 게시하세요. 더 필요하면 대체 후보를 제작하세요.

설치 파일은 아직 Apple 공증·Windows 서명이 없습니다. macOS는 처음 우클릭「열기」, Windows는 SmartScreen에서「추가 정보 → 실행」.

Intel Mac / Linux는 Docker 또는 CLI를 이용하세요. Windows 정식 패키지는 CI 설치·업그레이드·영상 흐름 검증을 통과했지만 사람의 UI 검증과 전체 관찰 기간은 아직 완료하지 않았습니다. [1.5.0 Release](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0).

[설치 가이드](docs/USER_INSTALLATION_GUIDE.en.md) · [문제 해결](docs/FAQ.en.md)

**Docker / Web**

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env
mkdir -p data logs uploads
docker compose up -d --build
```

[웹 UI](http://localhost:3000)를 엽니다. [API 문서](http://localhost:8000/docs)는 백엔드 기동 후. [Docker 가이드](docs/DOCKER.en.md).

Linux에서 바인드 권한 오류가 나면 소유권을 먼저 고칩니다.

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

LAN IP나 자체 도메인으로 접속하면 `.env`의 `AUTOCLIP_ALLOWED_ORIGINS`에 프런트엔드 주소를 쉼표로 구분해 추가하세요.

**CLI / MCP**

Python 3.10+(3.11 권장), PATH의 FFmpeg와 FFprobe가 필요합니다. Redis는 필요 없습니다. [정식 CLI / MCP ZIP](https://github.com/zhouxiaoka/autoclip/releases/download/v1.5.0/autoclip-1.5.0-cli-mcp.zip)을 풀고 해당 디렉터리에서 실행하세요:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --force-reinstall --no-deps autoclip-1.5.0-py3-none-any.whl
```

위 활성화는 macOS / Linux용입니다. Windows는 `py -m venv venv`로 만들고 `venv\Scripts\Activate.ps1`로 활성화합니다. 이전 1.5 후보 wheel은 정식 wheel을 강제 재설치해야 하며 버전 번호만 확인하면 안 됩니다.

먼저 모델 설정을 저장하세요. 데스크톱 설정을 공유하거나 ZIP의 키 없는 예제로 전용 데이터 디렉터리를 설정합니다. [CLI / MCP](docs/CLI_AND_MCP.md)(중국어). `produce`는 이전 `run --provider` 임시 설정을 쓰지 않습니다. `--srt`로 전사를 생략할 수 있습니다.

```bash
autoclip --version
autoclip produce talk.mp4 --srt talk.srt --platform douyin --portrait-style podcast --json
autoclip outputs PROJECT_ID --export-kits
autoclip mcp
autoclip mcp install opencode
```

`PROJECT_ID`는 제작 결과의 ID로 바꾸세요. MCP는 `start_quick_output` / `get_quick_output_status`. 클라이언트 `command`는 가상환경 `autoclip` 절대 경로, `args`는 `["mcp"]`. 이전 `run` / `export`와 클립 도구도 유지됩니다. [CLI / MCP](docs/CLI_AND_MCP.md)(중국어)·[OpenCode](docs/OPENCODE.en.md)·[Agent skill](skills/autoclip/SKILL.md)(중국어).

## 모델 설정

| 방식 | 설정 |
| --- | --- |
| 클라우드 API | 설정에서 제공자와 API Key. OpenAI 호환은 Base URL도 가능. |
| Ollama | 기본 `http://localhost:11434/v1`, 모델 `qwen2.5:7b`, Key 없음. |
| LM Studio | 모델을 열고 Local Server. 기본 `http://localhost:1234/v1`. |

Docker 안 `localhost`는 컨테이너입니다. 호스트 모델은 컨테이너가 닿는 주소를 쓰세요.

[모델 설정](docs/MULTI_LLM_PROVIDER_GUIDE.md)(중국어) · [로컬과 컨테이너](docs/CLI_AND_MCP.md)(중국어)

## 스폰서

AutoClip을 후원하는 파트너입니다. 둘 다 OpenAI 호환 API라 설정에서 고르고 Key를 넣으면 모델이 나열됩니다.

<table>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="72"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td valign="middle">
      GPT, Claude, Gemini, Grok, DeepSeek, Kimi, GLM과 이미지·영상·음성. 상담, 영수증, 충전 1:1. <a href="https://88api.ai/sign-up?aff=2PIc">추천 링크</a>로 체험. <a href="docs/88API_SETUP.en.md">설정</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="72"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar</strong></a>
    </td>
    <td valign="middle">
      Claude, GPT, Gemini, DeepSeek 등. 일부는 공식가 0.1할인, 위안 결제, 영수증, 모델 검증. <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">추천 링크</a>로 $5 체험. <a href="docs/INFISTAR_SETUP.en.md">설정</a>
    </td>
  </tr>
</table>

서비스·가격·혜택은 파트너 제공, 각 사이트 안내가 우선입니다.

## 자주 묻는 질문

<details>
<summary>무료인가요? API Key가 필요한가요?</summary>

앱은 무료 MIT. 클라우드 분석·전사·AI 이미지는 본인 인증 정보와 제공자 요금으로 이용합니다. 기본 자동 표지는 유료 이미지 생성 없이 제작합니다. Ollama / LM Studio는 클라우드 키가 필요 없지만 적합한 하드웨어가 필요합니다. 직접 게시에는 본인 Bilibili 또는 [Upload-Post](https://www.upload-post.com) 계정이 필요합니다.

</details>

<details>
<summary>영상이 업로드되나요?</summary>

자르기와 렌더는 기기에서 실행합니다. 클라우드 분석에는 관련 자막·문구, 화면 이해나 참조 이미지 생성에는 필요한 샘플 프레임, 클라우드 전사에는 오디오를 보냅니다. 로컬 분석·전사에는 해당 클라우드 API가 필요 없습니다. 게시를 선택하면 완성 영상을 연결한 플랫폼으로 업로드합니다. 통계·오류 보고는 설정에서 끌 수 있습니다. [개인정보](docs/PRIVACY.en.md).

</details>

<details>
<summary>어떤 영상에 적합한가요?</summary>

주로 검증한 소재는 인터뷰·팟캐스트·강의·토크입니다. 제작자 자막이 가장 빠르며 없으면 로컬/클라우드 전사를 사용합니다. 게임이나 대화가 적은 소재는 이미지 지원 모델로 화면 이해를 켜고 선택한 장면을 확인하세요.

</details>

<details>
<summary>클립이 생성되지 않아요.</summary>

자막/전사, 모델 연결, FFmpeg, 디스크, 플랫폼 조건을 확인하세요. YouTube 긴 영상은 완결된 180초 이상 클립이 필요합니다. 짧은 소재는 Shorts/Bilibili를 선택하세요. 계속 실패하면 버전·OS·길이·모델·민감 정보 없는 로그를 [알려진 문제](https://github.com/zhouxiaoka/autoclip/issues/96)에 남겨주세요.

</details>

[문제 해결](docs/FAQ.en.md) · [알려진 문제](https://github.com/zhouxiaoka/autoclip/issues/96)

## 문서

| 알고 싶은 것 | 문서 |
| --- | --- |
| 설치와 첫 클립 | [설치](docs/USER_INSTALLATION_GUIDE.en.md) |
| 자체 운영과 자동화 | [Docker](docs/DOCKER.en.md) · [CLI / MCP](docs/CLI_AND_MCP.md)(중국어) · [Agent skill](skills/autoclip/SKILL.md)(중국어) · [OpenCode](docs/OPENCODE.en.md) |
| 모델과 장애 | [모델 설정](docs/MULTI_LLM_PROVIDER_GUIDE.md)(중국어) · [FAQ](docs/FAQ.en.md) |
| 버전·로드맵·개인정보 | [변경 기록](CHANGELOG.md) · [로드맵](ROADMAP.md)(중국어) · [커뮤니티 보드](docs/COMMUNITY_BOARD.md)(중국어) · [개인정보](docs/PRIVACY.en.md) |
| 개발과 번역 | [기여](CONTRIBUTING.md)(중국어) · [번역 관리](docs/i18n.md)(중국어) |

## 참여

수정, 완성 예, 의견, 번역 개선을 환영합니다. 도움이 됐다면 Star를.

- **이야기:** [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [첫 클립 Q&A](https://github.com/zhouxiaoka/autoclip/discussions/128) · [아이디어](https://github.com/zhouxiaoka/autoclip/discussions/129)
- **버그:** [이슈 양식](https://github.com/zhouxiaoka/autoclip/issues/new/choose)에 OS, 버전, 모델, 재현, 가린 로그
- **제휴:** [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

개인 유지입니다. 즉시 지원이나 1:1 배포는 없습니다.

![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)

FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper, FunASR와 모든 기여자에게 감사합니다. [MIT License](LICENSE).
