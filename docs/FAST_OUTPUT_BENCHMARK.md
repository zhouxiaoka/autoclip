# 快速出片回归测试集

每次优化切片、包装、渲染或成本，都用同一组真实素材对比：`benchmarks/fast_output/cases.json`（负责人 2026-10-01 选定；id 不改，新素材往后加）。

## 怎么跑

1. 用测试数据目录启动后端（不要用自己的真实数据目录），模型与语音识别按要测的配置设好：

   ```bash
   AUTOCLIP_APP_DIR=<dir> AUTOCLIP_DATA_DIR=<dir> DATABASE_URL=sqlite:///<dir>/autoclip.db \
     nice -n 15 python -m backend.main --port 18765
   ```

2. 跑测试集（逐条导入、等渲染完；YouTube 用 Chrome 的登录态下载）：

   ```bash
   python scripts/fast_output_benchmark.py --data-dir <dir>                       # 全部
   python scripts/fast_output_benchmark.py --data-dir <dir> --cases kojima-wired  # 指定几条
   python scripts/fast_output_benchmark.py --data-dir <dir> --baseline benchmarks/fast_output/reports/<上次>.json
   ```

3. 结果写在 `benchmarks/fast_output/reports/<时间>.json` 与 `.md`；带 `--baseline` 时表格里给出与上次的差值。

## 报告里有什么

| 字段 | 来源 |
|---|---|
| 各阶段用时（下载、语音识别、挑片、切点、取景、包装、文案、渲染） | 项目 `metadata/llm_usage.jsonl` 的 timing 记录 |
| 模型调用次数、tokens、估算费用（qwen-plus 价） | 同一文件的用量记录 |
| 片段数 → 自动出片数、备选数、失败数、片段时长 | Studio 状态 |
| 原片分辨率、字幕来源（作者字幕 / 语音识别）、是否有硬字幕及其语言、包装降级数 | Studio 状态 |
| 前几条标题与发布标题 | 用于人工抽查 |

## 人工检查清单（每条抽 2 支）

- 开头从问题或观点的第一句开始，结尾等到回答讲完、有停顿，不带进下一个问题。
- 原片有硬字幕时不重复加同语言字幕；外语受众有对应语言字幕；字幕与声音同步。
- 竖屏对着说话人，换人时跟着切；屏幕演示段（如 OpenAI DevDay）保留完整画面。
- 画面清晰（原片 ≥ 720p）；封面人脸不被标题遮挡，名牌是嘉宾；文案符合平台风格与长度。
- 片尾动画完整、声音不突兀。

## 素材特点（为什么选它们）

见 `cases.json` 里每条的 `traits` 与 `watch`：长访谈、短素材、双人对谈、主题演讲与屏幕演示、中文无字幕素材、硬字幕（中文 / 外语配英文）、只有自动字幕、曾经只下到 360p 的源。
