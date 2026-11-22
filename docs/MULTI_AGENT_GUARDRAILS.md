# AutoClip 多 Agent 协作与发版防回归守卫规范

> 适用范围：所有面向 `integration/*`、`main` 及 release 分支的功能开发、缺陷修复与多 Agent 并行协作。

## 1. 单次发版体量与隔离原则

1. **常规版本控制改动体量**：每个常规发布周期尽量控制在 **20–30 个核心业务文件**以内，避免在一个 RC 分支里并行堆入 5 条以上大型重构线，导致单测局部通过但跨模块契约断链。
2. **大型新能力必须隔离**：跨周大功能（如 `obs-post-stream`）使用独立分支或显式 Feature Flag 隔离，禁止在 RC 止血/验收阶段混入。
3. **跨层改动必须同 PR 闭环**：
   - 修改埋点事件时，同步更新 producer、[event_inventory.json](analytics/event_inventory.json)、[event_catalog.json](analytics/event_catalog.json)、`backend/core/event_catalog.json` 以及对应 HogQL 查询；
   - 修改或新增 Tauri 命令时，前端 `invoke('...')` 与 `src-tauri/src/lib.rs` 的 `generate_handler![...]` 必须同 PR 对齐；
   - 修改任何面向用户文案时，同步更新全部 8 份语言包（`zh / en / ja / ko / fr / es / pt / ru`）。

## 2. 自动化防回归守卫（`scripts/ci_guards.py` + `scripts/quality_gate.py`）

除既有审查与错误码门禁外，以下两项跨层守卫已接入 `ci_guards`（阻断项）：

- **`tauri_invoke_contracts()`**：静态扫描 `frontend/src/` 下全部 `invoke('...')` 调用，强制要求目标命令已在 `src-tauri/src/lib.rs` 的 `generate_handler![...]` 注册，彻底杜绝按钮点击调用不存在命令的问题。
- **`orphaned_ui_components()`**：扫描 `frontend/src/features/studio/*.tsx` 与 `frontend/src/features/settings/*.tsx`，阻断新增任何 0 引用的孤立组件文件（防止类似重构时将失败恢复操作组件孤立掉的回归）。

## 3. 四条不可绕过的「用户黄金旅程」端到端回归套件

以下 4 条端到端回归接入 `quality_gate.py`（`backend_tests` + `redline_frontend` + `frontend_test`），任何 PR 不得跳过或弱化：

1. **黄金旅程 1 — 零配置开箱与思考模型容错**：全新空配置 → 配 Key（含思考/推理模型及 `auto` 模式下视觉探测失败降级）→ 保存成功 → 首页直接可导入（绝不落入 `no_model` 死路）。
2. **黄金旅程 2 — 分享文案与风控 Cookie 恢复**：粘贴 B 站带标题分享文案或受限 YouTube 链接 → 命中 `source_blocked` → `HashRouter` 下浏览器 Cookie 恢复 UI 正常弹出并可继续导入。
3. **黄金旅程 3 — 无字幕转写防假超时与竖屏一致性**：无字幕视频触发 Whisper 下载 → 进度持续推进不误触发前端 10 分钟超时 → 生成多条竖屏成片（含备选按需生成）全部保持 `9:16` 构图一致性。
4. **黄金旅程 4 — 失败卡全状态可恢复矩阵**：覆盖 `insufficient_quota`、`model_not_found`、`preservedCount > 0`、`generation.status === 'failed'`，在真实 `StudioResults` 与 `ProjectCard` 渲染输出上断言对应恢复按钮存在且不进入无限重试死循环。

对应测试文件：
- 后端：`backend/tests/test_golden_journeys.py`
- 前端：`frontend/tests/redline-golden-journeys.test.cjs`

## 4. 发版前外部生产依赖必核清单

发版打 tag 前，必须由发布负责人逐项核对外部生产服务状态（不可仅依赖本地离线单测）：

- [ ] **诊断接收服务（`autoclip-diagnostics-api`）**：确认线上 Cloudflare Worker 已部署支持 1.5.9 仅传脱敏链接/元数据的新载荷协议，R2/D1 清理任务正常运转（见 [DIAGNOSTICS_UPLOAD.md](DIAGNOSTICS_UPLOAD.md)）。
- [ ] **PostHog 生产看板**：确认 [success_rate.sql](analytics/success_rate.sql)、[value_funnel.sql](analytics/value_funnel.sql)、[ux_results.sql](analytics/ux_results.sql) 的版本发布时间窗（`{release_1_5_9}`）与内部测试队列过滤（`{internal_cohort_id}`）已在生产看板同步更新。
- [ ] **推荐服务商可用性**：确认默认新手稳定推荐顺序（DeepSeek、阿里云百炼位于赞助商之前）与远端推广配置（若有）状态一致，无失效入口或内部占位提示文案泄露。
