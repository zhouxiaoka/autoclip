<!-- mcp-name: io.github.zhouxiaoka/autoclip-mcp -->

<div align="center">

<img src="../../src-tauri/icons/128x128.png" alt="AutoClip" width="76" height="76">

# AutoClip

### Zamień dowolny film, link lub transmisję na żywo w klipy gotowe do publikacji.

**Otwartoźródłowa alternatywa dla OpusClip** — działające lokalnie wycinanie AI dla **podcastów, wywiadów i streamów gamingowych** z inteligentnym kadrowaniem, napisami, okładkami, tytułami i wbudowanym **MCP dla agentów AI**. Zero subskrypcji, brak paywalla.

<br>

<p>
  <a href="https://github.com/zhouxiaoka/autoclip/releases/latest"><img src="https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square&color=4F46E5" alt="GitHub release" height="20"></a>&nbsp;
  <a href="https://github.com/zhouxiaoka/autoclip/stargazers"><img src="https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square&color=FFD700&logo=github&logoColor=white&label=Stars" alt="GitHub stars" height="20"></a>&nbsp;
  <a href="https://github.com/zhouxiaoka/autoclip/releases"><img src="https://img.shields.io/github/downloads/zhouxiaoka/autoclip/total?style=flat-square&color=10B981" alt="Downloads" height="20"></a>&nbsp;
  <img src="https://img.shields.io/badge/Languages-20-0EA5E9?style=flat-square" alt="20 Languages" height="20">&nbsp;
  <a href="../../LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License: MIT" height="20"></a>
</p>

<br>

<!-- hero-cta:start -->
<p>
  <a href="https://zhouxiaoka.github.io/autoclip_intro/"><img src="../../docs/images/download-button.svg" alt="Download AutoClip" width="248" height="55"></a>&nbsp;&nbsp;
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>
</p>
<!-- hero-cta:end -->

<br>

<p>
  <a href="https://zhouxiaoka.github.io/autoclip_intro/"><strong>Strona główna</strong></a>
  &nbsp;&middot;&nbsp;
  <a href="https://github.com/zhouxiaoka/autoclip/releases/latest"><strong>Pobierz</strong></a>
  &nbsp;&middot;&nbsp;
  <a href="https://zhouxiaoka.github.io/autoclip_intro/features/game-streams/"><strong>Powtórki na żywo (v1.6)</strong></a>
  &nbsp;&middot;&nbsp;
  <a href="https://zhouxiaoka.github.io/autoclip_intro/cases/?lang=en"><strong>Przykłady</strong></a>
  &nbsp;&middot;&nbsp;
  <a href="#quick-start"><strong>Szybki start</strong></a>
  &nbsp;&middot;&nbsp;
  <a href="#documentation"><strong>Dokumentacja</strong></a>
  &nbsp;&middot;&nbsp;
  <a href="https://github.com/zhouxiaoka/autoclip/issues/new/choose"><strong>Zgłoś błąd</strong></a>
</p>

<p>
  <a href="../../README.md">English</a> · <a href="README-ZH.md">简体中文</a> · <a href="README-ZH-TW.md">繁體中文</a> · <a href="README-JA.md">日本語</a> · <a href="README-KO.md">한국어</a> · <a href="README-ES.md">Español</a> · <a href="README-PT.md">Português</a> · <a href="README-RU.md">Русский</a> · <a href="README-FR.md">Français</a> · <a href="README-ID.md">Bahasa Indonesia</a> · <a href="README-TR.md">Türkçe</a> · <a href="README-VI.md">Tiếng Việt</a> · <a href="README-DE.md">Deutsch</a> · <a href="README-IT.md">Italiano</a> · <strong>Polski</strong> · <a href="README-TH.md">ไทย</a> · <a href="README-NL.md">Nederlands</a> · <a href="README-UK.md">Українська</a> · <a href="README-HI.md">हिन्दी</a> · <a href="README-AR.md">العربية</a>
</p>

<br>

<p>
  ⭐ <em>Darmowy, na licencji MIT, zero subskrypcji — cały montaż i renderowanie odbywają się na Twoim komputerze. Zostaw gwiazdkę w repozytorium, jeśli uważasz projekt za przydatny!</em>
