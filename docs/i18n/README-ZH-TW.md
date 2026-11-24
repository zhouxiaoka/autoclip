<div align="center">

<img src="../../src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### 一個連結，一鍵出片

開源，在你的電腦上剪輯與算繪。貼上一個連結，選好平台，生成 <b>影片、封面與發佈文案</b>，<br>
支援抖音、小紅書、TikTok、Reels、YouTube Shorts、B 站與 YouTube。<br>
軟體免費，雲端模型依用量計費；需要調整時可進入編輯器。

<p>
  <a href="https://github.com/zhouxiaoka/autoclip/releases/latest"><img src="https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square" alt="GitHub release"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/stargazers"><img src="https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square" alt="GitHub stars"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/releases"><img src="https://img.shields.io/github/downloads/zhouxiaoka/autoclip/total?style=flat-square" alt="Downloads"></a>
  <a href="../../LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License: MIT"></a>
</p>

<a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>

**[官網](https://zhouxiaoka.github.io/autoclip_intro/)** · **[下載桌面版](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [案例庫](https://zhouxiaoka.github.io/autoclip_intro/cases/) · [研究](../research/2026-10-what-drives-views/article-zh.md) · [快速開始](#快速開始) · [文件](#文件) · [問題回報](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

[English](../../README.md) · [简体中文](README-ZH.md) · **繁體中文** · [日本語](README-JA.md) · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md) · [Bahasa Indonesia](README-ID.md) · [Türkçe](README-TR.md) · [Tiếng Việt](README-VI.md) · [Deutsch](README-DE.md)

</div>

![AutoClip v1.6 Live Stream Replays](../images/v1.6/autoclip-v1.6-demo.gif)

