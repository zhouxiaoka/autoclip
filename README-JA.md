<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### リンク一つ、ワンクリックで完成。

オープンソース、無料、手元のパソコンで動きます。リンクを貼り、数十円で <b>10本以上の投稿用クリップ</b> を受け取り、<br>
表紙・タイトル・説明・ハッシュタグまで、抖音・小紅書・TikTok・Reels・YouTube Shorts 用に揃います。<br>
編集ソフトも、AI との長いやり取りも不要です。

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

## 実際の完成クリップ

![AutoClip の縦型クリップ：小紅書インタビュー、TikTok ポッドキャスト、抖音インタビュー、Shorts ポッドキャスト](docs/images/v2/demo-wall.webp)

元動画はリンクを貼っただけです。上の各本は AutoClip が自動で選び、構図を決め、翻訳し、包装したそのままの出力で、人手の修正はありません。**[事例ライブラリで音声付きで見る →](https://zhouxiaoka.github.io/autoclip_intro/cases/)**

各クリップは対象プラットフォーム向けの一式です。縦動画、表紙、タイトル、説明、ハッシュタグ。ライブラリは随時更新します。[投稿する](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell)。

元映像の著作権は原作者にあります。効果展示：[Dwarkesh Patel — Dario Amodei](https://www.youtube.com/watch?v=n1E9IZfvGMA) · [Y Combinator — Sam Altman](https://www.youtube.com/watch?v=ZIaOBAjvc38) · [WIRED — Hideo Kojima](https://www.youtube.com/watch?v=02Ah5VQrzvA)

## できること

### リンクを貼れば完成
編集ソフトも AI チャットも不要。プラットフォームを選び、画角どおりに生成。表紙・タイトル・説明・ハッシュタグ付き。

### 包装は自動
抖音 / 小紅書はインタビュー型、TikTok / Reels / Shorts はポッドキャスト型。画面は話者を追い、外国語素材には現地語タイトルと二カ国語字幕。

### 手元のパソコンで
カットと書き出しはローカル。モデルは自分で選ぶ。直したいときだけ編集、一括は CLI / MCP。

## 速く、安い

リンク一つで、**10本以上**の投稿可能なクリップ。表紙・タイトル・説明・ハッシュタグ付き。

| 版 | 元動画 | 出力 | 費用 |
| --- | --- | ---: | ---: |
| **新版 · 字幕あり** | Jensen · 1h43m（英 → 小紅書） | **7.5 分 / 10 本** | **¥0.09** |
| 新版 · 字幕なし | TIM × 羅永浩 · 2h52m（中 → 抖音） | 29.5 分 / 10 本 | ¥0.20 |
| 旧版 | MrBeast · 2h06m（英 → TikTok） | 65 分 | ¥0.64 |

2–3 時間の対談はだいたい ¥0.1–0.2。作者字幕が無いと音声認識はローカルで、時間は長くなります。動画はパソコンから出ません。

<details>
<summary>計測条件</summary>

2026 年 10 月 1 日、同じ Apple Silicon Mac、分析モデル qwen-plus（100 万 tokens 入力 ¥0.8 / 出力 ¥2、阿里云百煉の第三者掲載価格）。費用はモデル呼び出しのみ。

Jensen の 7.5 分：ダウンロード約 1 分、作者字幕で文字起こし省略、ハイライト 25 秒、カット / 構図 / 包装約 2.5 分、10 本の書き出し約 3 分。旧版はハイライトだけで 35 分。

この版の主な変更：全文を一度にハイライト抽出、モデル呼び出しの並列化、作者字幕があればローカル ASR を省略、既定は上位 10 本だけ書き出し。

</details>

## 月額クラウドツールとの違い

| | AutoClip | 月額のクラウドツール |
| --- | --- | --- |
| 費用 | アプリ無料。モデルは従量。2–3 時間対談で約 ¥0.1–0.2 | 月額、処理時間で課金 |
| 動画の処理場所 | 自分のパソコン。クラウドモデルは字幕テキストのみ | 事業者のクラウドへアップロード |
| モデル | 自分で選ぶ、ローカルも可 | プラットフォーム指定 |
| 中国向け | 抖音・小紅書・B 站の専用テンプレ | 海外向けが中心 |
| コード | MIT、改変・自前デプロイ可 | クローズド |

右列は 2026 年 10 月時点の公開ページに基づきます。各製品の最新説明を確認してください。

## クイックスタート

| やりたいこと | おすすめ | 用意するもの |
| --- | --- | --- |
| このパソコンで作る | **デスクトップ** | macOS Apple Silicon または Windows x64 |
| 自前 Web / Linux | **Docker** | Docker と Compose v2 |
| 一括 / Agent | **CLI / MCP** | Python 3.10+（3.11 推奨）と FFmpeg |

### デスクトップ

1. **インストール。** [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) から。macOS Apple Silicon は `.dmg`、Windows 10 / 11 x64 は `-setup.exe`。Python と FFmpeg 同梱。
2. **モデル。** 設定で事業者を選び API Key を入れると分析モデルは自動選択。ローカルなら先に Ollama か LM Studio を起動。
3. **リンクを貼り、配信先を選ぶ。** 字幕付きの 10–30 分対談から。字幕が無い場合は設定で Whisper か SenseVoice を用意。
4. **受け取る。** 上位 10 本を確認し、必要なら編集してダウンロードまたは投稿。

インストーラはまだ Apple 公証・Windows 署名がありません。macOS は初回右クリック「開く」、Windows は SmartScreen で「詳細情報 → 実行」。

[インストールガイド](docs/USER_INSTALLATION_GUIDE.en.md) · [トラブルシュート](docs/FAQ.en.md)

**Docker / Web**

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env          # 选择 LLM_PROVIDER，填 API Key 和模型名；也可以启动后在设置页配置
mkdir -p data logs uploads
docker compose up -d --build
```

[Web UI](http://localhost:3000) を開く。[API ドキュメント](http://localhost:8000/docs) はバックエンド起動後。[Docker ガイド](docs/DOCKER.en.md)。

Linux でバインドマウントの権限エラーが出たら、先に所有者を直します。

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

**CLI / MCP**

Python 3.10+（3.11 推奨）と PATH 上の FFmpeg。CLI のローカル処理に Redis は不要。

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

MCP クライアントでは `command` を仮想環境の `autoclip` 絶対パス、`args` を `["mcp"]` に。[CLI / MCP](docs/CLI_AND_MCP.md)（中国語）、[OpenCode](docs/OPENCODE.en.md)、[Agent skill](skills/autoclip/SKILL.md)（中国語）。

## モデル設定

| 方法 | 設定 |
| --- | --- |
| クラウド API | 設定で事業者を選び API Key。OpenAI 互換は Base URL も可。 |
| Ollama | 既定 `http://localhost:11434/v1`、モデル `qwen2.5:7b`、Key 不要。 |
| LM Studio | モデルを読み Local Server を起動。既定 `http://localhost:1234/v1`。 |

Docker 内の `localhost` はコンテナ自身です。ホストのモデルにはコンテナから届く住所を指定。

[モデル設定](docs/MULTI_LLM_PROVIDER_GUIDE.md)（中国語） · [ローカルとコンテナ](docs/CLI_AND_MCP.md)（中国語）

## スポンサー

AutoClip を支援してくださっているパートナーです。どちらも OpenAI 互換 API で、設定から選んで Key を入れると利用可能なモデルが一覧されます。

<table>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://88api.ai/sign-up?aff=2PIc"><img src="docs/sponsors/88api-logo.jpg" alt="88API" width="72"></a><br>
      <a href="https://88api.ai/sign-up?aff=2PIc"><strong>88API</strong></a>
    </td>
    <td valign="middle">
      GPT、Claude、Gemini、Grok、DeepSeek、Kimi、GLM と画像・動画・音声。有人サポート、正規領収書、チャージ 1:1。<a href="https://88api.ai/sign-up?aff=2PIc">紹介リンク</a>で体験枠。<a href="docs/88API_SETUP.en.md">手順</a>
    </td>
  </tr>
  <tr>
    <td align="center" width="140" valign="middle">
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><img src="docs/sponsors/infistar-logo.svg" alt="Infistar" width="72"></a><br>
      <a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link"><strong>Infistar</strong></a>
    </td>
    <td valign="middle">
      Claude、GPT、Gemini、DeepSeek など。一部は公式の 0.1 折、人民元決済、領収書、モデル検証。<a href="https://www.infistar.cc/register?aff=XLK3BCM6&amp;ref_source=link">紹介リンク</a>で $5 体験。<a href="docs/INFISTAR_SETUP.en.md">手順</a>
    </td>
  </tr>
</table>

サービス・価格・特典はパートナー提供、各サイトの表示が優先です。

## よくある質問

<details>
<summary>有料ですか。API Key は必要ですか。</summary>

AutoClip は無料・MIT。クラウドモデルは事業者の従量で自分の Key が必要。1 時間 43 分の対談で約 ¥0.09。Ollama / LM Studio はクラウド Key 不要ですが機材は必要。海外投稿には自分の [Upload-Post](https://www.upload-post.com) アカウント。

</details>

<details>
<summary>動画はアップロードされますか。</summary>

カットと書き出しは端末内。クラウドモデルには字幕テキストだけ。完成クリップは「公開」を押したあと、接続済みの先にだけ送られます。分析とエラー報告は設定でオフにできます。[プライバシー](docs/PRIVACY.en.md)。

</details>

<details>
<summary>向いている動画は。</summary>

字幕ベースなので対談・ポッドキャスト・講義・トーク向き。作者字幕があると最速。無い場合は先にローカル文字起こし。映像だけ・音楽ものは限定的。

</details>

<details>
<summary>クリップができません。</summary>

失敗段階を確認：字幕空、モデル接続、FFmpeg、ディスク。より強いモデルを試す。続く場合は [既知の問題](https://github.com/zhouxiaoka/autoclip/issues/96) に種類・尺・モデルを添えて。

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