</p>

<!-- top-sponsors:start -->
<table width="100%">
  <tr>
    <td align="center" width="50%">
      <a href="https://go.apimart.ai/tw-autoclip"><img src="../../docs/sponsors/apimart.png" alt="APIMart" width="64"></a><br>
      <a href="https://go.apimart.ai/tw-autoclip"><strong>APIMart</strong></a><br>
      <sub>Low-cost AI image &amp; video API · GPT-Image-2 from $0.006/img</sub>
    </td>
    <td align="center" width="50%">
      <a href="mailto:christine_zhouye@163.com?subject=AutoClip%20Sponsor%20%2F%20Provider%20Partnership"><strong>Sponsor / Partner with AutoClip</strong></a><br>
      <sub>Put your AI API or creator tool in front of AutoClip users worldwide (cloud dynamic provider listing supported, zero client release needed).<br><a href="mailto:christine_zhouye@163.com">christine_zhouye@163.com</a></sub>
    </td>
  </tr>
</table>
<!-- top-sponsors:end -->

</div>

---

## Przegląd

Wrzuć link, lokalny plik wideo lub **powtórkę transmisji na żywo** — AutoClip znajduje najlepsze momenty, śledzi osobę mówiącą, wtapia napisy, generuje okładki i eksportuje klipy gotowe do publikacji na TikTok, Shorts, Reels, YouTube, Douyin, Xiaohongshu oraz Bilibili.

**Zaprojektowany jako local-first:** wycinanie i renderowanie działają bezpośrednio na Twoim komputerze, bez kolejek przesyłania i miesięcznych opłat. Użyj własnego klucza API albo działaj w 100% offline dzięki **Ollama / LM Studio + Whisper / SenseVoice**.

![AutoClip v1.6 Live Stream Replays Walkthrough](../images/v1.6/autoclip-v1.6-demo.gif)

<p align="center"><em>Strona główna → 6 źródeł powtórek na żywo → konfiguracja OBS WebSocket → import z Twitcha → gotowy klip z napisami i publikacją jednym kliknięciem.</em></p>

---

## Co nowego w v1.6

| Funkcja | Szczegóły |
| :--- | :--- |
| **6 źródeł powtórek na żywo** | Dedykowana karta **Powtórka na żywo** obsługująca **OBS Studio, Twitch, YouTube, Kick, Discord oraz nagrania lokalne**. |
| **Automatyczne przechwytywanie OBS** | Połącz się z OBS WebSocket (`4455`), przycinaj bezstratnie (`-c copy`) i automatycznie dodawaj klipy do kolejki zaraz po zakończeniu transmisji. |
| **Najlepsze momenty z gier** | Uogólnione wykrywanie najlepszych momentów obsługujące samodzielne akcje **8 s+** przy oszczędniejszym budżecie wizji/OCR. |
| **Szybka adaptacja jednym kliknięciem** | Ujednolicone karty odtwarzalnych klipów — zmień platformę docelową jednym kliknięciem bez utraty wcześniejszych eksportów. |
| **13 języków** | Pełny interfejs desktopowy, menu zasobnika i dokumentacja w 13 językach (`+ zh-TW, de, id, tr, vi`) oraz obsługa arabskich napisów RTL. |

<details>
<summary>📸 Wewnątrz aplikacji (5 zrzutów ekranu)</summary>

<table width="100%">
<tr>
<td align="center" valign="top" width="50%">
<img src="../images/v1.6/en-01-home.jpg" alt="Ekran główny z kartami Link, Plik i Powtórka na żywo"><br>
<em>Ekran główny — Link, Plik i Powtórka na żywo</em>
</td>
<td align="center" valign="top" width="50%">
<img src="../images/v1.6/en-02-replays-obs.jpg" alt="Wybór spośród 6 źródeł powtórek na żywo"><br>
<em>Powtórka na żywo — 6 źródeł powtórek</em>
</td>
</tr>
<tr>
<td align="center" valign="top" width="50%">
<img src="../images/v1.6/en-03-replays-obs-settings.jpg" alt="Wbudowane ustawienia połączenia OBS Studio WebSocket"><br>
<em>Wbudowane ustawienia OBS Studio WebSocket</em>
</td>
<td align="center" valign="top" width="50%">
<img src="../images/v1.6/en-04-replays-twitch.jpg" alt="Import powtórki z Twitcha"><br>
<em>Import z Twitcha i wybór lokalnych nagrań</em>
</td>
</tr>
<tr>
<td align="center" valign="top" colspan="2">
<img src="../images/v1.6/en-05-result-card.jpg" width="75%" alt="Gotowy klip z oznaczeniem źródła Twitch"><br>
<em>Gotowy klip — oznaczenie źródła, kadrowanie 9:16, napisy oraz Pobierz / Opublikuj / Powtórz jednym kliknięciem</em>
</td>
</tr>
</table>

