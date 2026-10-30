# R3: 重试从断点继续 — UI 截图

| 文件 | 场景 |
|------|------|
| `resume_subtitle.png` | 已有 `input.srt` 且源指纹一致 → 主按钮「已有字幕，从分析开始」+ 次级「从头重做」 |
| `resume_step.png` | step1 产物 + stamp 一致、step2 缺失 → 「从第 2 步继续」 |
| `fresh.png` | 次级「从头重做」清缓存（`fresh: true`） |

`resumed_from` 写入 `generation` / `studio_generation_finished`：`none` | `subtitle` | `step1`…`step4`。
