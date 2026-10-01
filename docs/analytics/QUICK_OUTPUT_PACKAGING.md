# 快速出片与模板包装：埋点补充说明

2026-09-30。分支 `worktree-project-diagnosis`，已合并 main `8968916b`（含 [新用户与 Studio 数据闭环](NEW_USER_STUDIO_V2.md)）。本文只说明代码，不代表已发布或线上看板已更新。

## 为什么要补

快速出片成为新的默认流程后：导入 → 自动理解 → 按平台自动派生版本 → 后端自动渲染，**没有“确认方案”这一步，也没有前端发起的导出**。沿用 main 的观察逻辑会出现：

| 旧观察 | 在自动出片下的表现 |
|---|---|
| `studio_screen_finished` | 只在 `awaiting_confirmation` 结束，自动出片永远不报；回到页面时若已渲染失败，会被误记为初筛失败 |
| `studio_production_finished` | 挂在确认方案上，自动出片不会登记 |
| `studio_export_*` | 版本由后端提交，前端没有导出请求 |
| `studio_auto_generation_finished`（上一版） | 仅在结果页开着且到达终态时上报；中途离开就没有终态 |

另外，新能力（平台模板、包装样式、说话人取景、包装降级、原片字幕、Shorts 截断）完全没有数据。

## 改动

| 事件 / 字段 | 语义 |
|---|---|
| `studio_screen_finished` + `outcome=auto_started` | 自动出片进入制作或渲染阶段即算初筛结束，不论之后成败；先于“失败”判断，避免误记 |
| `studio_generation_finished`（新，替代 `studio_auto_generation_finished`） | 导入时登记 `studio-generation` 观察，随 main 的观察持久化，生成到 `completed/partial/failed` 报一次；下次打开项目可补报 |
| 生成汇总计数 | `variant_count`、`completed_variant_count`、`failed_variant_count`、`skipped_variant_count`、`platform_count`、`interview_count`、`podcast_count`、`landscape_count`、`speaker_framed_count`、`packaging_fallback_count`、`trimmed_count`，布尔 `burned_captions`；`duration_ms` 由后端 `generation.created_at` → `finished_at` 计算，不用观察时刻 |
| 草稿保存/复制/改写/导出 | 增加 `template`、`packaging_style`、`tags_enabled`、`packaging_fallback`；`layout` 枚举增加 `window`；`auto_frame_retained` 同时认 `crop` 与 `window` |
| 成片下载（requested/saved/failed） | 成片卡下载带 `strategy_id`、`template`、`packaging_style`、`framing` |
| `studio_output_shared` / `studio_output_rated` | 带 main 的 `flow_id`、`material_origin` 上下文与上述版本枚举 |
| `studio_variant_produce_requested/accepted/request_failed`（新） | 用户点「生成这条」生成备选片段；带 `strategy_id` |
| `on_demand_variant_count`（生成汇总新增） | 只自动渲染评分最高的 10 条，其余为备选；该计数说明本次留了多少备选 |

后端配合：自动出片在制作/渲染/结束各阶段保留 `analysis.run_id`（main 的观察按 run 匹配）；生成终态写入 `generation.finished_at`；自动取景结果写入 `framing_source=auto`，使 main 的“自动取景被保留”指标覆盖自动出片。

## 隐私边界

新增字段全部是枚举、计数或布尔，经 `safeStudioProperties` 白名单：

- `template`: interview_zh / podcast_en / landscape / none
- `packaging_style`: classic / boxed / spotlight / pop / cinematic
- `framing`: speaker / full_frame / full_frame_pending / full_frame_captions
- `outcome` 新增 auto_started

不上传标题、字幕、译文、名牌人名、评论标签文字、高亮词、原视频标题或频道名。`frontend/tests/analytics-auto-generation.test.cjs` 覆盖：汇总计数、白名单丢弃标题与人名、自动出片初筛结局、生成终态只报一次。

## 负责人可以回答的问题

- 自动出片的完成、部分成功、失败比例，以及各平台模板占比。
- 说话人取景覆盖率（`speaker_framed_count / variant_count`）与包装降级率（`packaging_fallback_count`）。降级高说明文字模型不可用或返回不合格，需要看 Sentry。
- 哪些模板/样式的成片被下载、分享、评为“能直接用”。评分是低频抽样，只能看相对差异。
- 用户在 Studio 里切换样式、关闭评论标签的比例（草稿保存上的 `packaging_style`、`tags_enabled`）。

## 仍需上线后验证

新事件与字段需在 validation 环境实际收数，再在 PostHog 看板增加“快速出片”分组（`studio_generation_finished` 按 `outcome`，下载按 `template`/`packaging_style`）。schema 1、上一版 `studio_auto_generation_finished` 与本版不可跨版本合并比较。

2026-10-01 发版前补充：[客户端新增流程与实际交付复核](QUICK_OUTPUT_RELEASE_1_5.md)。