**[最新正式版](https://github.com/zhouxiaoka/autoclip/releases/latest)**，桌面版、CLI 與 MCP 同步更新。版本以 `autoclip --version` 與 MCP `get_version` 為準。一鍵出片、字幕分頁、人物取景與長影片佇列修復詳見 [更新日誌](../../CHANGELOG.md)。舊版使用者請升級。

## 實際成片

點擊截圖或「播放」即可直接觀看完整成片；下方語言為成片字幕語言。此處精選 6 支，展開可看另外 10 支。

### 直式 · 訪談式與滿版 Podcast 式

<table width="100%">
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/gates-ezra/01.mp4?v=2026-10-01g"><img src="../images/demos/gates-ezra-01.jpg" width="180" alt="Bill Gates — AI测试时竟会装傻？"></a><br>
<strong>Bill Gates</strong><br>
訪談式 · 抖音 · 中文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/gates-ezra/01.mp4?v=2026-10-01g">▶ 播放 1:01</a> · <a href="https://www.youtube.com/watch?v=A_156w0aYtU">原片</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/ai-labs-debate/01.mp4?v=2026-10-01g"><img src="../images/demos/ai-labs-debate-01.jpg" width="180" alt="AI Experts Debate — We&#x27;re Driving Toward a Cliff in the Fog"></a><br>
<strong>AI Experts Debate</strong><br>
訪談式 · Shorts · 英文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/ai-labs-debate/01.mp4?v=2026-10-01g">▶ 播放 1:25</a> · <a href="https://www.youtube.com/watch?v=OhOmLqR5nN4">原片</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/robbins-36months/01.mp4?v=2026-10-01g"><img src="../images/demos/robbins-36months-01.jpg" width="180" alt="Tony Robbins — 风险极小，回报极大？"></a><br>
<strong>Tony Robbins</strong><br>
滿版 Podcast · 抖音 · 中文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/robbins-36months/01.mp4?v=2026-10-01g">▶ 播放 1:45</a> · <a href="https://www.youtube.com/watch?v=DuRcrbP3kag">原片</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/garfield-poehler/01.mp4?v=2026-10-01g"><img src="../images/demos/garfield-poehler-01.jpg" width="180" alt="Andrew Garfield × Amy Poehler — I Love Competition—but Hate Fake Casualness"></a><br>
<strong>Andrew Garfield × Amy Poehler</strong><br>
滿版 Podcast · Shorts · 英文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/garfield-poehler/01.mp4?v=2026-10-01g">▶ 播放 1:01</a> · <a href="https://www.youtube.com/watch?v=OJV8AaWCxQQ">原片</a>
</td>
</tr>
</table>

### 橫式 · 保留原畫幅

<table width="100%">
<tr>
<td align="center" valign="top" width="50%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-tongliya/01.mp4?v=2026-10-01g"><img src="../images/demos/luyu-tongliya-01.jpg" width="360" alt="佟丽娅 × 鲁豫 — 舞蹈是我骨子里的东西"></a><br>
<strong>佟麗婭 × 魯豫</strong><br>
原畫幅 · B 站 · 中文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-tongliya/01.mp4?v=2026-10-01g">▶ 播放 1:41</a> · <a href="https://www.bilibili.com/video/BV1qheu6kEFV/">原片</a>
</td>
<td align="center" valign="top" width="50%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/altman-uses-ai/01.mp4?v=2026-10-01g"><img src="../images/demos/altman-uses-ai-01.jpg" width="360" alt="Sam Altman — AI是文艺复兴，还是工业革命？"></a><br>
<strong>Sam Altman</strong><br>
原畫幅 · B 站 · 中文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/altman-uses-ai/01.mp4?v=2026-10-01g">▶ 播放 2:02</a> · <a href="https://www.youtube.com/watch?v=jZh55CQwSh8">原片</a>
</td>
</tr>
</table>

<details>
<summary>查看更多 10 支實際成片</summary>

<table width="100%">
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/neumann-doac/01.mp4?v=2026-10-01g"><img src="../images/demos/neumann-doac-01.jpg" width="180" alt="Adam Neumann — Success is how you feel one minute before death—full of love, no regret"></a><br>
<strong>Adam Neumann</strong><br>
滿版 Podcast · TikTok · 英文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/neumann-doac/01.mp4?v=2026-10-01g">▶ 播放 0:59</a> · <a href="https://www.youtube.com/watch?v=IQ4JVWdj4Q0">原片</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-xiaoqi/02.mp4?v=2026-10-01g"><img src="../images/demos/luyu-xiaoqi-02.jpg" width="180" alt="小奇 × 鲁豫 — 想证明自己，又怕被注视"></a><br>
<strong>小奇 × 魯豫</strong><br>
訪談式 · 抖音 · 中文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-xiaoqi/02.mp4?v=2026-10-01g">▶ 播放 0:50</a> · <a href="https://www.bilibili.com/video/BV1ighy6AEPz/">原片</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-guokeyu/01.mp4?v=2026-10-01g"><img src="../images/demos/luyu-guokeyu-01.jpg" width="180" alt="郭柯宇 × 鲁豫 — 演员的快感在创作过程 不在结果"></a><br>
<strong>郭柯宇 × 魯豫</strong><br>
訪談式 · 抖音 · 中文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-guokeyu/01.mp4?v=2026-10-01g">▶ 播放 1:11</a> · <a href="https://www.bilibili.com/video/BV1LDYV6HEXR/">原片</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/dafoe-hot-ones/01.mp4?v=2026-10-01g"><img src="../images/demos/dafoe-hot-ones-01.jpg" width="180" alt="Willem Dafoe — Fake teeth made him feel lascivious and instantly became the character"></a><br>
<strong>Willem Dafoe</strong><br>
滿版 Podcast · TikTok · 英文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/dafoe-hot-ones/01.mp4?v=2026-10-01g">▶ 播放 1:07</a> · <a href="https://www.youtube.com/watch?v=YqugY2zTIoI">原片</a>
</td>
</tr>
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/tim-luoyonghao/01.mp4?v=2026-10-01g"><img src="../images/demos/tim-luoyonghao-01.jpg" width="180" alt="TIM × 罗永浩 — 红得快的网红 糊得更快"></a><br>
<strong>TIM × 羅永浩</strong><br>
訪談式 · 抖音 · 中文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/tim-luoyonghao/01.mp4?v=2026-10-01g">▶ 播放 1:05</a> · <a href="https://www.bilibili.com/video/BV1B5xkzPEhx/">原片</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/jensen-dwarkesh/01.mp4?v=2026-10-01g"><img src="../images/demos/jensen-dwarkesh-01.jpg" width="180" alt="Jensen Huang — AI是五层蛋糕 能源才是底层"></a><br>
<strong>Jensen Huang</strong><br>
訪談式 · 小紅書 · 中文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/jensen-dwarkesh/01.mp4?v=2026-10-01g">▶ 播放 1:17</a> · <a href="https://www.youtube.com/watch?v=Hrbq66XqtCo">原片</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/karpathy-dwarkesh/01.mp4?v=2026-10-01g"><img src="../images/demos/karpathy-dwarkesh-01.jpg" width="180" alt="Andrej Karpathy — AI还不能当实习生用 因认知能力严重不足"></a><br>
<strong>Andrej Karpathy</strong><br>
訪談式 · 抖音 · 中文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/karpathy-dwarkesh/01.mp4?v=2026-10-01g">▶ 播放 0:43</a> · <a href="https://www.youtube.com/watch?v=lXUZvyajciY">原片</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/apple-a20/01.mp4?v=2026-10-01g"><img src="../images/demos/apple-a20-01.jpg" width="180" alt="A20 Pro — 苹果芯片不是拼乐高"></a><br>
<strong>A20 Pro</strong><br>
訪談式 · 小紅書 · 中文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/apple-a20/01.mp4?v=2026-10-01g">▶ 播放 2:00</a> · <a href="https://www.bilibili.com/video/BV1e4Y96FEaJ/">原片</a>
</td>
</tr>
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/stallone-nyt/01.mp4?v=2026-10-01g"><img src="../images/demos/stallone-nyt-01.jpg" width="180" alt="Sylvester Stallone — 60岁写《洛奇》 是向衰老宣战"></a><br>
<strong>Sylvester Stallone</strong><br>
訪談式 · 抖音 · 中文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/stallone-nyt/01.mp4?v=2026-10-01g">▶ 播放 1:39</a> · <a href="https://www.youtube.com/watch?v=ccs-B_nTfZs">原片</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/mrbeast-colin-samir/01.mp4?v=2026-10-01g"><img src="../images/demos/mrbeast-colin-samir-01.jpg" width="180" alt="MrBeast — YouTube&#x27;s first 5 seconds matter more than thumbnails"></a><br>
<strong>MrBeast</strong><br>
滿版 Podcast · TikTok · 英文<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/mrbeast-colin-samir/01.mp4?v=2026-10-01g">▶ 播放 1:42</a> · <a href="https://www.youtube.com/watch?v=9IQ_ldV9z_A">原片</a>
</td>
<td></td>
<td></td>
</tr>
</table>

</details>

影片、封面與發佈文案請見 **[官網案例庫 →](https://zhouxiaoka.github.io/autoclip_intro/cases/)**，歡迎[投稿你的成片](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell)。原片版權歸原作者所有，僅作效果展示。

## 能做什麼

### 貼上連結就出片

選好平台，依平台的畫幅與時長要求自動生成。每個平台依評分自動生成至多 10 支合格片段，其餘列為備選，點擊「生成這支」再製作。每支都附帶封面、標題、簡介、話題標籤與 ZIP 發佈包。

### 成片自動包裝

抖音 / 小紅書預設訪談式，TikTok / Reels / Shorts 預設滿版 Podcast 式；直式也可自行選擇兩種版式。字幕與文案語言仍依平台而定，B 站 / YouTube 為橫式。畫面會跟隨說話者，無人鏡頭保留完整畫面。自動品牌片尾預設開啟，可在設定中關閉；複製發佈文案不會附上 AutoClip 署名。

### 全程在你的電腦上完成

剪輯、取景與算繪皆在本機完成。分析模型可自選，字幕可使用作者字幕、本機 Whisper / SenseVoice 或已設定的雲端轉錄。CLI / MCP 與桌面版共用同一套一鍵出片流程。

## 真實素材的耗時與費用

以下是開發期間三支不同素材的實測數據，並非同一輸入的速度對照。費用依當時 qwen-plus 的文字模型用量估算，不含雲端語音辨識、AI 生圖或投稿服務費用；實際帳單以所選服務商為準。

| 版本 | 原片 | 出片 | 文字模型費用估算（人民幣） |
| --- | --- | ---: | ---: |
| **新版 · 有字幕** | Jensen · 1h43m（英 → 小紅書） | **7.5 分鐘 / 10 支** | **¥0.09** |
| 新版 · 無字幕 | TIM × 羅永浩 · 2h52m（中 → 抖音） | 29.5 分鐘 / 10 支 | ¥0.20 |
| 舊版 | MrBeast · 2h06m（英 → TikTok） | 65 分鐘 | ¥0.64 |

<details>
<summary>測試條件與記錄</summary>

2026-10-01，同一台 Apple Silicon Mac。前兩支為新流程、自動生成 10 支；舊流程生成 33 支，素材與輸出數量不同。Jensen 使用作者字幕，TIM 使用本機 Whisper base。

已有作者字幕時會跳過轉錄；沒有字幕時可選本機或雲端轉錄。追加平台與製作備選會增加處理時間與用量。完整階段記錄與估算口徑見 [成本與時間](../COST_PER_VIDEO.md)。

</details>

## 模型與資料由你掌控

剪輯與算繪皆在你的電腦上完成。使用雲端分析會傳送相關字幕與文案；畫面理解或參考影格生圖會傳送所需抽樣畫面，雲端轉錄則會傳送音訊。使用本機分析與本機轉錄時不需要對應的雲端 API。成片只有在選擇投稿後才會上傳到已連結的平台；匿名統計與錯誤回報可在設定中關閉。詳見 [隱私權說明](../PRIVACY.md)。

## 快速開始

| 你的使用情境            | 建議方式          | 準備事項                              |
| ----------------- | ------------- | --------------------------------- |
| 在電腦上出片            | **桌面版**       | macOS Apple Silicon 或 Windows x64 |
| 自建 Web 服務 / Linux | **Docker**    | Docker 與 Compose v2               |
| 批次處理 / 接入 Agent   | **CLI / MCP** | Python 3.10+（建議 3.11）與 FFmpeg     |

### 桌面版

1. **下載安裝**：至 [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) 下載。macOS Apple Silicon 請選 `.dmg`，Windows 10 / 11 x64 請選 `-setup.exe`。安裝包內建 Python 與 FFmpeg。macOS 15 及以上首次開啟：雙擊一次，若遭系統阻擋請前往「系統設定 → 隱私權與安全性 → 仍要打開」（[Apple 說明](https://developer.apple.com/news/?id=saqachfa)）。較舊的 macOS 可對應用程式按右鍵 →「打開」。Windows 若出現 SmartScreen，請點擊「更多資訊 → 仍要執行」。
2. **設定模型**：在設定中選擇服務商、填寫 API Key，選擇可用的分析模型，測試連線並儲存；本機模型請先在 Ollama / LM Studio 啟動服務並載入模型。
3. **先看範例，再貼自己的影片**：首頁尚未建立專案時，點擊「用範例專案看看效果」，不需要 API Key，範例已內建於安裝包中。之後使用自己的訪談或 Podcast 影片時，可選擇直式版面。若沒有字幕、本機 Whisper 裝不上或速度太慢，請打開「設定 → 預設模型 → 語音轉字幕」，改用百煉雲端轉錄（`qwen-audio-3.1-asr-flash`，約 0.1 元人民幣/小時音訊，實際以阿里雲帳單為準）。音訊會上傳至雲端。匯入被阻擋時，點擊「改用雲端轉錄」。若安裝本機轉錄，首次需下載約 220 MB，中國大陸網路環境約 15 分鐘。
4. **檢查並下載**：預覽自動成片，檢查字幕、取景與內容完整性，再下載發佈包或連結帳號投稿；需要更多片段時可生成備選。

Intel Mac 目前沒有桌面安裝包，與 Linux 一樣請使用 Docker 或 CLI。桌面安裝包目前未購買程式碼簽章 / Apple 公證（計畫見 [#119](https://github.com/zhouxiaoka/autoclip/issues/119)），新版本可能觸發 SmartScreen 或防毒軟體誤報；所有安裝包均由公開 GitHub Actions `Desktop Build` 建置，可在 Release 附件 `build-provenance.json` 核對 SHA-256，或改用 Docker / 原始碼執行。安裝需求請見 [安裝指南](../USER_INSTALLATION_GUIDE.md) 與 [最新 Release](https://github.com/zhouxiaoka/autoclip/releases/latest)。

[完整安裝與首次使用指南](../USER_INSTALLATION_GUIDE.md) · [遇到問題？](../FAQ.md)

**CLI / MCP（Claude Code、Codex、OpenCode 與腳本）**

```bash
uvx autoclip-mcp
npx skills add zhouxiaoka/autoclip

autoclip --version
autoclip produce talk.mp4 --srt talk.srt --platform tiktok --portrait-style podcast --json
autoclip outputs PROJECT_ID --export-kits
```

<details>
<summary>离线 Wheel、源码安装与 MCPB 打包</summary>

```bash
# Install from a downloaded CLI/MCP release ZIP wheel
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --force-reinstall --no-deps autoclip_mcp-*-py3-none-any.whl

# Or install from source
python -m pip install --no-deps .
```

如需本地构建 MCPB 包而不发布，运行 `python scripts/pack_mcpb.py`（不自动执行 `smithery mcp publish`）。

</details>


**Docker / Web 部署**

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env
mkdir -p data logs uploads
docker compose up -d --build
```

開啟 Web UI：`http://localhost:3000`（後端 API 文件：`http://localhost:8000/docs`）。掛載權限與自訂網域設定見 [Docker 指南](../DOCKER.md)。
## 模型設定

| 方式        | 設定                                                             |
| --------- | -------------------------------------------------------------- |
| 雲端 API    | 在設定中選擇服務商，填寫自己的 API Key。OpenAI 相容服務還可設定 Base URL。              |
| Ollama | 預設位址 `http://localhost:11434/v1`；先拉取並啟動本機模型，再選擇服務實際提供的模型，無需 API Key。 |
| LM Studio | 載入模型並啟動 Local Server，預設位址 `http://localhost:1234/v1`。          |

Docker 存取宿主機模型服務時，`localhost` 指向容器本身，需改為容器可存取的宿主機位址。

[模型設定指南](../MULTI_LLM_PROVIDER_GUIDE.md) · [本機模型與容器設定](../CLI_AND_MCP.md)

## 特別感謝 ❤️

<table>
  <tr>
    <td align="center" width="140">
      <a href="https://go.apimart.ai/tw-autoclip"><img src="../sponsors/apimart.png" alt="APIMart" width="88"></a><br>
      <a href="https://go.apimart.ai/tw-autoclip"><strong>APIMart</strong></a>
    </td>
    <td>
      感謝 <strong>APIMart</strong> 贊助了本專案！<strong>APIMart</strong> 是專注於 AI 圖片／影片生成的低價 API 平台，GPT-Image-2 低至 <strong>$0.006/張</strong>，1 美元可產出 <strong>160+</strong> 張圖片。圖片、影片一套非同步 API 通吃，送出任務取得 ID、透過回呼取得結果，大量批次處理上萬張不逾時、更換模型免改程式碼。依用量計費、無月費，透過此<a href="https://go.apimart.ai/tw-autoclip">註冊連結</a>註冊即可開始使用。
    </td>
  </tr>
  </table>

## 推薦連結

這是作者推薦連結，並非上方的贊助商。

使用此連結註冊阿里雲或領取優惠，再到百煉控制台建立 API Key，即可在「設定 → 預設模型 → 語音轉字幕」使用百煉雲端轉錄。音訊會上傳至雲端。

1. [作者推薦連結](https://www.aliyun.com/benefit?userCode=qmyj6jch)：註冊或領取優惠。
2. [百煉控制台](https://bailian.console.aliyun.com/)：建立 API Key。

## 常見問題

<details>
<summary>需要付費或 API Key 嗎？</summary>

軟體免費，採 MIT 開源授權。雲端分析、轉錄與 AI 生圖依所選服務商計費，需使用自己的憑證；自動設計封面預設不呼叫付費生圖。Ollama / LM Studio 本機分析不需要雲端金鑰，但需具備相應硬體。直接投稿還需自己的 B 站或 [Upload-Post](https://www.upload-post.com) 帳號。

</details>

<details>
<summary>我的影片會上傳嗎？</summary>

剪輯與算繪皆在你的電腦上完成。使用雲端分析會傳送相關字幕與文案；畫面理解或參考影格生圖會傳送所需抽樣畫面，雲端轉錄則會傳送音訊。使用本機分析與本機轉錄時不需要對應的雲端 API。成片只有在選擇投稿後才會上傳到已連結的平台；匿名統計與錯誤回報可在設定中關閉。詳見 [隱私權說明](../PRIVACY.md)。

</details>

<details>
<summary>什麼影片效果最好？</summary>

訪談、Podcast、課程與口播是主要驗證場景，有作者字幕時處理最快。缺少字幕可使用本機或雲端轉錄；遊戲錄影、口播較少的素材可啟用畫面辨識並選擇支援圖片的模型，但仍需檢查實際選段。

</details>

<details>
<summary>為什麼沒有生成片段？</summary>

請先檢查具體失敗階段：字幕／轉錄是否成功、模型連線、FFmpeg 與磁碟空間是否正常，以及候選片段是否符合目標平台規則。YouTube 長影片要求完整片段至少 180 秒，短素材可選擇 Shorts 或 B 站。若仍失敗，請附上 `autoclip --version` 的版本號、作業系統、素材時長、模型與去識別化日誌，詳見 [已知問題](https://github.com/zhouxiaoka/autoclip/issues/96)。

</details>

[完整疑難排解指南](../FAQ.md) · [已知問題](https://github.com/zhouxiaoka/autoclip/issues/96)

## 文件

| 你想了解      | 文件                                                                                                                                    |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| 安裝與首次出片   | [安裝指南](../USER_INSTALLATION_GUIDE.md)                                                                                               |
| 自建服務與自動化  | [Docker 部署](../DOCKER.md) · [CLI / MCP](../CLI_AND_MCP.md) · [Agent skill](../../skills/autoclip/SKILL.md) · [OpenCode 接入](../OPENCODE.md) |
| 設定模型與疑難排解 | [模型設定](../MULTI_LLM_PROVIDER_GUIDE.md) · [常見問題](../FAQ.md)                                                                        |
| 版本、路線圖與隱私 | [更新日誌](../../CHANGELOG.md) · [路線圖](../ROADMAP.md) · [社群看板](../COMMUNITY_BOARD.md) · [隱私權說明](../PRIVACY.md)                                  |
| 研究筆記       | [選對瞬間，而不是堆特效](../research/2026-10-what-drives-views/article-zh.md) · [English](../research/2026-10-what-drives-views/article-en.md) |
| 參與開發與翻譯   | [貢獻指南](../../CONTRIBUTING.md) · [翻譯維護](../i18n.md)                                                                                        |

## 參與貢獻

歡迎提交修復、出片範例、使用回饋與翻譯改進。如果 AutoClip 對你有幫助，歡迎給專案一顆 Star。

- **提問與交流**：[GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [第一次出片問答](https://github.com/zhouxiaoka/autoclip/discussions/128) · [分享想法](https://github.com/zhouxiaoka/autoclip/discussions/129)
- **回報問題**：使用 [Issue 範本](https://github.com/zhouxiaoka/autoclip/issues/new/choose)，附上系統、版本、所選模型、重現步驟與已去識別化的日誌
- **合作聯繫**：[christine_zhouye@163.com](mailto:christine_zhouye@163.com)

個人維護，回覆時間不固定，不提供即時客服或一對一部署服務。

![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)

感謝 FastAPI、React、Tauri、FFmpeg、yt-dlp、Whisper、FunASR，以及所有貢獻者。本專案採用 [MIT License](../../LICENSE)。
