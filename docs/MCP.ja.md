# AutoClip MCP・AI エージェント連携ガイド

[English](MCP.en.md) · [简体中文](CLI_AND_MCP.md) · **日本語** · [한국어](MCP.ko.md) · [Español](MCP.es.md) · [Deutsch](MCP.de.md)

Claude Code、Cursor、Windsurf、OpenCode などの MCP 対応 AI エージェントから AutoClip を直接操作し、長尺動画や配信アーカイブからショート動画を自動生成できます。デスクトップ版と同一のローカルパイプラインを使用するため、サブスク不要・透かしなし・完全ローカルレンダリングで動作します。

---

## 1 行セットアップ

### Claude Code
```bash
claude mcp add autoclip -- uvx autoclip-mcp
```

### エージェントスキル導入
```bash
npx skills add zhouxiaoka/autoclip
```

### Cursor / Windsurf / 汎用 MCP クライアント（`mcp.json`）
```json
{
  "mcpServers": {
    "autoclip": {
      "command": "uvx",
      "args": ["autoclip-mcp"]
    }
  }
}
```

> **必要環境:** Python 3.10+（3.11 推奨）、`uv`（`uvx`）、`ffmpeg`。バージョン確認は `autoclip --version` または MCP の `get_version` を使用してください。

---

## 主な MCP ツール

| ツール名 | 用途 |
| :--- | :--- |
| `get_version` | インストール済み AutoClip のバージョンを取得 |
| `list_styles` | 利用可能な編集スタイル（`editorial`、`street`、`news`、`cinema`、`classic` など）を一覧取得 |
| `start_quick_output` | 切り抜き・字幕焼き込み・表紙生成ジョブを非同期開始 |
| `get_quick_output_status` | 進捗（`progress` / `stage` / `eta`）をポーリングし、完成動画や投稿キットのパスを取得 |
| `cancel_job` | 実行中ジョブを安全に停止（完了済みクリップは保持） |

### `start_quick_output` の呼び出し例
```json
{
  "source": "/absolute/path/talk.mp4",
  "platforms": ["youtube_shorts", "tiktok"],
  "portrait_style": "podcast",
  "template": "editorial"
}
```

- **セキュリティ:** API キーは MCP 引数に含めません。デスクトップ設定または環境変数 `AUTOCLIP_API_KEY` を使用します。Ollama / LM Studio + Whisper による完全オフライン実行にも対応しています。
- 詳細仕様は [English Guide](MCP.en.md) または [CLI & MCP リファレンス (ZH)](CLI_AND_MCP.md) を参照してください。
