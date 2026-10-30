# F5: 导入区常驻就绪状态行 — UI 截图

Fixture HTML：`frontend/f5-shots/index.html`（chrome headless 截图）。

| 文件 | 场景 |
|------|------|
| `01-all-green.png` | 全绿：「模型 ✓ deepseek-chat · 转写 ✓ 本地 small · 画面 — 未启用 · FFmpeg ✓」 |
| `02-trial-warn.png` | F2 试跑失败：模型项附「⚠ 未通过试跑」（与 F2 黄标语言一致） |
| `03-missing-asr-fix.png` | 转写 ✗ +「一键修复」（`install_whisper` / `useTranscriptionRecovery`） |

每项可点 → `repairDestination`（settings_ai / speech / vision）；✗ 另带一键修复按钮。
