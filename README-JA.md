<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="72" height="72">

# AutoClip

### オープンソースの AI ハイライト動画編集ツール

長い動画から、シェアしたくなる見どころを。

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

**[デスクトップ版を入手](https://github.com/zhouxiaoka/autoclip/releases/latest)** · [クイックスタート](#quick-start) · [公式サイト](https://zhouxiaoka.github.io/autoclip_intro/) · [ドキュメント](#documentation) · [問題を報告](https://github.com/zhouxiaoka/autoclip/issues/new/choose)

[简体中文](README.md) · [English](README-EN.md) · **日本語** · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

</div>

AutoClip は AI で動画の字幕を分析し、見どころを抽出してタイトルを作成し、クリップやまとめ動画を自動生成します。インタビュー、ポッドキャスト、講義、ライブ配信のアーカイブに適しており、デスクトップアプリ、Docker の Web UI、CLI / MCP から利用できます。

## 画面プレビュー

![動画の読み込みとプロジェクト管理](docs/images/home-v1.4.0.png)

<table>
  <tr>
    <td width="50%" align="center"><strong>AI によるクリップ生成結果</strong></td>
    <td width="50%" align="center"><strong>Studio でプレビュー・編集</strong></td>
  </tr>
  <tr>
    <td><a href="docs/images/clips-v1.4.0.png"><img src="docs/images/clips-v1.4.0.png" alt="AI によるクリップ生成結果" width="100%"></a></td>
    <td><a href="docs/images/studio-v1.4.0.png"><img src="docs/images/studio-v1.4.0.png" alt="Studio でプレビュー・編集" width="100%"></a></td>
  </tr>
</table>

<sub>v1.4.0 に後続の Studio 修正を含む実際の画面です。動画の読み込み、実際に生成されたクリップの確認、Studio での編集を紹介します。UI は中国語、事例の字幕と生成タイトルは英語です。</sub>

[撮影バージョンと事例の出典（中国語）](docs/images/README.md)

## スポンサーへの感謝 ❤️

<table>
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

## 主な機能

### 長い動画から見どころを抽出

- **動画の読み込み**: ローカル動画、YouTube、Bilibili のリンクに対応。SRT 字幕も指定できます。
- **見どころの抽出**: 字幕から概要、トピックの時間範囲、評価スコア、クリップのタイトルを生成します。
- **クリップとまとめ動画**: クリップとおすすめのまとめ動画を生成し、順序を手動で変更できます。

### 書き出しと投稿

- **公開用の書き出し**: Douyin、小紅書、YouTube Shorts、Bilibili 向けのプリセット、字幕の焼き込み、タイトルカードに対応します。
- **カバーと投稿**：v1.3.2 以降はカバーの自動生成、即時投稿、予約投稿に対応。海外プラットフォームは自分の Upload-Post アカウントで連携し、Bilibili は別途設定します。
- **投稿管理**：投稿履歴とカレンダーで予約を管理できます。投稿せず、動画をダウンロードすることも可能です。

<details>
<summary>対応プラットフォーム・アカウント・書き出しの詳細</summary>

クリップができたら、そのクリップで投稿を開きます。 **v1.3.2** から使えます。 海外は、自分の Upload-Post アカウントで接続したプラットフォームです。 TikTok、Instagram、YouTube、Facebook、LinkedIn、X、Threads、Pinterest、Bluesky、Discord、Telegram、Google Business のうち、そのアカウントで使えるもの。

Bilibili はアカウント 1 つです。 設定で Cookie を一度貼り付けます。 SESSDATA、bili_jct、DedeUserID が必要です。 今すぐ出すか、予約できます。

タイトルと説明は任意で、空ならクリップのタイトルです。 字幕の焼き込みは既定でオン、約 4 秒のタイトルカードも既定でオン。 公開範囲は対応しているプラットフォームでは既定で自分だけです。 private / 自分だけを約束するのは TikTok、YouTube、Bilibili だけです。

投稿せずに書き出すこともできます。 プロジェクトページで投稿履歴とカレンダーを見て、まだ出ていない予約を取り消せます。 「今週を組む」は海外だけです。 未投稿のクリップを月曜・水曜・金曜の 09:00 に入れ、Bilibili は含みません。

縦型アカウントは 9:16 で、60 秒では切りません。 Bilibili だけなら横画面。 LinkedIn または X だけなら元の画角。 縦型と Bilibili を同じ回で出すときは、それぞれ別に書き出します。

投稿時にカバーを自動生成でき、Bilibili の空カバー却下を避けます。

既定のカバーとタイトルカードの詳細は、その版のインストーラー説明に従います。 **v1.3.2** から使えます。

</details>

### 使い方に合わせて選択

- **モデルを選択**：Qwen、OpenAI 互換 API、Gemini などのクラウドサービス、または Ollama / LM Studio のローカルモデルを利用できます。
- **自動化**: CLI で処理を組み合わせたり、MCP クライアントから同じ処理パイプラインを呼び出したりできます。
- **多言語インターフェース**: v1.3.1 から、アプリ、公式サイト、README は中国語・英語・日本語・韓国語・スペイン語・ポルトガル語・ロシア語・フランス語に対応しています。ヘッダーで言語を選択するか、システム設定に従えます。素材と生成内容の言語は変わりません。

> 動画を読み込み → 字幕の準備 / 文字起こし → AI 分析・評価 → クリップとまとめ動画を生成 → 書き出し

<a id="quick-start"></a>

## クイックスタート

| 用途 | おすすめ | 必要な環境 |
| --- | --- | --- |
| パソコンで動画を編集 | **デスクトップ版** | macOS Apple Silicon / Windows x64 |
| セルフホスト / Linux | **Docker** | Docker + Compose v2 |
| 一括処理 / Agent 連携 | **CLI / MCP** | Python 3.10+（推奨 3.11）+ FFmpeg |

### デスクトップ版：最初のクリップ作成

1. **インストール。** [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) から、macOS Apple Silicon は `.dmg`、Windows 10 / 11 x64 は `-setup.exe` を入手します。Python と FFmpeg は同梱済み。Intel Mac / Linux は Docker または CLI を利用してください。動作条件は各リリースをご確認ください。
2. **モデル設定。** 設定で提供元を選び、API キーとモデル名を入力し、接続テスト後に保存します。ローカルモデルの場合は先に Ollama または LM Studio を起動します。
3. **動画を読み込む。** まずは 3〜5 分の動画で試してください。SRT 字幕も一緒に読み込めます。字幕がない場合は、設定でローカル Whisper と音声モデルを準備します。
4. **確認して書き出す。** クリップの開始・終了位置、タイトル、内容を確認し、書き出しプリセットを選びます。アカウントを連携して投稿することもできます。

[詳しいインストール手順（英語）](docs/USER_INSTALLATION_GUIDE.en.md) · [トラブル対処（英語）](docs/FAQ.en.md)

<details>
<summary><strong>Docker / Web</strong></summary>

Docker と Docker Compose v2 が必要です。リポジトリのルートで実行します。

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
```

```bash
cp env.example .env
```

起動前に `.env` を編集し、`LLM_PROVIDER`、対応する API キー、モデル名を設定してください。起動後に設定画面から変更することもできます。

```bash
mkdir -p data logs uploads
docker compose up -d --build
```

[Web UI](http://localhost:3000) を開きます。バックエンド起動後は [API ドキュメント](http://localhost:8000/docs) も利用できます。詳細は [Docker ガイド](DOCKER.md)（中国語）を参照してください。

Linux でバインドマウントしたディレクトリの権限エラーが出る場合は、次のコマンドでプロジェクトのデータディレクトリの所有者を修正し、サービスを再起動してください。

```bash
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
```

</details>

<details>
<summary><strong>CLI / MCP</strong></summary>

Python 3.10 以上（3.11 推奨）と PATH 上の FFmpeg が必要です。以下は macOS / Linux 用です。Windows PowerShell では `venv\Scripts\Activate.ps1` で仮想環境を有効化します。CLI のローカル処理に Redis は不要です。

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
```

ローカルモデルの例：Ollama をインストールして起動し、モデルをダウンロードします。字幕のない動画には `faster-whisper` が必要で、初回の文字起こし時に音声モデルをダウンロードします。既存の字幕を使う場合は `--srt talk.srt` を追加します。

```bash
ollama pull qwen2.5:7b
python -m pip install faster-whisper
autoclip doctor --provider ollama
autoclip run talk.mp4 --provider ollama --json
```

`PROJECT_ID` を処理結果のプロジェクト ID に置き換えると Shorts 形式で書き出せます。`autoclip mcp` は stdio MCP サーバーを起動します。

```bash
autoclip export PROJECT_ID --preset shorts
autoclip mcp
```

MCP クライアントの `command` に仮想環境内の `autoclip` の絶対パス、`args` に `["mcp"]` を設定します。[CLI / MCP ガイド](docs/CLI_AND_MCP.md)と [Agent skill](skills/autoclip/SKILL.md)（中国語）を参照してください。

</details>

## モデル設定

| 方式 | 設定 |
| --- | --- |
| クラウドモデル | 設定で提供元を選び、API キーとモデル名を入力します。OpenAI 互換サービスでは Base URL も指定できます。 |
| Ollama | 既定のアドレスは `http://localhost:11434/v1`、モデルは `qwen2.5:7b`。API キーは不要です。 |
| LM Studio | モデルを読み込み、Local Server を起動します。既定のアドレスは `http://localhost:1234/v1`。サーバーで提供中のモデルを選びます。 |

Docker 内の `localhost` はコンテナ自身を指します。ホストのモデルを使う場合は、コンテナから接続できるアドレスを設定してください。詳細は CLI / MCP ガイドにあります。動画の切り出しはローカルで行いますが、クラウドモデルによる分析では字幕テキストを選択したプロバイダーに送信します。動画やモデルのダウンロードにはネット接続が必要です。

[Infistar · 設定ガイド（英語）](docs/INFISTAR_SETUP.en.md)

## よくある質問

<details>
<summary>有料ですか？API キーは必要ですか？</summary>

AutoClip 本体は引き続き無料で、MIT ライセンスのオープンソースです。クラウドモデルは各社の利用料金がかかり、自分の API キーが必要です。Ollama / LM Studio はクラウドのキー不要ですが、モデルと対応するハードウェアが必要です。**v1.3.2** から、海外への投稿に自分の [Upload-Post](https://www.upload-post.com) アカウントが必要です。無料枠、有料枠、TikTok、YouTube、Instagram などの日次上限は Upload-Post 自身のページに従います。AutoClip の約束ではありません。

</details>

<details>
<summary>動画はアップロードされますか？</summary>

編集はお使いの端末に残ります。クラウドモデルには字幕テキストを送信します。完成したクリップが端末を離れるのは、「投稿」を押したあとだけで、接続済みのプラットフォームに送られます。投稿せずに書き出すこともできます。この投稿ページは **v1.3.2** から使えます。利用統計やエラー報告はバージョンと設定によるため、プライバシー説明をご確認ください。

</details>

<details>
<summary>字幕がなくても使えますか？</summary>

はい。先にローカルの Whisper コンポーネントと音声モデルを準備してください。既存の SRT も読み込めます。正確な字幕があれば文字起こしの待ち時間や認識ミスを減らせます。

</details>

<details>
<summary>クリップが生成されないのはなぜですか？</summary>

失敗した段階を確認し、空の字幕、モデル接続、評価のしきい値、FFmpeg、空き容量を調べてください。しきい値を 0.7 から 0.5 に下げて試せますが、生成は保証されません。

</details>

<details>
<summary>どんな動画に向いていますか？処理時間は？</summary>

主に字幕を分析するため、インタビュー、ポッドキャスト、講義、解説に向いています。映像中心の動作や音楽は十分に評価できない場合があります。時間は動画の長さ、機器、モデル、書き出し設定により異なるので、短い素材から試してください。

素材の準備と公開動画の例は [初回利用ガイド（英語）](docs/USER_INSTALLATION_GUIDE.en.md) をご覧ください。

</details>

[詳しいトラブル対処（英語）](docs/FAQ.en.md) · [既知の問題](https://github.com/zhouxiaoka/autoclip/issues/96)

<a id="documentation"></a>

## ドキュメント

| 内容 | ドキュメント |
| --- | --- |
| 初回利用 | [インストール（英語）](docs/USER_INSTALLATION_GUIDE.en.md) |
| ホスティングと自動化 | [Docker（英語）](docs/DOCKER.en.md) · [CLI / MCP（中国語）](docs/CLI_AND_MCP.md) · [Agent skill（中国語）](skills/autoclip/SKILL.md) |
| モデル設定とトラブル対処 | [モデル設定（中国語）](docs/MULTI_LLM_PROVIDER_GUIDE.md) · [トラブル対処（英語）](docs/FAQ.en.md) |
| バージョンとプライバシー | [変更履歴](CHANGELOG.md) · [プライバシー（英語）](docs/PRIVACY.en.md) |
| 開発と翻訳 | [貢献ガイド（中国語）](CONTRIBUTING.md) · [翻訳の管理（中国語）](docs/i18n.md) |
| スポンサーの設定 | [Infistar](docs/INFISTAR_SETUP.en.md) |

README は 8 言語に対応しています。インストール・Docker・トラブル対処には英語版があり、その他の詳細資料は主に中国語です。

## 貢献とお問い合わせ

コードの修正、フィードバック、翻訳の改善を歓迎します。不具合の報告には、OS、バージョン、モデル、再現手順、機密情報を取り除いたエラーログを添えてください。

個人が余暇に保守しています。返信時期は一定ではなく、即時サポートや個別の導入支援は提供していません。お問い合わせの前によくある質問と既知の問題をご確認ください。

機能のアイデア、使い方、モデルの要望は [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions) へ。再現できる不具合は [Issue テンプレート](https://github.com/zhouxiaoka/autoclip/issues/new/choose) を使ってください。ルールは [コミュニティボード](docs/COMMUNITY_BOARD.md)（中国語）にあります。

- [案内とカテゴリ](https://github.com/zhouxiaoka/autoclip/discussions/127)
- [最初のクリップ Q&A](https://github.com/zhouxiaoka/autoclip/discussions/128)
- [アイデア](https://github.com/zhouxiaoka/autoclip/discussions/129)

- メール: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

FastAPI、React、Tauri、FFmpeg、yt-dlp、Whisper、およびすべての貢献者に感謝します。[MIT License](LICENSE) で公開しています。AutoClip が役に立ったら、Star で応援してください。

<details>
<summary>コミュニティでの実績 · Star History</summary>

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily?language=Python" alt="AutoClip — Trendshift Python daily ranking" width="250" height="55"></a>
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/trendshift/repositories/25801/daily" alt="AutoClip — Trendshift daily ranking, all languages" width="250" height="55"></a>
</p>

以下は Trendshift が提供するバッジです。クリックすると AutoClip の掲載履歴を確認できます。GitHub Trending と Trendshift は別のランキングであり、バッジは記録された実績を示すもので、現在の順位ではありません。

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)

</details>
