<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### 링크 하나, 클릭 한 번.

오픈 소스, 무료, 내 컴퓨터에서 실행. 링크를 붙이고 몇 푼이면 <b>바로 올릴 수 있는 클립 10개 이상</b>을 받습니다.<br>
표지, 제목, 설명, 해시태그까지 抖音·小红书·TikTok·Reels·YouTube Shorts용으로 맞춰 줍니다.<br>
편집기도, AI 와의 긴 대화도 필요 없습니다.

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

## 실제 완성 클립

![AutoClip 세로 클립: 小红书 인터뷰, TikTok 팟캐스트, 抖音 인터뷰, Shorts 팟캐스트](docs/images/v2/demo-wall.webp)

원본은 링크 하나뿐입니다. 위 클립은 AutoClip이 고르고, 구도를 잡고, 번역하고, 포장한 원본 출력입니다. 손 편집 없음. **[사례 라이브러리에서 소리와 함께 보기 →](https://zhouxiaoka.github.io/autoclip_intro/cases/)**

각 클립은 대상 플랫폼용 세트입니다. 세로 영상, 표지, 제목, 설명, 해시태그. 라이브러리는 자주 갱신됩니다. [올리기](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell).

원본 저작권은 원작자에게 있습니다. 효과 시연: [Dwarkesh Patel — Dario Amodei](https://www.youtube.com/watch?v=n1E9IZfvGMA) · [Y Combinator — Sam Altman](https://www.youtube.com/watch?v=ZIaOBAjvc38) · [WIRED — Hideo Kojima](https://www.youtube.com/watch?v=02Ah5VQrzvA)

## 무엇을 하나요

### 링크만 붙이면 됩니다
편집기도 AI 채팅도 없습니다. 플랫폼을 고르면 화면비에 맞춰 생성. 표지·제목·설명·해시태그 포함.

### 포장은 자동
抖音 / 小红书는 인터뷰형, TikTok / Reels / Shorts는 팟캐스트형. 화면은 화자를 따라가고, 외국어는 현지어 제목과 이중 자막.

### 내 컴퓨터에서
자르기와 렌더는 로컬. 모델은 직접 고르고, 고칠 때만 편집기, 대량은 CLI / MCP.

## 빠르고 저렴합니다

링크 하나 넣으면 **10개 이상** 바로 올릴 클립. 표지·제목·설명·해시태그 포함.

| 버전 | 원본 | 결과 | 비용 |
| --- | --- | ---: | ---: |
| **신판 · 자막 있음** | Jensen · 1h43m (영 → 小红书) | **7.5분 / 10개** | **¥0.09** |
| 신판 · 자막 없음 | TIM × 뤄융하오 · 2h52m (중 → 抖音) | 29.5분 / 10개 | ¥0.20 |
| 구판 | MrBeast · 2h06m (영 → TikTok) | 65분 | ¥0.64 |

2–3시간 인터뷰는 보통 ¥0.1–0.2. 제작자 자막이 없으면 음성 인식은 로컬에서, 시간이 더 걸립니다. 영상은 컴퓨터를 떠나지 않습니다.

<details>
<summary>측정 조건</summary>

2026년 10월 1일, 같은 Apple Silicon Mac, 분석 모델 qwen-plus (백만 tokens 입력 ¥0.8 / 출력 ¥2, 알리클라우드 백롄 제3자 가격). 비용은 모델 호출만.

Jensen 7.5분: 다운로드 약 1분, 제작자 자막으로 전사 생략, 하이라이트 25초, 컷/구도/포장 약 2.5분, 10개 렌더 약 3분. 구판은 하이라이트만 35분.

이번 판의 네 가지: 전체 자막 한 번에 하이라이트, 모델 호출 병렬, 제작자 자막이 있으면 로컬 ASR 생략, 기본은 상위 10개만 렌더.

</details>

## 월간 클라우드 도구와 비교

| | AutoClip | 월간 클라우드 도구 |
| --- | --- | --- |
| 비용 | 앱 무료. 모델은 종량. 2–3시간 인터뷰 약 ¥0.1–0.2 | 월 구독, 처리 시간 과금 |
| 영상 처리 위치 | 내 컴퓨터. 클라우드는 자막 텍스트만 | 업체 클라우드에 업로드 |
| 모델 | 직접 선택, 로컬 가능 | 플랫폼 지정 |
| 중국 플랫폼 | 抖音, 小红书, Bilibili 템플릿 | 해외 위주 |
| 코드 | MIT, 수정·자체 배포 가능 | 비공개 |

오른쪽은 2026년 10월 유사 클라우드 제품 공개 페이지 기준입니다. 최신 안내는 각 제품을 보세요.

## 빠른 시작

| 하고 싶은 일 | 추천 | 준비물 |
| --- | --- | --- |
| 이 컴퓨터에서 만들기 | **데스크톱** | macOS Apple Silicon 또는 Windows x64 |
| 자체 웹 / Linux | **Docker** | Docker와 Compose v2 |
| 대량 / Agent | **CLI / MCP** | Python 3.10+ (3.11 권장)와 FFmpeg |

### 데스크톱

1. **설치.** [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest)에서. macOS Apple Silicon은 `.dmg`, Windows 10 / 11 x64는 `-setup.exe`. Python과 FFmpeg 포함.
2. **모델.** 설정에서 제공자를 고르고 API Key를 넣으면 분석 모델은 자동. 로컬이면 먼저 Ollama 또는 LM Studio 실행.
3. **링크를 붙이고 플랫폼을 고르세요.** 자막 있는 10–30분 인터뷰부터. 자막이 없으면 설정에서 Whisper 또는 SenseVoice.
4. **받기.** 상위 10개를 보고, 필요하면 고친 뒤 받거나 게시.

설치 파일은 아직 Apple 공증·Windows 서명이 없습니다. macOS는 처음 우클릭「열기」, Windows는 SmartScreen에서「추가 정보 → 실행」.

[설치 가이드](docs/USER_INSTALLATION_GUIDE.en.md) · [문제 해결](docs/FAQ.en.md)

**Docker / Web**

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env          # 选择 LLM_PROVIDER，填 API Key 和模型名；也可以启动后在设置页配置
mkdir -p data logs uploads
docker compose up -d --build
```

[웹 UI](http://localhost:3000)를 엽니다. [API 문서](http://localhost:8000/docs)는 백엔드 기동 후. [Docker 가이드](docs/DOCKER.en.md).

Linux에서 바인드 권한 오류가 나면 소유권을 먼저 고칩니다.

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

**CLI / MCP**

Python 3.10+(3.11 권장)와 PATH의 FFmpeg. CLI 로컬 처리에 Redis는 필요 없습니다.

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

MCP 클라이언트에서 `command`는 가상환경 `autoclip` 절대 경로, `args`는 `["mcp"]`. [CLI / MCP](docs/CLI_AND_MCP.md)(중국어), [OpenCode](docs/OPENCODE.en.md), [Agent skill](skills/autoclip/SKILL.md)(중국어).

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
<summary>유료인가요? API Key가 필요한가요?</summary>

AutoClip은 무료 MIT. 클라우드 모델은 제공자 종량과 본인 Key. 1시간 43분 인터뷰 약 ¥0.09. Ollama / LM Studio는 클라우드 Key 없이 하드웨어만. 해외 게시는 본인 [Upload-Post](https://www.upload-post.com) 계정.

</details>

<details>
<summary>영상이 업로드되나요?</summary>

자르기와 렌더는 기기에서. 클라우드 모델은 자막 텍스트만. 완성 클립은「게시」를 누른 뒤 연결한 곳으로만. 분석과 오류 보고는 설정에서 끌 수 있습니다. [개인정보](docs/PRIVACY.en.md).

</details>

<details>
<summary>어떤 영상이 잘 되나요?</summary>

자막 기반이라 인터뷰·팟캐스트·강의·토크에 맞습니다. 제작자 자막이 가장 빠르고, 없으면 로컬 전사. 액션·음악만은 제한적.

</details>

<details>
<summary>클립이 안 나옵니다.</summary>

실패 단계: 빈 자막, 모델 연결, FFmpeg, 디스크. 더 강한 모델을 시도. 계속되면 [알려진 문제](https://github.com/zhouxiaoka/autoclip/issues/96)에 종류·길이·모델을 적으세요.

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