</details>

---

## Przykłady

Kliknij dowolną miniaturę lub **▶ Odtwórz**, aby obejrzeć pełne klipy wyrenderowane przez AutoClip. Oznaczenia językowe wskazują język wtopionych napisów.

### Pionowe · Wywiad i podcast

<table width="100%">
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/gates-ezra/01.mp4?v=2026-10-01g"><img src="../images/demos/gates-ezra-01.jpg" width="180" alt="Bill Gates"></a><br>
<strong>Bill Gates</strong><br>
Wywiad · Douyin · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/gates-ezra/01.mp4?v=2026-10-01g">▶ Odtwórz 1:01</a> · <a href="https://www.youtube.com/watch?v=A_156w0aYtU">Źródło</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/ai-labs-debate/01.mp4?v=2026-10-01g"><img src="../images/demos/ai-labs-debate-01.jpg" width="180" alt="AI Experts Debate"></a><br>
<strong>AI Experts Debate</strong><br>
Wywiad · Shorts · EN<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/ai-labs-debate/01.mp4?v=2026-10-01g">▶ Odtwórz 1:25</a> · <a href="https://www.youtube.com/watch?v=OhOmLqR5nN4">Źródło</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/robbins-36months/01.mp4?v=2026-10-01g"><img src="../images/demos/robbins-36months-01.jpg" width="180" alt="Tony Robbins"></a><br>
<strong>Tony Robbins</strong><br>
Podcast · Douyin · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/robbins-36months/01.mp4?v=2026-10-01g">▶ Odtwórz 1:45</a> · <a href="https://www.youtube.com/watch?v=DuRcrbP3kag">Źródło</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/garfield-poehler/01.mp4?v=2026-10-01g"><img src="../images/demos/garfield-poehler-01.jpg" width="180" alt="Andrew Garfield × Amy Poehler"></a><br>
<strong>Garfield × Poehler</strong><br>
Podcast · Shorts · EN<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/garfield-poehler/01.mp4?v=2026-10-01g">▶ Odtwórz 1:01</a> · <a href="https://www.youtube.com/watch?v=OJV8AaWCxQQ">Źródło</a>
</td>
</tr>
</table>

### Poziome · Oryginalne proporcje obrazu

<table width="100%">
<tr>
<td align="center" valign="top" width="50%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-tongliya/01.mp4?v=2026-10-01g"><img src="../images/demos/luyu-tongliya-01.jpg" width="360" alt="Tong Liya × Lu Yu"></a><br>
<strong>佟丽娅 × 鲁豫</strong> · 16:9 · Bilibili · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-tongliya/01.mp4?v=2026-10-01g">▶ Odtwórz 1:41</a> · <a href="https://www.bilibili.com/video/BV1qheu6kEFV/">Źródło</a>
</td>
<td align="center" valign="top" width="50%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/altman-uses-ai/01.mp4?v=2026-10-01g"><img src="../images/demos/altman-uses-ai-01.jpg" width="360" alt="Sam Altman"></a><br>
<strong>Sam Altman</strong> · 16:9 · Bilibili · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/altman-uses-ai/01.mp4?v=2026-10-01g">▶ Odtwórz 2:02</a> · <a href="https://www.youtube.com/watch?v=jZh55CQwSh8">Źródło</a>
</td>
</tr>
</table>

<details>
<summary>Zobacz 10 kolejnych klipów</summary>

