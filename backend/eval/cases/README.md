每个 case 一个目录：

- `input.srt` — 合成或脱敏字幕
- `timeline.json` — 模拟 step2 LLM 输出（不要把用户视频提交上来）
- `expect.json` — 约束：`clips_min/max`、`duration_min/max`、`must_not_zero`、`coverage_min`

```bash
python -m backend.eval
```
