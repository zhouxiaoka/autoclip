<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="80" height="80">

# AutoClip

**AI로 영상의 하이라이트를 찾아 클릭 한 번으로 HD 숏폼 영상을 만드세요.**

[简体中文](README.md) · [English](README-EN.md) · [日本語](README-JA.md) · **한국어** · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/forks)
[![GitHub issues](https://img.shields.io/github/issues/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/issues)
[![License: MIT](https://img.shields.io/github/license/zhouxiaoka/autoclip?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — Trendshift" width="250" height="55"></a>
</p>

무료 오픈 소스 · 로컬 편집 · 클라우드 및 로컬 모델 지원

[웹사이트](https://zhouxiaoka.github.io/autoclip_intro/) · [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [문제 신고](https://github.com/zhouxiaoka/autoclip/issues)

**데스크톱 설치 파일: [macOS · Apple Silicon](https://github.com/zhouxiaoka/autoclip/releases/latest) · [Windows · x64](https://github.com/zhouxiaoka/autoclip/releases/latest)**

[설치와 첫 클립 만들기 (English)](docs/USER_INSTALLATION_GUIDE.en.md) · [전체 문제 해결 가이드(영어)](docs/FAQ.en.md)

</div>

인터뷰, 팟캐스트, 강의, 라이브 다시보기에서 짧은 영상을 만드세요. AutoClip이 하이라이트를 찾고 제목, 클립, 모음 영상을 생성합니다. 결과를 직접 수정하고 내보낼 수도 있습니다.

## 화면 미리보기

![AutoClip 영상 가져오기 화면](docs/images/import-local.jpg)

로컬 영상과 SRT 자막을 가져올 수 있습니다. 이미지는 중국어 UI입니다.

## 주요 기능

| 기능 | 설명 |
| --- | --- |
| 영상 가져오기 | 로컬 파일, YouTube 및 Bilibili 링크 지원. |
| 하이라이트 찾기 | 자막을 분석해 주요 장면, 제목, 주제별 타임라인 생성. |
| 클립 편집 | 클립과 모음 영상을 만들고 시작·종료 시점, 텍스트, 화면 비율 조정. |
| 게임 하이라이트 | 게임 녹화의 이벤트 탐지. 비전 모델을 설정하고 게임 분석을 켜야 하며, 클라우드 비용은 제공업체가 청구합니다. [설정 안내(중국어)](docs/MULTI_LLM_PROVIDER_GUIDE.md). |
| 내보내기와 게시 | 가로·세로 영상, 자막, 타이틀 카드, 표지 생성, 즉시·예약 게시 지원. [게시 안내(중국어)](docs/PUBLISH_UPLOAD_POST.md). |
| 모델과 자동화 | Qwen, OpenAI, Gemini, DeepSeek 등의 클라우드 모델과 Ollama / LM Studio 로컬 모델 지원. CLI 및 MCP 제공. |

> 가져오기 → 제작 유형 확인 → AI 분석 및 편집 → 수정 후 내보내기

## 빠른 시작

1. **설치하기.** [GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases/latest)에서 macOS Apple Silicon용 `.dmg` 또는 Windows x64용 `-setup.exe`를 받으세요. Python과 FFmpeg가 포함되어 있습니다.
2. **모델 설정하기.** 설정에서 클라우드 API Key를 입력하거나 로컬 모델에 연결하고 연결 테스트 후 저장하세요.
3. **클립 만들기.** 영상을 가져오고 제작 유형을 확인하면 분석과 편집을 시작합니다. 결과를 수정하고 내보내세요.

Windows 실기기에서 설치, 가져오기, 저장 검증은 아직 완료되지 않았습니다. Intel Mac / Linux는 Docker 또는 CLI를 이용하세요.

[설치 안내(영어)](docs/USER_INSTALLATION_GUIDE.en.md) · [문제 해결(영어)](docs/FAQ.en.md)

<details>
<summary>Docker / Web, CLI, MCP</summary>

- **Docker / Web:** [Docker 안내(영어)](docs/DOCKER.en.md)에 따라 브라우저 UI를 직접 호스팅하세요.
- **CLI:** 일괄 처리와 스크립트 연동은 [CLI 안내(중국어)](docs/CLI_AND_MCP.md)를 참고하세요.
- **MCP:** 같은 안내에서 클라이언트를 연결하거나 [Agent skill(중국어)](skills/autoclip/SKILL.md)을 사용하세요.

</details>

## 자주 묻는 질문

<details>
<summary>비용이 드나요?</summary>

AutoClip은 MIT 라이선스의 무료 오픈 소스입니다. 클라우드 모델에는 개인 API Key가 필요하며 제공업체가 사용료를 청구합니다. Ollama / LM Studio는 클라우드 Key가 필요 없습니다. 해외 플랫폼 게시에는 개인 [Upload-Post](https://www.upload-post.com) 계정이 필요하며 요금과 한도는 해당 사이트에서 확인하세요.

</details>

<details>
<summary>영상이 업로드되나요?</summary>

편집과 렌더링은 로컬에서 실행됩니다. 클라우드 자막 분석은 관련 텍스트를, 비전 분석은 샘플 프레임과 필요한 텍스트를 전송합니다. 게시하면 완성 영상을 연결한 플랫폼에 업로드합니다. 로컬로만 내보낼 수도 있습니다. [개인정보 안내(영어)](docs/PRIVACY.en.md).

</details>

<details>
<summary>자막이 없어도 되나요?</summary>

로컬 Whisper와 음성 모델을 설정하면 음성을 텍스트로 변환할 수 있습니다. 기존 SRT도 가져올 수 있습니다. 처음에는 자막이 있는 짧은 영상으로 시작해 보세요. [시작 안내(영어)](docs/USER_INSTALLATION_GUIDE.en.md).

</details>

<details>
<summary>어떤 영상에 적합한가요? HD로 내보낼 수 있나요?</summary>

자막 분석은 인터뷰, 팟캐스트, 강의, 말하기 중심 영상에 적합합니다. 게임 녹화는 비전 분석을 사용할 수 있습니다. 가로·세로 1080p 내보내기를 지원하며 화질은 원본과 출력 설정에 따라 달라집니다. 처리 시간은 영상 길이, 모델, 하드웨어에 따라 달라집니다.

</details>

## 프로젝트 후원

AutoClip의 지속적인 개발과 유지보수를 위한 기업 및 개인 후원을 환영합니다. 기업 후원사는 README에 브랜드와 서비스 소개를 게재할 수 있습니다.

후원 문의 : [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

## 문서와 커뮤니티

- [설치(영어)](docs/USER_INSTALLATION_GUIDE.en.md) · [모델 설정(중국어)](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [문제 해결(영어)](docs/FAQ.en.md)
- [변경 기록(중국어)](CHANGELOG.md) · [문서(중국어)](docs/README.md)
- 질문과 아이디어는 [Discussions](https://github.com/zhouxiaoka/autoclip/discussions), 버그는 [Issues](https://github.com/zhouxiaoka/autoclip/issues/new/choose)에 남겨 주세요.
- 코드, 문서, 번역 기여를 환영합니다. [기여 안내(중국어)](CONTRIBUTING.md).
- 연락 및 후원 문의: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

모든 기여자와 FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper 등 오픈 소스 프로젝트에 감사드립니다. 도움이 되었다면 Star로 응원해 주세요.

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)
