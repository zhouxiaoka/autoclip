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

**[웹사이트](https://zhouxiaoka.github.io/autoclip_intro/)** · **[데스크톱 받기](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [사례](https://zhouxiaoka.github.io/autoclip_intro/cases/) · [빠른 시작](#빠른-시작) · [문서](#문서) · [이슈](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · **한국어** · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

</div>

**[1.5.0 정식 출시](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0)**. 데스크톱·CLI·MCP를 함께 업데이트했습니다. 자동 제작, 자막 페이지 분할, 인물 구도, 긴 영상 대기열 수정은 [변경 기록](CHANGELOG.md)을 확인하고 이전 버전에서 업그레이드하세요.

## 실제 완성 클립

이미지나 “재생”을 클릭하면 완성된 영상을 볼 수 있습니다. 언어 표시는 영상의 자막 언어입니다. 추천 영상 6개를 먼저 보여주며, 펼치면 10개를 더 볼 수 있습니다.

### 세로 · 인터뷰형 및 전체 화면 팟캐스트형

<table width="100%">
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/gates-ezra/01.mp4?v=2026-10-01g"><img src="docs/images/demos/gates-ezra-01.jpg" width="180" alt="Bill Gates — AI测试时竟会装傻？"></a><br>
<strong>Bill Gates</strong><br>
인터뷰형 · Douyin · 중국어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/gates-ezra/01.mp4?v=2026-10-01g">▶ 재생 1:01</a> · <a href="https://www.youtube.com/watch?v=A_156w0aYtU">원본</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/ai-labs-debate/01.mp4?v=2026-10-01g"><img src="docs/images/demos/ai-labs-debate-01.jpg" width="180" alt="AI Experts Debate — We&#x27;re Driving Toward a Cliff in the Fog"></a><br>
<strong>AI Experts Debate</strong><br>
인터뷰형 · Shorts · 영어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/ai-labs-debate/01.mp4?v=2026-10-01g">▶ 재생 1:25</a> · <a href="https://www.youtube.com/watch?v=OhOmLqR5nN4">원본</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/robbins-36months/01.mp4?v=2026-10-01g"><img src="docs/images/demos/robbins-36months-01.jpg" width="180" alt="Tony Robbins — 风险极小，回报极大？"></a><br>
<strong>Tony Robbins</strong><br>
전체 화면 팟캐스트형 · Douyin · 중국어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/robbins-36months/01.mp4?v=2026-10-01g">▶ 재생 1:45</a> · <a href="https://www.youtube.com/watch?v=DuRcrbP3kag">원본</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/garfield-poehler/01.mp4?v=2026-10-01g"><img src="docs/images/demos/garfield-poehler-01.jpg" width="180" alt="Andrew Garfield × Amy Poehler — I Love Competition—but Hate Fake Casualness"></a><br>
<strong>Andrew Garfield × Amy Poehler</strong><br>
전체 화면 팟캐스트형 · Shorts · 영어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/garfield-poehler/01.mp4?v=2026-10-01g">▶ 재생 1:01</a> · <a href="https://www.youtube.com/watch?v=OJV8AaWCxQQ">원본</a>
</td>
</tr>
</table>

### 가로 · 원본 화면 비율 유지

<table width="100%">
<tr>
<td align="center" valign="top" width="50%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-tongliya/01.mp4?v=2026-10-01g"><img src="docs/images/demos/luyu-tongliya-01.jpg" width="360" alt="佟丽娅 × 鲁豫 — 舞蹈是我骨子里的东西"></a><br>
<strong>佟丽娅 × 鲁豫</strong><br>
원본 화면 비율 · Bilibili · 중국어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-tongliya/01.mp4?v=2026-10-01g">▶ 재생 1:41</a> · <a href="https://www.bilibili.com/video/BV1qheu6kEFV/">원본</a>
</td>
<td align="center" valign="top" width="50%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/altman-uses-ai/01.mp4?v=2026-10-01g"><img src="docs/images/demos/altman-uses-ai-01.jpg" width="360" alt="Sam Altman — AI是文艺复兴，还是工业革命？"></a><br>
<strong>Sam Altman</strong><br>
원본 화면 비율 · Bilibili · 중국어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/altman-uses-ai/01.mp4?v=2026-10-01g">▶ 재생 2:02</a> · <a href="https://www.youtube.com/watch?v=jZh55CQwSh8">원본</a>
</td>
</tr>
</table>

<details>
<summary>실제 완성 영상 10개 더 보기</summary>

<table width="100%">
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/neumann-doac/01.mp4?v=2026-10-01g"><img src="docs/images/demos/neumann-doac-01.jpg" width="180" alt="Adam Neumann — Success is how you feel one minute before death—full of love, no regret"></a><br>
<strong>Adam Neumann</strong><br>
전체 화면 팟캐스트형 · TikTok · 영어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/neumann-doac/01.mp4?v=2026-10-01g">▶ 재생 0:59</a> · <a href="https://www.youtube.com/watch?v=IQ4JVWdj4Q0">원본</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-xiaoqi/02.mp4?v=2026-10-01g"><img src="docs/images/demos/luyu-xiaoqi-02.jpg" width="180" alt="小奇 × 鲁豫 — 想证明自己，又怕被注视"></a><br>
<strong>小奇 × 鲁豫</strong><br>
인터뷰형 · Douyin · 중국어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-xiaoqi/02.mp4?v=2026-10-01g">▶ 재생 0:50</a> · <a href="https://www.bilibili.com/video/BV1ighy6AEPz/">원본</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-guokeyu/01.mp4?v=2026-10-01g"><img src="docs/images/demos/luyu-guokeyu-01.jpg" width="180" alt="郭柯宇 × 鲁豫 — 演员的快感在创作过程 不在结果"></a><br>
<strong>郭柯宇 × 鲁豫</strong><br>
인터뷰형 · Douyin · 중국어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-guokeyu/01.mp4?v=2026-10-01g">▶ 재생 1:11</a> · <a href="https://www.bilibili.com/video/BV1LDYV6HEXR/">원본</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/dafoe-hot-ones/01.mp4?v=2026-10-01g"><img src="docs/images/demos/dafoe-hot-ones-01.jpg" width="180" alt="Willem Dafoe — Fake teeth made him feel lascivious and instantly became the character"></a><br>
<strong>Willem Dafoe</strong><br>
전체 화면 팟캐스트형 · TikTok · 영어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/dafoe-hot-ones/01.mp4?v=2026-10-01g">▶ 재생 1:07</a> · <a href="https://www.youtube.com/watch?v=YqugY2zTIoI">원본</a>
</td>
</tr>
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/tim-luoyonghao/01.mp4?v=2026-10-01g"><img src="docs/images/demos/tim-luoyonghao-01.jpg" width="180" alt="TIM × 罗永浩 — 红得快的网红 糊得更快"></a><br>
<strong>TIM × 罗永浩</strong><br>
인터뷰형 · Douyin · 중국어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/tim-luoyonghao/01.mp4?v=2026-10-01g">▶ 재생 1:05</a> · <a href="https://www.bilibili.com/video/BV1B5xkzPEhx/">원본</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/jensen-dwarkesh/01.mp4?v=2026-10-01g"><img src="docs/images/demos/jensen-dwarkesh-01.jpg" width="180" alt="Jensen Huang — AI是五层蛋糕 能源才是底层"></a><br>
<strong>Jensen Huang</strong><br>
인터뷰형 · 샤오훙슈 · 중국어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/jensen-dwarkesh/01.mp4?v=2026-10-01g">▶ 재생 1:17</a> · <a href="https://www.youtube.com/watch?v=Hrbq66XqtCo">원본</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/karpathy-dwarkesh/01.mp4?v=2026-10-01g"><img src="docs/images/demos/karpathy-dwarkesh-01.jpg" width="180" alt="Andrej Karpathy — AI还不能当实习生用 因认知能力严重不足"></a><br>
<strong>Andrej Karpathy</strong><br>
인터뷰형 · Douyin · 중국어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/karpathy-dwarkesh/01.mp4?v=2026-10-01g">▶ 재생 0:43</a> · <a href="https://www.youtube.com/watch?v=lXUZvyajciY">원본</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/apple-a20/01.mp4?v=2026-10-01g"><img src="docs/images/demos/apple-a20-01.jpg" width="180" alt="A20 Pro — 苹果芯片不是拼乐高"></a><br>
<strong>A20 Pro</strong><br>
인터뷰형 · 샤오훙슈 · 중국어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/apple-a20/01.mp4?v=2026-10-01g">▶ 재생 2:00</a> · <a href="https://www.bilibili.com/video/BV1e4Y96FEaJ/">원본</a>
</td>
</tr>
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/stallone-nyt/01.mp4?v=2026-10-01g"><img src="docs/images/demos/stallone-nyt-01.jpg" width="180" alt="Sylvester Stallone — 60岁写《洛奇》 是向衰老宣战"></a><br>
<strong>Sylvester Stallone</strong><br>
인터뷰형 · Douyin · 중국어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/stallone-nyt/01.mp4?v=2026-10-01g">▶ 재생 1:39</a> · <a href="https://www.youtube.com/watch?v=ccs-B_nTfZs">원본</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/mrbeast-colin-samir/01.mp4?v=2026-10-01g"><img src="docs/images/demos/mrbeast-colin-samir-01.jpg" width="180" alt="MrBeast — YouTube&#x27;s first 5 seconds matter more than thumbnails"></a><br>
<strong>MrBeast</strong><br>
전체 화면 팟캐스트형 · TikTok · 영어<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/mrbeast-colin-samir/01.mp4?v=2026-10-01g">▶ 재생 1:42</a> · <a href="https://www.youtube.com/watch?v=9IQ_ldV9z_A">원본</a>
</td>
<td></td>
<td></td>
</tr>
</table>

</details>

영상, 커버와 게시 문구는 **[사례 라이브러리 →](https://zhouxiaoka.github.io/autoclip_intro/cases/?lang=ko)** 에서 확인하고, [직접 만든 영상도 공유해 주세요](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell). 원본 영상의 저작권은 원작자에게 있으며, 이 영상은 효과를 보여주기 위한 예시입니다.

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
2. **모델 설정.** 제공자와 API Key를 입력하고 이용 가능한 분석 모델을 선택한 뒤 연결을 테스트하고 저장하세요. 로컬은 먼저 Ollama / LM Studio에서 모델을 로드하고 서비스를 시작하세요.
3. **링크와 플랫폼 선택.** 자막이 있는 인터뷰나 팟캐스트로 시작하고 세로 레이아웃을 고르세요. 자막이 없으면 설정에서 Whisper / SenseVoice를 준비하거나 클라우드 전사를 설정하세요.
4. **확인 후 저장.** 자막·구도·내용의 완결성을 확인하고 게시 패키지를 저장하거나 계정을 연결해 게시하세요. 더 필요하면 대체 후보를 제작하세요.

Intel Mac / Linux는 Docker 또는 CLI를 이용할 수 있습니다. 요구 사항, 첫 실행 안내, 검증 범위는 [설치 가이드](docs/USER_INSTALLATION_GUIDE.en.md)와 [1.5.0 Release](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0)를 참고하세요.

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

위 명령은 macOS / Linux용입니다. Windows는 `py -m venv venv`로 만들고 `.\venv\Scripts\Activate.ps1`로 활성화한 뒤 같은 `python -m pip` 설치 명령을 실행하세요.

먼저 모델 설정을 저장하세요. 데스크톱 설정을 공유하거나 ZIP의 키 없는 예제로 전용 데이터 디렉터리를 설정합니다. [CLI / MCP](docs/CLI_AND_MCP.md)(중국어). `produce`는 이전 `run --provider` 임시 설정을 쓰지 않습니다. `--srt`로 전사를 생략할 수 있습니다.

```bash
autoclip --version
autoclip produce talk.mp4 --srt talk.srt --platform douyin --portrait-style podcast --json
autoclip outputs PROJECT_ID --export-kits
```

MCP 클라이언트가 서버를 시작합니다. 별도 디버깅은 다른 터미널에서 `autoclip mcp`; OpenCode 설정은 `autoclip mcp install opencode`로 작성할 수 있습니다.

`PROJECT_ID`는 제작 결과의 ID로 바꾸세요. MCP는 `start_quick_output` / `get_quick_output_status`. 클라이언트 `command`는 가상환경 `autoclip` 절대 경로, `args`는 `["mcp"]`. 이전 `run` / `export`와 클립 도구도 유지됩니다. [CLI / MCP](docs/CLI_AND_MCP.md)(중국어)·[OpenCode](docs/OPENCODE.en.md)·[Agent skill](skills/autoclip/SKILL.md)(중국어).

## 모델 설정

| 방식 | 설정 |
| --- | --- |
| 클라우드 API | 설정에서 제공자와 API Key. OpenAI 호환은 Base URL도 가능. |
| Ollama | 기본 주소 `http://localhost:11434/v1`. 로컬 모델을 내려받아 실행하고 서비스가 제공하는 모델을 선택하세요. API Key는 필요 없습니다. |
| LM Studio | 모델을 열고 Local Server. 기본 `http://localhost:1234/v1`. |

Docker 안 `localhost`는 컨테이너입니다. 호스트 모델은 컨테이너가 닿는 주소를 쓰세요.

[모델 설정](docs/MULTI_LLM_PROVIDER_GUIDE.md)(중국어) · [로컬과 컨테이너](docs/CLI_AND_MCP.md)(중국어)

## 후원에 감사드립니다 ❤️

<table>
  <tr>
    <td align="center" width="140">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="88"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td>
      <strong>88API Token 플랫폼</strong>의 AutoClip 후원에 감사드립니다! GPT, Claude, Gemini, Grok, DeepSeek, Kimi, GLM을 통합하여 자막 분석, 하이라이트 선택, 제목 생성에 활용할 수 있습니다.<br>
      🎨 <strong>멀티미디어</strong>: GPT-Image, Seedance, Veo, MiniMax Hailuo H3, Kling, Whisper, TTS 등 이미지·영상·음성 모델을 제공합니다. AutoClip에서는 호환되는 분석·표지 생성·자막 전사 API를 사용합니다.<br>
      🏷️ <strong>서비스 및 결제</strong>: 파트너 안내에 따르면 해외 법인이 운영하며 상담원 지원, 정식 청구서, 1:1 충전 비율을 제공합니다. 세부 조건은 플랫폼을 확인하세요.<br>
      🎁 <strong>신규 가입 혜택</strong>: <a href="https://88api.ai/sign-up?aff=2PIc">전용 추천 링크</a>로 가입하면 모델 테스트용 체험 크레딧을 받을 수 있습니다. 이벤트 조건이 적용됩니다. <a href="docs/88API_SETUP.en.md">설정 가이드 (영어)</a>
    </td>
  </tr>
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
