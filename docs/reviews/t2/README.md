# T2: 首次素材建议只处理前 30 分钟 — UI 截图

静态 fixture（`/tmp/t2-shots` → chrome headless）对照 UrlPreview / StudioResults 主路径。

| 文件 | 场景 |
|------|------|
| `01-first-window-prompt.png` | 无成功历史 + 时长 > 30 min → 提示「第一次建议先试 30 分钟以内…」+ 「只处理前 30 分钟」/「处理全片」 |
| `02-post-success-tip.png` | `plan.overrides.source_window` 出片成功后顶提示「配置没问题，可以重新导入全片」 |

`source_window: {start:0,end:1800}` 写入 FormData → ImportOptions → plan.overrides；转写 ffmpeg `-t` 切临时音频，SRT / drafts 按窗口过滤；成片时间戳仍对应原片。