<table width="100%">
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/neumann-doac/01.mp4?v=2026-10-01g"><img src="../images/demos/neumann-doac-01.jpg" width="180" alt="Adam Neumann"></a><br>
<strong>Adam Neumann</strong><br>
Podcast · TikTok · EN<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/neumann-doac/01.mp4?v=2026-10-01g">▶ Odtwórz 0:59</a> · <a href="https://www.youtube.com/watch?v=IQ4JVWdj4Q0">Źródło</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-xiaoqi/02.mp4?v=2026-10-01g"><img src="../images/demos/luyu-xiaoqi-02.jpg" width="180" alt="Xiao Qi × Lu Yu"></a><br>
<strong>小奇 × 鲁豫</strong><br>
Wywiad · Douyin · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-xiaoqi/02.mp4?v=2026-10-01g">▶ Odtwórz 0:50</a> · <a href="https://www.bilibili.com/video/BV1ighy6AEPz/">Źródło</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-guokeyu/01.mp4?v=2026-10-01g"><img src="../images/demos/luyu-guokeyu-01.jpg" width="180" alt="Guo Keyu × Lu Yu"></a><br>
<strong>郭柯宇 × 鲁豫</strong><br>
Wywiad · Douyin · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-guokeyu/01.mp4?v=2026-10-01g">▶ Odtwórz 1:11</a> · <a href="https://www.bilibili.com/video/BV1LDYV6HEXR/">Źródło</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/dafoe-hot-ones/01.mp4?v=2026-10-01g"><img src="../images/demos/dafoe-hot-ones-01.jpg" width="180" alt="Willem Dafoe"></a><br>
<strong>Willem Dafoe</strong><br>
Podcast · TikTok · EN<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/dafoe-hot-ones/01.mp4?v=2026-10-01g">▶ Odtwórz 1:07</a> · <a href="https://www.youtube.com/watch?v=YqugY2zTIoI">Źródło</a>
</td>
</tr>
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/tim-luoyonghao/01.mp4?v=2026-10-01g"><img src="../images/demos/tim-luoyonghao-01.jpg" width="180" alt="TIM × Luo Yonghao"></a><br>
<strong>TIM × 罗永浩</strong><br>
Wywiad · Douyin · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/tim-luoyonghao/01.mp4?v=2026-10-01g">▶ Odtwórz 1:05</a> · <a href="https://www.bilibili.com/video/BV1B5xkzPEhx/">Źródło</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/jensen-dwarkesh/01.mp4?v=2026-10-01g"><img src="../images/demos/jensen-dwarkesh-01.jpg" width="180" alt="Jensen Huang"></a><br>
<strong>Jensen Huang</strong><br>
Wywiad · Xiaohongshu · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/jensen-dwarkesh/01.mp4?v=2026-10-01g">▶ Odtwórz 1:17</a> · <a href="https://www.youtube.com/watch?v=Hrbq66XqtCo">Źródło</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/karpathy-dwarkesh/01.mp4?v=2026-10-01g"><img src="../images/demos/karpathy-dwarkesh-01.jpg" width="180" alt="Andrej Karpathy"></a><br>
<strong>Andrej Karpathy</strong><br>
Wywiad · Douyin · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/karpathy-dwarkesh/01.mp4?v=2026-10-01g">▶ Odtwórz 0:43</a> · <a href="https://www.youtube.com/watch?v=lXUZvyajciY">Źródło</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/apple-a20/01.mp4?v=2026-10-01g"><img src="../images/demos/apple-a20-01.jpg" width="180" alt="A20 Pro"></a><br>
<strong>A20 Pro</strong><br>
Wywiad · Xiaohongshu · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/apple-a20/01.mp4?v=2026-10-01g">▶ Odtwórz 2:00</a> · <a href="https://www.bilibili.com/video/BV1e4Y96FEaJ/">Źródło</a>
</td>
</tr>
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/stallone-nyt/01.mp4?v=2026-10-01g"><img src="../images/demos/stallone-nyt-01.jpg" width="180" alt="Sylvester Stallone"></a><br>
<strong>Sylvester Stallone</strong><br>
Wywiad · Douyin · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/stallone-nyt/01.mp4?v=2026-10-01g">▶ Odtwórz 1:39</a> · <a href="https://www.youtube.com/watch?v=ccs-B_nTfZs">Źródło</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/mrbeast-colin-samir/01.mp4?v=2026-10-01g"><img src="../images/demos/mrbeast-colin-samir-01.jpg" width="180" alt="MrBeast"></a><br>
<strong>MrBeast</strong><br>
Podcast · TikTok · EN<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/mrbeast-colin-samir/01.mp4?v=2026-10-01g">▶ Odtwórz 1:42</a> · <a href="https://www.youtube.com/watch?v=9IQ_ldV9z_A">Źródło</a>
</td>
<td></td>
<td></td>
</tr>
</table>

