<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### 오픈 소스 AI 하이라이트 영상 편집 도구

긴 영상에서 공유하고 싶은 순간을 찾아보세요.

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily?language=Python" alt="AutoClip — Trendshift Python daily ranking" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily" alt="AutoClip — Trendshift daily ranking, all languages" width="250" height="55"></a>
</p>

**[데스크톱 앱 다운로드](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [빠른 시작](#quick-start) · [웹사이트](https://zhouxiaoka.github.io/autoclip_intro/) · [문서](#documentation) · [문제 신고](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · **한국어** · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

</div>

AutoClip은 AI로 영상 자막을 분석하고 하이라이트를 찾아 제목, 클립, 모음 영상을 자동으로 만듭니다. 인터뷰, 팟캐스트, 강의, 라이브 방송 녹화에 적합하며 데스크톱 앱, Docker 웹 UI, CLI / MCP로 사용할 수 있습니다.

## 화면 미리보기

![영상 가져오기 및 프로젝트 관리](docs/images/home-v1.4.0.png)

<table>
  <tr>
    <td width="50%" align="center"><strong>AI 클립 생성 결과</strong></td>
    <td width="50%" align="center"><strong>Studio 미리보기 및 편집</strong></td>
  </tr>
  <tr>
    <td><a href="docs/images/clips-v1.4.0.png"><img src="docs/images/clips-v1.4.0.png" alt="AI 클립 생성 결과" width="100%"></a></td>
    <td><a href="docs/images/studio-v1.4.0.png"><img src="docs/images/studio-v1.4.0.png" alt="Studio 미리보기 및 편집" width="100%"></a></td>
  </tr>
</table>

<sub>후속 Studio 수정 사항이 포함된 v1.4.0의 실제 화면입니다. 영상 가져오기, 실제 생성된 클립 확인, Studio 편집 과정을 보여 줍니다. UI는 중국어이며 예시 자막과 생성된 제목은 영어입니다.</sub>

[스크린샷 버전 및 예시 출처 (중국어)](docs/images/README.md)

## 후원에 감사드립니다 ❤️

<table>
  <tr>
    <td align="center" width="140">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="88"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar.cc</strong></a>
    </td>
    <td>
      AutoClip을 후원하는 <strong>Infistar.cc</strong>에 감사드립니다! 긴 영상의 자막 분석, 하이라이트 선택, 제목 생성에 활용할 수 있는 여러 모델의 API를 제공합니다.<br>
      ⚙️ <strong>호환 API 설정</strong>: AutoClip에서 OpenAI 호환 제공업체를 선택하고 Base URL, API 키, 사용 가능한 모델을 입력하세요.<br>
      🧩 <strong>다양한 모델</strong>: 후원사는 Claude, GPT, Gemini, DeepSeek 등을 제공합니다. 호환 엔드포인트를 지원하는 모델을 선택하여 자막 분석과 하이라이트 선택 결과를 비교할 수 있습니다.<br>
      🏷️ <strong>가격 및 서비스</strong>: 후원사 안내에 따르면 일부 모델은 <strong>공식 정가의 1%부터</strong> 이용할 수 있으며, 위안화 결제, 청구서 발행, 모델 진위 확인을 지원합니다. 적용 모델, 현재 가격과 조건은 플랫폼에서 확인하세요.<br>
      🎁 <strong>AutoClip 전용 혜택</strong>: 신규 사용자는 <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">전용 추천 링크</a>로 가입하면 <strong>$5 체험 크레딧</strong>을 받을 수 있습니다. 적용 조건은 이벤트 안내를 확인하세요. <a href="docs/INFISTAR_SETUP.en.md">설정 가이드 (영어)</a>
    </td>
  </tr>
</table>

## 주요 기능

썸네일을 클릭하면 큰 이미지를 볼 수 있습니다.

<table>
  <tr>
    <td width="50%" valign="top">
      <h4>영상 가져오기</h4>
      <p>로컬 영상, YouTube 및 Bilibili 링크를 지원하며 SRT 자막을 추가할 수 있습니다.</p>
      <a href="docs/images/feature-import.png"><img src="docs/images/feature-import.png" alt="영상 가져오기" width="420"></a>
    </td>
    <td width="50%" valign="top">
      <h4>하이라이트 찾기</h4>
      <p>자막에서 개요, 주제별 시간 구간, 하이라이트 점수, 클립 제목을 추출합니다.</p>
      <a href="docs/images/clips-v1.4.0.png"><img src="docs/images/clips-v1.4.0.png" alt="하이라이트 찾기" width="260"></a>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>클립과 모음 영상</h4>
      <p>클립과 추천 모음 영상을 생성하고 순서를 직접 조정할 수 있습니다.</p>
      <a href="docs/images/feature-collections.png"><img src="docs/images/feature-collections.png" alt="클립과 모음 영상" width="420"></a>
    </td>
    <td width="50%" valign="top">
      <h4>게시용 내보내기</h4>
      <p>Douyin, Xiaohongshu, YouTube Shorts, Bilibili 프리셋과 자막 삽입, 타이틀 카드를 지원합니다.</p>
      <a href="docs/images/feature-export.png"><img src="docs/images/feature-export.png" alt="게시용 내보내기" width="420"></a>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>표지 및 게시</h4>
      <p>v1.3.2부터 표지 자동 생성, 즉시 게시, 예약 게시를 지원합니다. 해외 플랫폼은 본인의 Upload-Post 계정으로 연결하고 Bilibili는 별도로 설정합니다.</p>
      <a href="docs/images/feature-publish.png"><img src="docs/images/feature-publish.png" alt="표지 및 게시" width="200"></a>
      <a href="docs/images/feature-cover.png"><img src="docs/images/feature-cover.png" alt="표지 및 게시" width="200"></a>
      <p><sub>이 데모에는 게시 계정이 연결되어 있지 않습니다. 게시 완료 결과가 아닌 게시 진입 화면과 표지 설정을 보여 줍니다.</sub></p>
    </td>
    <td width="50%" valign="top">
      <h4>게시 관리</h4>
      <p>게시 기록과 달력에서 예약을 관리할 수 있으며, 게시 없이 영상만 다운로드할 수도 있습니다.</p>
      <a href="docs/images/feature-calendar.png"><img src="docs/images/feature-calendar.png" alt="게시 관리" width="420"></a>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>모델 선택</h4>
      <p>Qwen, OpenAI 호환 API, Gemini 등 클라우드 서비스나 Ollama / LM Studio의 로컬 모델을 사용할 수 있습니다.</p>
      <a href="docs/images/feature-models.png"><img src="docs/images/feature-models.png" alt="모델 선택" width="420"></a>
    </td>
    <td width="50%" valign="top">
      <h4>자동화</h4>
      <p>CLI로 작업을 구성하거나 MCP 클라이언트에서 동일한 처리 파이프라인을 호출할 수 있습니다.</p>
      <a href="docs/images/feature-cli.png"><img src="docs/images/feature-cli.png" alt="자동화" width="420"></a>
      <p><sub>CLI / MCP에는 GUI가 없습니다. 실제 명령 도움말 출력을 표시한 페이지의 스크린샷입니다.</sub></p>
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center" valign="top">
      <h4>다국어 인터페이스</h4>
      <p>v1.3.1부터 앱, 웹사이트, README는 중국어, 영어, 일본어, 한국어, 스페인어, 포르투갈어, 러시아어, 프랑스어를 지원합니다. 상단에서 언어를 선택하거나 시스템 설정을 따를 수 있습니다. 원본 미디어와 생성 콘텐츠의 언어는 변경되지 않습니다.</p>
      <a href="docs/images/feature-languages.png"><img src="docs/images/feature-languages.png" alt="다국어 인터페이스" width="420"></a>
      <p><sub>영어 UI와 언어 선택 메뉴입니다. 미디어와 생성된 콘텐츠는 원래 언어를 유지합니다.</sub></p>
    </td>
  </tr>
</table>

<details>
<summary>지원 플랫폼, 계정 요건 및 내보내기 세부 정보</summary>

클립이 준비되면 그 클립에서 게시를 엽니다. **v1.3.2**부터 사용할 수 있습니다. 해외 플랫폼은 본인의 Upload-Post 계정에 연결한 곳입니다. TikTok, Instagram, YouTube, Facebook, LinkedIn, X, Threads, Pinterest, Bluesky, Discord, Telegram, Google Business 중 그 계정에서 쓸 수 있는 곳입니다. Bilibili는 계정 하나입니다. 설정에서 Cookie를 한 번 붙여 넣습니다. SESSDATA, bili_jct, DedeUserID가 있어야 합니다. 지금 올리거나 예약할 수 있습니다. 제목과 설명은 비워 두면 클립 제목을 씁니다. 자막 삽입은 기본으로 켜져 있고, 약 4초 타이틀 카드도 기본으로 켜져 있습니다. 공개 범위는 지원하는 플랫폼에서 기본이 나만 보기입니다. private / 나만 보기를 약속하는 곳은 TikTok, YouTube, Bilibili뿐입니다. 게시하지 않고 받을 수도 있습니다. 프로젝트 페이지에서 게시 기록과 달력을 보고, 아직 나가지 않은 예약을 취소할 수 있습니다.

「이번 주 배치」는 해외만 해당합니다. 아직 올리지 않은 클립을 월·수·금 09:00에 넣고, Bilibili는 넣지 않습니다. 세로 계정은 9:16으로 만들며 60초로 자르지 않습니다. Bilibili만이면 가로 화면입니다. LinkedIn 또는 X만이면 원본 화면입니다. 세로 계정과 Bilibili를 같은 번에 보내면 각각 따로 만듭니다.

게시할 때 커버를 자동으로 만들 수 있어, Bilibili 빈 커버 거절을 피합니다. 기본 커버와 타이틀 카드의 세부 내용은 그 버전 설치 파일 설명을 따릅니다. **v1.3.2**부터 사용할 수 있습니다.

</details>


> 영상 가져오기 → 자막 준비 / 음성 전사 → AI 분석 및 평가 → 클립과 모음 영상 생성 → 내보내기

<a id="quick-start"></a>

## 빠른 시작

| 사용 목적 | 권장 방식 | 준비 사항 |
| --- | --- | --- |
| 컴퓨터에서 영상 편집 | **데스크톱 앱** | macOS Apple Silicon / Windows x64 |
| 자체 호스팅 / Linux | **Docker** | Docker + Compose v2 |
| 일괄 처리 / Agent 연동 | **CLI / MCP** | Python 3.10+ (3.11 권장) + FFmpeg |

### 데스크톱: 첫 클립 만들기

1. **설치.** [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest)에서 macOS Apple Silicon은 `.dmg`, Windows 10 / 11 x64는 `-setup.exe`를 받으세요. Python과 FFmpeg가 포함되어 있습니다. Intel Mac / Linux는 Docker 또는 CLI를 사용하세요. 시스템 요건은 해당 릴리스를 확인하세요.
2. **모델 설정.** 설정에서 제공업체를 선택하고 API 키와 모델명을 입력한 뒤 연결을 테스트하고 저장하세요. 로컬 모델은 먼저 Ollama 또는 LM Studio를 실행하세요.
3. **영상 가져오기.** 3~5분 샘플로 시작하세요. SRT 자막을 함께 가져올 수 있습니다. 자막이 없다면 설정에서 로컬 Whisper 구성 요소와 음성 모델을 먼저 준비하세요.
4. **미리보기 및 내보내기.** 클립의 시작·종료 지점, 제목과 내용을 확인하고 내보내기 프리셋을 선택하세요. 계정을 연결해 게시할 수도 있습니다.

[전체 설치 가이드 (영어)](docs/USER_INSTALLATION_GUIDE.en.md) · [문제 해결 (영어)](docs/FAQ.en.md)

<details>
<summary><strong>Docker / Web</strong></summary>

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

</details>

<details>
<summary><strong>CLI / MCP</strong></summary>

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

</details>

## 모델 설정

| 방식 | 설정 |
| --- | --- |
| 클라우드 모델 | 설정에서 제공업체를 선택하고 API 키와 모델명을 입력하세요. OpenAI 호환 서비스는 Base URL도 지정할 수 있습니다. |
| Ollama | 기본 주소는 `http://localhost:11434/v1`, 모델은 `qwen2.5:7b`입니다. API 키가 필요하지 않습니다. |
| LM Studio | 모델을 로드하고 Local Server를 시작하세요. 기본 주소는 `http://localhost:1234/v1`이며 서버가 제공하는 모델을 선택해야 합니다. |

Docker 내부의 `localhost`는 컨테이너 자체를 가리킵니다. 호스트의 모델을 사용하려면 컨테이너에서 접근 가능한 주소를 설정하세요. 자세한 내용은 CLI / MCP 가이드에 있습니다. 영상 자르기는 로컬에서 수행하지만 클라우드 모델 분석은 선택한 제공업체에 자막 텍스트를 전송합니다. 영상과 모델 다운로드에는 인터넷이 필요합니다.

[Infistar · 설정 가이드 (영어)](docs/INFISTAR_SETUP.en.md)

## 자주 묻는 질문

<details>
<summary>무료인가요? API 키가 필요한가요?</summary>

AutoClip 자체는 계속 MIT 라이선스의 무료 오픈 소스입니다. 클라우드 모델은 제공업체의 요금이 적용되며 본인의 API 키가 필요합니다. Ollama / LM Studio는 클라우드 키가 필요 없지만 모델 파일과 적절한 하드웨어가 필요합니다. **v1.3.2**부터 해외 게시에는 본인의 [Upload-Post](https://www.upload-post.com) 계정이 필요합니다. 무료·유료 등급과 TikTok, YouTube, Instagram 등의 일일 한도는 Upload-Post 자신의 페이지를 따릅니다. AutoClip의 약속이 아닙니다.

</details>

<details>
<summary>영상이 업로드되나요?</summary>

편집은 사용자 기기에 남습니다. 클라우드 모델 분석에는 자막 텍스트를 전송합니다. 완성된 클립이 기기를 떠나는 때는 「게시」를 누른 뒤뿐이며, 연결해 둔 플랫폼으로만 갑니다. 게시하지 않고 받을 수도 있습니다. 이 게시 페이지는 **v1.3.2**부터 사용할 수 있습니다. 통계와 오류 보고는 버전 및 설정에 따라 달라지므로 개인정보 안내를 확인하세요.

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

샘플 준비와 공개 영상 예시는 [첫 사용 가이드 (영어)](docs/USER_INSTALLATION_GUIDE.en.md)를 참고하세요.

</details>

[전체 문제 해결 가이드(영어)](docs/FAQ.en.md) · [알려진 문제](https://github.com/zhouxiaoka/autoclip/issues/96)

<a id="documentation"></a>

## 문서

| 내용 | 문서 |
| --- | --- |
| 첫 사용 | [설치 (영어)](docs/USER_INSTALLATION_GUIDE.en.md) |
| 호스팅 및 자동화 | [Docker (영어)](docs/DOCKER.en.md) · [CLI / MCP (중국어)](docs/CLI_AND_MCP.md) · [Agent skill (중국어)](skills/autoclip/SKILL.md) |
| 모델 설정 및 문제 해결 | [모델 설정 (중국어)](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [문제 해결 (영어)](docs/FAQ.en.md) |
| 버전 및 개인정보 | [변경 기록](CHANGELOG.md) · [개인정보 안내 (영어)](docs/PRIVACY.en.md) |
| 개발 및 번역 | [기여 가이드 (중국어)](CONTRIBUTING.md) · [번역 관리 (중국어)](docs/i18n.md) |
| 후원 서비스 설정 | [Infistar](docs/INFISTAR_SETUP.en.md) |

README는 8개 언어로 제공됩니다. 설치, Docker, 문제 해결 가이드는 영어로도 제공되며, 나머지 상세 문서는 주로 중국어입니다.

## 기여 및 연락처

코드 수정, 피드백, 번역 개선을 환영합니다. 버그를 신고할 때 OS, 버전, 모델, 재현 단계, 민감한 정보를 제거한 오류 로그를 함께 보내 주세요.

개인이 여가 시간에 유지 관리합니다. 답변 시점은 일정하지 않으며 실시간 지원이나 일대일 설치 지원은 제공하지 않습니다. 연락 전에 FAQ와 알려진 문제를 확인해 주세요.

기능 아이디어, 사용 사례, 모델 요청은 [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions)에 올려 주세요. 재현 가능한 버그는 [Issue 템플릿](https://github.com/zhouxiaoka/autoclip/issues/new/choose)을 사용합니다. 규칙은 [커뮤니티 보드](docs/COMMUNITY_BOARD.md)(중국어)에 있습니다.

- [안내와 분류](https://github.com/zhouxiaoka/autoclip/discussions/127)
- [첫 클립 Q&A](https://github.com/zhouxiaoka/autoclip/discussions/128)
- [아이디어](https://github.com/zhouxiaoka/autoclip/discussions/129)

- 이메일: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper와 모든 기여자에게 감사드립니다. [MIT License](LICENSE)로 배포됩니다. AutoClip이 도움이 되었다면 Star로 응원해 주세요.

<details>
<summary>커뮤니티 성과 · Star History</summary>

아래 배지는 Trendshift에서 제공합니다. 클릭하면 AutoClip의 순위 기록을 확인할 수 있습니다. GitHub Trending과 Trendshift는 서로 다른 순위이며, 배지는 현재 실시간 순위가 아닌 기록된 성과를 보여 줍니다.

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)

</details>
