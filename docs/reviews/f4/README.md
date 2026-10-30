# F4: URL 导入先 inspect 再下载 — UI 截图

Fixture-driven renders（`frontend/f4-shots`）使用真实 `UrlPreview` + studio CSS / Btn。

| 文件 | 场景 |
|------|------|
| `01-platform-subtitle.png` | 有平台字幕 → 「有平台字幕，不需要本地转写」+ 确认并开始下载 |
| `02-need-transcription-install.png` | 无字幕本地转写 + readiness 未就绪 → 「安装转写」在下载前 |
| `03-visual-no-audio.png` | 无音轨 → 「无音轨，只能按画面制作（需视觉模型）」 |

流程：粘贴 URL → `POST /studio/inspect-url`（yt-dlp skip_download）→ 预览卡 → 确认/3s 撤销后才 download；inspect 失败走 `browserCookieRecovery`。
