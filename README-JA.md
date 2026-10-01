<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### リンク一つ、ワンクリックで完成。

オープンソース。カットと書き出しは手元のパソコンで。リンクと投稿先を選び、<b>動画・表紙・投稿文</b>を生成します。<br>
抖音・小紅書・TikTok・Reels・YouTube Shorts・Bilibili・YouTube に対応。<br>
アプリは無料、クラウドモデルは従量課金。調整したいときはエディターを使えます。

<p>
  <a href="https://github.com/zhouxiaoka/autoclip/releases/latest"><img src="https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square" alt="GitHub release"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/stargazers"><img src="https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square" alt="GitHub stars"></a>
  <a href="https://github.com/zhouxiaoka/autoclip/releases"><img src="https://img.shields.io/github/downloads/zhouxiaoka/autoclip/total?style=flat-square" alt="Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License: MIT"></a>
</p>

<a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>

**[デスクトップ版を入手](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [事例](https://zhouxiaoka.github.io/autoclip_intro/cases/) · [クイックスタート](#クイックスタート) · [ドキュメント](#ドキュメント) · [不具合報告](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

[简体中文](README.md) · [English](README-EN.md) · **日本語** · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

</div>

**[1.5.0 正式リリース](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0)**。デスクトップ・CLI・MCP を同時更新。自動制作、字幕のページ分割、人物構図、長尺キューの修正は [変更履歴](CHANGELOG.md) を参照し、旧版から更新してください。

## 実際の完成クリップ

![AutoClip の縦型クリップ：小紅書インタビュー、TikTok ポッドキャスト、抖音インタビュー、Shorts ポッドキャスト](docs/images/v2/demo-wall.webp)

AutoClip による対談式・ポッドキャスト式の包装例です。完成動画と原作者情報は **[事例ライブラリ →](https://zhouxiaoka.github.io/autoclip_intro/cases/)**。

投稿先に合わせた動画・表紙・タイトル・説明・ハッシュタグ・ZIP 投稿パックを生成。事例は随時更新、[完成動画の投稿](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell)も歓迎。

元映像の著作権は原作者にあります。効果展示：[Dwarkesh Patel — Dario Amodei](https://www.youtube.com/watch?v=n1E9IZfvGMA) · [Y Combinator — Sam Altman](https://www.youtube.com/watch?v=ZIaOBAjvc38) · [WIRED — Hideo Kojima](https://www.youtube.com/watch?v=02Ah5VQrzvA)

## できること

### リンクを貼れば完成

投稿先の画角と長さ条件に合わせて生成。各プラットフォームで条件を満たす上位最大 10 本を自動制作し、残りは必要時に生成します。表紙・タイトル・説明・ハッシュタグ・ZIP 投稿パックを同梱。

### 包装は自動

抖音 / 小紅書は対談式、TikTok / Reels / Shorts は全画面ポッドキャスト式が既定。縦型レイアウトは選択でき、字幕と投稿文の言語は投稿先に従います。Bilibili / YouTube は横型。人物を追従し、人物のいない場面は全体を保持。ブランドのアウトロは既定でオン、設定でオフにできます。コピーした投稿文に AutoClip の署名は付きません。

### 手元のパソコンで

カット・構図・書き出しはローカル。分析モデルを選び、作者字幕、ローカル Whisper / SenseVoice、設定済みクラウド文字起こしを利用できます。CLI / MCP も同じ自動制作パイプラインです。

## 実素材での時間と費用

開発中の異なる 3 素材の記録であり、同一入力の比較試験ではありません。当時の qwen-plus テキストモデル使用量による推計で、クラウド ASR・AI 画像生成・投稿サービスの費用は含みません。実際の請求は事業者によります。

| 版 | 元動画 | 出力 | テキストモデル費用の推計（人民元） |
| --- | --- | ---: | ---: |
| **新版 · 字幕あり** | Jensen · 1h43m（英 → 小紅書） | **7.5 分 / 10 本** | **¥0.09** |
| 新版 · 字幕なし | TIM × 羅永浩 · 2h52m（中 → 抖音） | 29.5 分 / 10 本 | ¥0.20 |
| 旧版 | MrBeast · 2h06m（英 → TikTok） | 65 分 | ¥0.64 |

<details>
<summary>測定条件と記録</summary>

2026-10-01、同じ Apple Silicon Mac。新パイプラインの 2 件は 10 本、旧版は 33 本を生成し、素材と本数が異なります。Jensen は作者字幕、TIM はローカル Whisper base を使用。

作者字幕があれば文字起こしを省略。なければローカルまたはクラウド ASR を選択。投稿先や追加クリップが増えると時間・使用量も増えます。[詳細記録](docs/COST_PER_VIDEO.md)（中国語）。

</details>

## モデルとデータの送り先を選ぶ

カットと書き出しは端末内。クラウド分析には関連字幕と投稿文、映像理解や参照画像生成には必要な抽出フレーム、クラウド文字起こしには音声を送ります。ローカル分析・文字起こしは対応するクラウド API 不要です。投稿を選ぶと完成動画を接続済みの投稿先へ送信。統計・エラー報告は設定で無効にできます。[プライバシー](docs/PRIVACY.en.md)。

## クイックスタート

| やりたいこと | おすすめ | 用意するもの |
| --- | --- | --- |
| このパソコンで作る | **デスクトップ** | macOS Apple Silicon または Windows x64 |
| 自前 Web / Linux | **Docker** | Docker と Compose v2 |
| 一括 / Agent | **CLI / MCP** | Python 3.10+（3.11 推奨）と FFmpeg |

### デスクトップ

1. **インストール。** [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) から。macOS Apple Silicon は `.dmg`、Windows 10 / 11 x64 は `-setup.exe`。Python と FFmpeg 同梱。
2. **モデル設定。** 事業者と API Key を設定し、利用可能な分析モデルを選択、接続テスト後に保存。ローカルは先に Ollama / LM Studio でモデルを読み込み、サービスを起動します。
3. **リンクと投稿先を選ぶ。** 字幕付きの対談やポッドキャストで試し、縦型レイアウトを選択。字幕がなければ設定で Whisper / SenseVoice を準備、またはクラウド文字起こしを設定。
4. **確認して保存。** 字幕・構図・内容の完全性を確認し、投稿パックを保存または接続済みアカウントへ投稿。必要に応じて追加候補を生成。

Intel Mac / Linux は Docker または CLI を利用できます。必要環境・初回起動・検証範囲は [インストールガイド](docs/USER_INSTALLATION_GUIDE.en.md) と [1.5.0 Release](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0) を参照。

[インストールガイド](docs/USER_INSTALLATION_GUIDE.en.md) · [トラブルシュート](docs/FAQ.en.md)

**Docker / Web**

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env
mkdir -p data logs uploads
docker compose up -d --build
```

[Web UI](http://localhost:3000) を開く。[API ドキュメント](http://localhost:8000/docs) はバックエンド起動後。[Docker ガイド](docs/DOCKER.en.md)。

Linux でバインドマウントの権限エラーが出たら、先に所有者を直します。

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

LAN IP や独自ドメインから開く場合、`.env` の `AUTOCLIP_ALLOWED_ORIGINS` にフロントエンドの URL をカンマ区切りで追加。

**CLI / MCP**

Python 3.10+（3.11 推奨）、PATH 上の FFmpeg と FFprobe が必要。Redis は不要です。[正式 CLI / MCP ZIP](https://github.com/zhouxiaoka/autoclip/releases/download/v1.5.0/autoclip-1.5.0-cli-mcp.zip) を解凍し、そのディレクトリで実行：

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --force-reinstall --no-deps autoclip-1.5.0-py3-none-any.whl
```

上記は macOS / Linux 用。Windows は `py -m venv venv` で作成し、`.\venv\Scripts\Activate.ps1` で有効化。その後は同じ `python -m pip` コマンドでインストールします。

先にモデル設定を保存。デスクトップ設定を共有、または ZIP の Key 無しサンプルで専用データディレクトリを設定。[CLI / MCP](docs/CLI_AND_MCP.md)（中国語）。`produce` は旧 `run --provider` の一時指定を使いません。`--srt` で文字起こしを省略。

```bash
autoclip --version
autoclip produce talk.mp4 --srt talk.srt --platform douyin --portrait-style podcast --json
autoclip outputs PROJECT_ID --export-kits
```

MCP サーバーはクライアントが起動します。単独の確認は別の端末で `autoclip mcp`。OpenCode の設定は `autoclip mcp install opencode` で作成できます。

`PROJECT_ID` は制作結果の ID に置換。MCP は `start_quick_output` / `get_quick_output_status` を使用。クライアントの `command` は仮想環境の `autoclip` 絶対パス、`args` は `["mcp"]`。旧 `run` / `export` と切片ツールも利用可能。[CLI / MCP](docs/CLI_AND_MCP.md)（中国語）・[OpenCode](docs/OPENCODE.en.md)・[Agent skill](skills/autoclip/SKILL.md)（中国語）。

## モデル設定

| 方法 | 設定 |
| --- | --- |
| クラウド API | 設定で事業者を選び API Key。OpenAI 互換は Base URL も可。 |
| Ollama | 既定 `http://localhost:11434/v1`。ローカルモデルを取得・起動し、サービスが提供するモデルを選択。Key 不要。 |
| LM Studio | モデルを読み Local Server を起動。既定 `http://localhost:1234/v1`。 |

Docker 内の `localhost` はコンテナ自身です。ホストのモデルにはコンテナから届く住所を指定。

[モデル設定](docs/MULTI_LLM_PROVIDER_GUIDE.md)（中国語） · [ローカルとコンテナ](docs/CLI_AND_MCP.md)（中国語）

## スポンサーへの感謝 ❤️

<table>
  <tr>
    <td align="center" width="140">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="88"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td>
      <strong>88API Tokenプラットフォーム</strong> のご支援に感謝します！GPT、Claude、Gemini、Grok、DeepSeek、Kimi、GLM を集約し、字幕分析・見どころ選定・タイトル生成に活用できます。<br>
      🎨 <strong>マルチメディア</strong>：GPT-Image、Seedance、Veo、MiniMax Hailuo H3、Kling、Whisper、TTS などの画像・動画・音声モデルを提供。AutoClip は対応する分析・カバー画像生成・文字起こし API を利用できます。<br>
      🏷️ <strong>サービスと決済</strong>：提携先によると海外法人が運営し、有人サポート・請求書・1:1 のチャージ比率を提供。条件はプラットフォームをご確認ください。<br>
      🎁 <strong>新規登録特典</strong>：<a href="https://88api.ai/sign-up?aff=2PIc">専用紹介リンク</a>から登録するとモデル検証用の体験クレジットを受け取れます。適用条件はキャンペーンページをご確認ください。 <a href="docs/88API_SETUP.en.md">設定ガイド（英語）</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="88"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar.cc</strong></a>
    </td>
    <td>
      AutoClip を支援する <strong>Infistar.cc</strong> に感謝します！長い動画の字幕分析、見どころの選定、タイトル生成に利用できる複数モデルの API サービスです。<br>
      ⚙️ <strong>互換 API で設定</strong>：AutoClip で OpenAI 互換の提供元を選び、Base URL、API キー、利用可能なモデルを入力します。<br>
      🧩 <strong>モデルを選択</strong>：提供元は Claude、GPT、Gemini、DeepSeek などを取り扱っています。互換エンドポイントに対応するモデルで、字幕分析や見どころ選定の結果を比較できます。<br>
      🏷️ <strong>料金とサービス</strong>：提供元の案内では、一部モデルは<strong>公式定価の 1% から</strong>利用でき、人民元決済、請求書発行、モデルの真正性確認に対応しています。対象モデル、料金、条件は提供元のページをご確認ください。<br>
      🎁 <strong>AutoClip 限定特典</strong>：新規ユーザーは<a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">専用紹介リンク</a>から登録すると <strong>$5 のお試しクレジット</strong>を受け取れます。適用条件はキャンペーンページをご確認ください。 <a href="docs/INFISTAR_SETUP.en.md">設定ガイド（英語）</a>
    </td>
  </tr>
</table>

## よくある質問

<details>
<summary>有料ですか。API Key は必要ですか。</summary>

アプリは無料・MIT。クラウド分析・文字起こし・AI 画像生成は自分の認証情報と事業者の料金を使用。既定の自動表紙は有料の画像生成を使いません。Ollama / LM Studio はクラウド Key 不要ですが適切な機材が必要。直接投稿には自分の Bilibili または [Upload-Post](https://www.upload-post.com) アカウントが必要。

</details>

<details>
<summary>動画はアップロードされますか。</summary>

カットと書き出しは端末内。クラウド分析には関連字幕と投稿文、映像理解や参照画像生成には必要な抽出フレーム、クラウド文字起こしには音声を送ります。ローカル分析・文字起こしは対応するクラウド API 不要です。投稿を選ぶと完成動画を接続済みの投稿先へ送信。統計・エラー報告は設定で無効にできます。[プライバシー](docs/PRIVACY.en.md)。

</details>

<details>
<summary>向いている動画は。</summary>

主に検証しているのは対談・ポッドキャスト・講義・トーク。作者字幕があれば最速、なければローカルまたはクラウド文字起こし。ゲームや会話の少ない素材は画像対応モデルで映像理解を有効にし、選ばれた場面を確認してください。

</details>

<details>
<summary>クリップができません。</summary>

字幕・文字起こし、モデル接続、FFmpeg、ディスク、投稿先条件を確認。YouTube 長尺は完結した 180 秒以上のクリップが必要。短い素材は Shorts / Bilibili を選択。続く場合は版・OS・尺・モデル・匿名化ログを [既知の問題](https://github.com/zhouxiaoka/autoclip/issues/96) へ。

</details>

[トラブルシュート](docs/FAQ.en.md) · [既知の問題](https://github.com/zhouxiaoka/autoclip/issues/96)

## ドキュメント

| 知りたいこと | 文書 |
| --- | --- |
| インストールと初回 | [インストール](docs/USER_INSTALLATION_GUIDE.en.md) |
| 自前運用と自動化 | [Docker](docs/DOCKER.en.md) · [CLI / MCP](docs/CLI_AND_MCP.md)（中国語） · [Agent skill](skills/autoclip/SKILL.md)（中国語） · [OpenCode](docs/OPENCODE.en.md) |
| モデルと障害 | [モデル設定](docs/MULTI_LLM_PROVIDER_GUIDE.md)（中国語） · [FAQ](docs/FAQ.en.md) |
| 版・ロードマップ・プライバシー | [更新履歴](CHANGELOG.md) · [ロードマップ](ROADMAP.md)（中国語） · [コミュニティ掲示板](docs/COMMUNITY_BOARD.md)（中国語） · [プライバシー](docs/PRIVACY.en.md) |
| 開発と翻訳 | [貢献](CONTRIBUTING.md)（中国語） · [翻訳の管理](docs/i18n.md)（中国語） |

## 参加する

修正、完成例、感想、翻訳の改善を歓迎します。役に立ったら Star を。

- **話す：** [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [初回 Q&A](https://github.com/zhouxiaoka/autoclip/discussions/128) · [アイデア](https://github.com/zhouxiaoka/autoclip/discussions/129)
- **不具合：** [Issue フォーム](https://github.com/zhouxiaoka/autoclip/issues/new/choose) に OS、版、モデル、手順、伏せたログ
- **提携：** [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

個人メンテです。即時サポートや個別デプロイはありません。

![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)

FastAPI、React、Tauri、FFmpeg、yt-dlp、Whisper、FunASR とすべての貢献者に感謝。[MIT License](LICENSE)。