</details>

Przeglądaj ponad 16 klipów, okładek i gotowych opisów postów w **[Galerii przykładów →](https://zhouxiaoka.github.io/autoclip_intro/cases/?lang=en)** lub [udostępnij własne klipy](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell). Prawa autorskie do materiałów źródłowych należą do ich oryginalnych twórców.

---

<a id="quick-start"></a>

## Szybki start

| Zastosowanie | Zalecana konfiguracja | Wymagania |
| :--- | :--- | :--- |
| **Aplikacja desktopowa (najprostsza)** | Pobierz `.dmg` / `-setup.exe` z [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) | macOS Apple Silicon lub Windows 10/11 x64 (Python i FFmpeg w pakiecie) |
| **Agenci AI / CLI / MCP** | `uvx autoclip-mcp` lub `npx skills add zhouxiaoka/autoclip` | Python 3.10+ (zalecany 3.11) i FFmpeg |
| **Self-hosting / Linux / Intel Mac** | `docker compose up -d --build` | Docker i Compose v2 |

### 1. Aplikacja desktopowa

1. Pobierz najnowszy instalator z **[GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases/latest)** (`aarch64.dmg` dla macOS Apple Silicon, `x64-setup.exe` dla Windows). Przenośny Python i FFmpeg są dołączone do pakietu.
2. Otwórz **Ustawienia**, wybierz dostawcę w chmurze (lub uruchom Ollama / LM Studio), przetestuj połączenie i zapisz — albo kliknij **Otwórz przykładowy projekt** bez klucza API.
3. Wklej link do wideo, upuść plik albo przejdź do **Powtórka na żywo**, aby połączyć OBS lub zaimportować nagranie transmisji. Wybierz platformy i kliknij **Generuj**.

> Instalatory są budowane publicznie w GitHub Actions (`Desktop Build`) z weryfikacją sum SHA-256 `build-provenance.json`. Pierwsze uruchomienie niepodpisanej kompilacji: w **macOS** uruchom `xattr -dr com.apple.quarantine "/Applications/AutoClip Desktop.app"` (lub *Ustawienia systemowe → Prywatność i ochrona → Otwórz mimo to*); w **Windows** kliknij **Więcej informacji → Uruchom mimo to** w oknie SmartScreen. Zobacz **[Politykę podpisywania kodu i weryfikacji](../../CODE_SIGNING.md)** (notaryzacja śledzona w [#119](https://github.com/zhouxiaoka/autoclip/issues/119)).

### 2. CLI i MCP (Claude Code, Cursor, Codex, OpenCode oraz skrypty)

Pozwól agentom kodującym AI wycinać filmy bezpośrednio z terminala (`claude mcp add autoclip -- uvx autoclip-mcp`). Pełne przewodniki konfiguracji MCP: **[English](../MCP.en.md)** · [简体中文](../CLI_AND_MCP.md) · [日本語](../MCP.ja.md) · [한국어](../MCP.ko.md) · [Español](../MCP.es.md) · [Deutsch](../MCP.de.md).

```bash
uvx autoclip-mcp
npx skills add zhouxiaoka/autoclip

autoclip --version
autoclip produce talk.mp4 --srt talk.srt --platform tiktok --portrait-style podcast --json
autoclip outputs PROJECT_ID --export-kits
```

<details>
<summary>Pakiet offline wheel, instalacja ze źródeł i pakowanie MCPB</summary>

```bash
# Install from a downloaded CLI/MCP release ZIP wheel
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --force-reinstall --no-deps autoclip_mcp-*-py3-none-any.whl

# Or install from source
python -m pip install --no-deps .
```

Aby zbudować lokalny pakiet MCPB bez publikowania, uruchom `python scripts/pack_mcpb.py` (nigdy nie uruchamiaj `smithery mcp publish` automatycznie).

</details>


### 3. Docker / Web

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env
mkdir -p data logs uploads
docker compose up -d --build
```

Otwórz interfejs webowy pod adresem `http://localhost:3000` (dokumentacja API pod `http://localhost:8000/docs`). Zobacz [Przewodnik Docker](../DOCKER.en.md), aby poznać szczegóły uprawnień bind-mount oraz własnych domen.

---

## Wydajność i koszty

Pomiary wykonane na komputerze Mac z Apple Silicon (koszt LLM oszacowany dla `qwen-plus`; nie obejmuje ASR w chmurze ani generowania obrazów AI; dokładne zużycie sprawdź na rachunku swojego dostawcy):

| Wejście | Źródło | Czas i wynik | Szac. koszt LLM |
| :--- | :--- | ---: | ---: |
| **Z gotowymi napisami** | Jensen Huang · 1 godz. 43 min (EN → Xiaohongshu) | **7,5 min / 10 klipów** | **¥0,09** |
| **Bez napisów (lokalny Whisper)** | TIM × Luo Yonghao · 2 godz. 52 min (ZH → Douyin) | 29,5 min / 10 klipów | ¥0,20 |

---

## Sponsor ❤️

<table>
  <tr>
    <td align="center" width="140">
      <a href="https://go.apimart.ai/tw-autoclip"><img src="../sponsors/apimart.png" alt="APIMart" width="88"></a><br>
      <a href="https://go.apimart.ai/tw-autoclip"><strong>APIMart</strong></a>
    </td>
    <td>
      Podziękowania dla <strong>APIMart</strong> za sponsorowanie AutoClip! <strong>APIMart</strong> to niskokosztowa platforma API do generowania obrazów i wideo AI — GPT-Image-2 już od <strong>$0.006/obraz</strong> (<strong>160+</strong> obrazów za dolara). Jedno asynchroniczne API obsługuje zarówno obrazy, jak i wideo: wyślij zadanie, odbierz ID i pobierz wyniki przez polling lub callback. Przetwarzaj dziesiątki tysięcy obrazów wsadowo bez przekroczeń czasu i przełączaj modele bez zmian w kodzie. Płatność za zużycie bez miesięcznego abonamentu — <a href="https://go.apimart.ai/tw-autoclip">zarejestruj się tutaj</a>.
    </td>
  </tr>
</table>

## Transkrypcja w chmurze (Alibaba Cloud)

*Link partnerski (niezależny od powyższego sponsora):* załóż konto w Alibaba Cloud, utwórz klucz API w konsoli Bailian i włącz ASR w chmurze Bailian w **Ustawienia → Domyślne modele → Mowa na napisy**.

1. [Rejestracja w Alibaba Cloud](https://www.aliyun.com/benefit?userCode=qmyj6jch) (link partnerski)
2. [Konsola Bailian](https://bailian.console.aliyun.com/) — utwórz swój klucz API

---

## FAQ

<details>
<summary>Czy AutoClip jest darmowy? Czy potrzebuję klucza API?</summary>

Tak — AutoClip jest darmowy i udostępniany na licencji MIT. Analiza w chmurze, transkrypcja i okładki AI korzystają z Twoich własnych kluczy API według stawek dostawcy (lokalny układ okładki jest domyślnie darmowy). Ollama i LM Studio nie wymagają klucza w chmurze. Bezpośrednia publikacja korzysta z Twojego własnego konta Bilibili lub [Upload-Post](https://www.upload-post.com).

</details>

<details>
<summary>Czy moje wideo jest wysyłane do chmury?</summary>

Cięcie i renderowanie działają lokalnie. Analiza w chmurze wysyła wyłącznie tekst napisów; modele wizyjne otrzymują tylko próbkowane klatki; ASR w chmurze przesyła dźwięk. Korzystanie z lokalnych modeli LLM + Whisper / SenseVoice utrzymuje wszystko offline. Statystyki i raporty awarii można wyłączyć w Ustawieniach. Zobacz [Prywatność](../PRIVACY.en.md).

</details>

<details>
<summary>Jakie rodzaje filmów sprawdzają się najlepiej?</summary>

Podcasty, wywiady, wystąpienia, kursy oraz powtórki transmisji z gier (OBS / Twitch / YouTube / Kick / Discord). Źródła z gotowymi napisami działają najszybciej; w innym przypadku użyj lokalnego Whisper / SenseVoice lub ASR w chmurze. W przypadku rozgrywki lub streamów z małą ilością dialogów włącz model obsługujący analizę obrazu.

</details>

<details>
<summary>Dlaczego nie wygenerowano żadnych klipów?</summary>

Sprawdź etap, na którym wystąpił błąd: napisy/transkrypcja, połączenie z modelem, FFmpeg, miejsce na dysku lub limity długości platformy (długie formy na YouTube wymagają ≥180 s; dla krótszych klipów użyj Shorts, TikTok lub Bilibili). Jeśli problem nadal występuje, otwórz zgłoszenie z wynikiem `autoclip --version`, systemem operacyjnym, modelem oraz zanonimizowanymi logami albo sprawdź [Znane problemy (#96)](https://github.com/zhouxiaoka/autoclip/issues/96).

</details>

[Rozwiązywanie problemów](../FAQ.en.md) · [Znane problemy](https://github.com/zhouxiaoka/autoclip/issues/96)

---

<a id="documentation"></a>

## Dokumentacja

| Temat | Przewodnik |
| :--- | :--- |
| Instalacja i pierwsze klipy | [Przewodnik instalacji](../USER_INSTALLATION_GUIDE.en.md) |
| Self-hosting i agenci | [Docker](../DOCKER.en.md) · [MCP i agenci AI](../MCP.en.md) ([ZH](../CLI_AND_MCP.md) · [JA](../MCP.ja.md) · [KO](../MCP.ko.md) · [ES](../MCP.es.md) · [DE](../MCP.de.md)) · [Agent Skill](../../skills/autoclip/SKILL.md) (ZH) · [OpenCode](../OPENCODE.en.md) |
| Modele i rozwiązywanie problemów | [Konfiguracja Multi-LLM](../MULTI_LLM_PROVIDER_GUIDE.md) (ZH) · [FAQ](../FAQ.en.md) |
| Wydania i prywatność | [Changelog](../../CHANGELOG.md) · [Podpisywanie kodu](../../CODE_SIGNING.md) · [Mapa rozwoju](../ROADMAP.md) (ZH) · [Tablica społeczności](../COMMUNITY_BOARD.md) (ZH) · [Prywatność](../PRIVACY.en.md) |
| Badania | [Pick the Moment, Not the Effect](../research/2026-10-what-drives-views/article-en.md) · [中文](../research/2026-10-what-drives-views/article-zh.md) |
| Współtworzenie i tłumaczenia | [Współtworzenie](../../CONTRIBUTING.md) (ZH) · [Tłumaczenie AutoClip](../../TRANSLATING.md) · [Przewodnik tłumaczeń](../i18n.md) (ZH) |

## Współtworzenie

Pull requesty, zgłoszenia błędów, przykładowe klipy i tłumaczenia są mile widziane. Jeśli AutoClip oszczędza Twój czas, ⭐ gwiazdka bardzo pomaga!

- **Społeczność:** [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [Q&amp;A pierwszego klipu](https://github.com/zhouxiaoka/autoclip/discussions/128) · [Pomysły na funkcje](https://github.com/zhouxiaoka/autoclip/discussions/129)
- **Zgłaszanie błędów:** skorzystaj z [szablonu zgłoszenia](https://github.com/zhouxiaoka/autoclip/issues/new/choose), podając system operacyjny, wersję, model, kroki odtworzenia błędu i zanonimizowane logi
- **Partnerstwa:** [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

AutoClip jest rozwijany przez jedną osobę — prosimy o wyrozumiałość w sprawie asynchronicznych odpowiedzi (brak wsparcia na żywo oraz indywidualnej pomocy przy wdrożeniach).

![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)

Zbudowano w oparciu o FastAPI, React, Tauri, FFmpeg, yt-dlp, Whisper oraz FunASR. [Licencja MIT](../../LICENSE).
