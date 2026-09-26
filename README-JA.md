<div align="center">

<img src="src-tauri/icons/128x128.png" alt="AutoClip" width="80" height="80">

# AutoClip

**長い動画から、シェアしたくなる見どころを。**

[简体中文](README.md) · [English](README-EN.md) · **日本語** · [한국어](README-KO.md) · [Español](README-ES.md) · [Português](README-PT.md) · [Русский](README-RU.md) · [Français](README-FR.md)

[![GitHub release](https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/forks)
[![GitHub issues](https://img.shields.io/github/issues/zhouxiaoka/autoclip?style=flat-square)](https://github.com/zhouxiaoka/autoclip/issues)
[![License: MIT](https://img.shields.io/github/license/zhouxiaoka/autoclip?style=flat-square)](LICENSE)

<p align="center">
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending #3" width="250" height="55"></a>
</p>

ローカルで編集 · モデルのキーは自分で用意

Trendshift が記録した掲載実績であり、現在のリアルタイム順位ではありません。GitHub Trending と Trendshift は別のランキングです。

[公式サイト](https://zhouxiaoka.github.io/autoclip_intro/) · [Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [問題を報告](https://github.com/zhouxiaoka/autoclip/issues)

**デスクトップ版: [macOS · Apple Silicon](https://github.com/zhouxiaoka/autoclip/releases/latest) · [Windows · x64](https://github.com/zhouxiaoka/autoclip/releases/latest)**

[インストールと最初のクリップ作成 (English)](docs/USER_INSTALLATION_GUIDE.en.md) · [詳しいトラブル対処（英語）](docs/FAQ.en.md)

</div>

v1.3.1 から、アプリ、公式サイト、README は中国語・英語・日本語・韓国語・スペイン語・ポルトガル語・ロシア語・フランス語に対応しています。ヘッダーで言語を選択するか、システム設定に従えます。素材と生成内容の言語は変わりません。

AutoClip は AI で動画の字幕を分析し、見どころを抽出してタイトルを作成し、クリップやまとめ動画を自動生成します。インタビュー、ポッドキャスト、講義、ライブ配信のアーカイブに適しており、デスクトップアプリ、Docker の Web UI、CLI / MCP から利用できます。

## 画面プレビュー

![AutoClip v1.3.0 — local video import](docs/images/import-local.jpg)

v1.3.0 の実際の Web 画面です。ファイル読み込み欄からローカル動画と任意の SRT 字幕を追加できます。

## 主な機能

| 機能 | 説明 |
| --- | --- |
| 動画の読み込み | ローカル動画、YouTube、Bilibili のリンクに対応。SRT 字幕も指定できます。 |
| 見どころの抽出 | 字幕から概要、トピックの時間範囲、評価スコア、クリップのタイトルを生成します。 |
| クリップとまとめ動画 | クリップとおすすめのまとめ動画を生成し、順序を手動で変更できます。 |
| 投稿（v1.3.2） | **v1.3.2** から、クリップができたら同じ画面で投稿または予約できます。海外のプラットフォームは Upload-Post を使い、Bilibili は設定でログイン Cookie を一度貼り付けます。既定はプラットフォームが許す範囲で非公開です。投稿せずに書き出すこともできます。詳細は [投稿ガイド（中国語）](docs/PUBLISH_UPLOAD_POST.md)。 |
| 自動カバー（v1.3.2） | 投稿時にカバーを自動生成し、空のカバーで Bilibili に拒まれないようにします。既定はインストール説明に従います。**v1.3.2** から使えます。 |
| 公開用の書き出し | Douyin、小紅書、YouTube Shorts、Bilibili 向けのプリセット、字幕の焼き込み、タイトルカードに対応します。 |
| モデルの選択 | Qwen、OpenAI、Gemini、DeepSeek、Doubao Seed、Kimi、GLM、および Ollama / LM Studio のローカルモデルに対応します（API キーは自分で用意）。 |
| 自動化 | CLI で処理を組み合わせたり、MCP クライアントから同じ処理パイプラインを呼び出したりできます。 |

> 動画を読み込み → 字幕の準備 / 文字起こし → AI 分析・評価 → クリップとまとめ動画を生成 → 書き出し

## クイックスタート

### 1. デスクトップ版

[GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) から、お使いの環境に合うインストーラーをダウンロードしてください。

| プラットフォーム | インストール方法 |
| --- | --- |
| macOS · Apple Silicon | `.dmg` |
| Windows 10 / 11 · x64 | `-setup.exe` |
| Intel Mac / Linux | 以下の Docker または CLI を使用 |

デスクトップ版には Python と FFmpeg が含まれます。対応環境と初回起動の手順は各リリースをご確認ください。インストール後、設定でモデルプロバイダーを選び、接続をテストして保存してから動画を読み込みます。

### 2. Docker / Web

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

### 3. CLI / MCP

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

## モデル設定

| 方式 | 設定 |
| --- | --- |
| クラウドモデル | 設定で Qwen、OpenAI、Gemini、DeepSeek、Doubao Seed、Kimi または GLM を選び、API キーを入力します。互換インターフェースでは Base URL を指定できます。 |
| Ollama | 既定のアドレスは `http://localhost:11434/v1`、モデルは `qwen2.5:7b`。API キーは不要です。 |
| LM Studio | モデルを読み込み、Local Server を起動します。既定のアドレスは `http://localhost:1234/v1`。サーバーで提供中のモデルを選びます。 |

Docker 内の `localhost` はコンテナ自身を指します。ホストのモデルを使う場合は、コンテナから接続できるアドレスを設定してください。詳細は CLI / MCP ガイドにあります。動画の切り出しはローカルで行いますが、クラウドモデルによる分析では字幕テキストを選択したプロバイダーに送信します。動画やモデルのダウンロードにはネット接続が必要です。

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

</details>

[詳しいトラブル対処（英語）](docs/FAQ.en.md) · [既知の問題](https://github.com/zhouxiaoka/autoclip/issues/96)

## ドキュメント

README は 8 言語で提供しています。以下の詳細ガイドは主に中国語です。README の翻訳言語と、アプリの UI や文字起こしモデルの対応言語は異なります。

- [インストールと最初のクリップ作成 (English)](docs/USER_INSTALLATION_GUIDE.en.md)
- [Docker デプロイ（中国語）](DOCKER.md)
- [CLI・MCP・ローカルモデル（中国語）](docs/CLI_AND_MCP.md)
- [モデルプロバイダー（中国語）](docs/MULTI_LLM_PROVIDER_GUIDE.md)
- [よくある質問（中国語）](docs/FAQ.md)
- [貢献ガイド（中国語）](CONTRIBUTING.md)
- [変更履歴](CHANGELOG.md)
- [プライバシーについて（中国語 / 英語）](docs/PRIVACY.en.md)
- [README 翻訳・バッジ管理（中国語）](docs/i18n.md)

## 貢献とお問い合わせ

コードの修正、フィードバック、翻訳の改善を歓迎します。不具合の報告には、OS、バージョン、モデル、再現手順、機密情報を取り除いたエラーログを添えてください。

個人が余暇に保守しています。返信時期は一定ではなく、即時サポートや個別の導入支援は提供していません。お問い合わせの前によくある質問と既知の問題をご確認ください。

機能のアイデア、使い方、モデルの要望は [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions) へ。再現できる不具合は [Issue テンプレート](https://github.com/zhouxiaoka/autoclip/issues/new/choose) を使ってください。ルールは [コミュニティボード](docs/COMMUNITY_BOARD.md)（中国語）にあります。

- [案内とカテゴリ](https://github.com/zhouxiaoka/autoclip/discussions/127)
- [最初のクリップ Q&A](https://github.com/zhouxiaoka/autoclip/discussions/128)
- [アイデア](https://github.com/zhouxiaoka/autoclip/discussions/129)

- メール: [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

FastAPI、React、Tauri、FFmpeg、yt-dlp、Whisper、およびすべての貢献者に感謝します。[MIT License](LICENSE) で公開しています。AutoClip が役に立ったら、Star で応援してください。

[![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)](https://star-history.com/#zhouxiaoka/autoclip&Date)
