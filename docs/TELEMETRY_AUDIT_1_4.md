# AutoClip 1.4 PostHog / Sentry 审查与补齐方案

日期：2026-09-27；代码基线：`13d25ad2`。范围：已读取代码、执行离线验证，并只读检查现有 PostHog 看板和 Sentry 项目。以下矩阵保留审查时的缺口；本轮已按清单实施，当前契约、线上链接和验收限制见 [Studio 监控实施记录](analytics/STUDIO_MONITORING.md)。

## 结论

两套系统都需要更新，但不需要重装 SDK。PostHog 负责产品使用、流程转化与结果；Sentry 负责工程异常与定位。现有隐私开关、字段过滤、release/source maps 保留。首要任务是覆盖在用的 Studio 流程，而不是继续给不可达旧组件补事件。

## 覆盖矩阵

| 用户动作/阶段 | 现有覆盖 | 缺口与调整 |
| --- | --- | --- |
| 首页、确认页、编辑器 | 有页面事件 | `routeName` 把 `/import/:id` 和 `/project/:id/studio/:draftId` 都记作 `/other`；需新增固定路由名，不能发送真实 ID |
| 视频导入 | `studio_import_requested/accepted/request_failed` | 未区分文件/YouTube/B站、是否自带字幕；accepted 只是请求受理，不能算素材下载或制作成功 |
| 推荐完成 | `studio_screen_finished` | 只有 recommended/manual_fallback/failed；`mode=local` 的正常字幕推荐被算 manual_fallback。应分别保留 ai/local/manual/fallback，并记录有无可用字幕的有限枚举 |
| 修改方案、重新识别 | 未接 observeStudioOperation | `correctPlan/analyze` 无请求结果事件，也不重新登记观察；首次失败后的恢复漏报。补独立 attempt 生命周期，不能把旧 plan 当本次完成 |
| 确认制作 | `studio_confirm_*` | 没有字幕/视觉路线、content/highlight/promo 选择、自动/显式画幅等有限属性，无法判断新能力采用情况 |
| 制作结果 | `studio_production_finished` | 只有 completed/failed；高光成功但推广失败仍是整体 failed，无法统计部分成功。需后端提供本次分目标结果、候选数量及耗时，不从历史草稿总数推测 |
| 草稿打开、保存、复制 | 无业务事件 | 不知道用户是否进入编辑、修改或复用；记录动作结果即可，不记录每次按键、字幕、标题、提示词 |
| AI 文案改写 | 无业务事件 | 有额外模型调用但缺采用/失败口径；记录请求结果、耗时、固定错误分类，不记录输入输出正文 |
| 导出渲染 | `studio_export_*` 与 finished | 有最小闭环，但缺制作类型、画幅、字幕/模板有限枚举、渲染耗时和安全错误码 |
| 下载成片 | 只有 `studio_download_requested` | 桌面保存成功/失败均无事件。原生保存已有返回结果，可上报 saved/failed；浏览器普通链接只能报 requested，不能声称写盘成功 |
| 视觉配置与连接测试 | 未接旧 provider_test_* | `VisionSettings` 直接调用接口；应区分 text/vision 配置与连通结果，不发送 key、base_url 或任意自定义模型字符串 |
| 社交发布 | 保留旧发布/发布导出能力 | `publish_export` 是渲染，不是上传社交平台成功。需单独核验发布请求/平台受理/最终结果，Studio 来源仅用固定 source_type |

## 已确认的实现问题

1. **P1：Studio 后台异常监控缺口。** `backend/services/studio/jobs.py` 的 `_inspect/_render/_produce_selected` 捕获异常后保存失败状态；多处仅 warning，部分只写 JSON。没有显式 capture_exception。当前 Sentry logging 仅接 ERROR，before_send 又丢弃无异常栈的纯日志，不能依赖“记过日志就会上报”。这些异常不会冒泡到 FastAPI 全局异常处理器。需在异步任务的终态失败边界统一上报；同一次失败只报一次，避免共享分析被两个目标重复报告。
2. **P1：当前业务看板漏掉新链路。** 线上 `MjbdVzZb` 的 SQL 与 `docs/analytics/business_signals.sql` 一致，IN 列表没有 studio_*。该图即使持续收旧事件，也不能代表 1.4 使用情况。线上说明仍写“代码待发布验收”，需要更新为实际验收状态。
3. **P1：价值终点漏报。** `StudioDownloadLink.tsx` 在原生保存前报 requested，成功与 catch 分支没有结果事件。不能用点击数作为用户取得成片数。
4. **P2：当前统计存在误分类及信息不足。** 离线执行实际 WorkflowTracker，确认 local 推荐得到 manual_fallback、新页面得到 /other；制作只有整体失败，重试不登记。现有请求事件没有 attempt 关联，终态只有 outcome，不能可靠计算任务级转化/耗时。
5. **P2：直接增加 Sentry tags 不会生效。** 后端 before_send 仅保留已分类旧导入异常的 import_failure；前端只保留 app_locale。离线测试加入 phase/runtime 后，后端过滤结果无 tags。必须同步修改“有限枚举白名单”，而不是放行任意 context。
6. **P2：线上噪声与发布维度。** 已通过 Sentry 确认有 1.4.0 后端事件，但同时存在高频 ConnectionResetError。需先区分客户端正常断连与业务失败，不能直接全部屏蔽，也不能用它替代出片失败率。后端 environment=desktop/web，前端=production/development，跨端看板需要显式映射，后端另补受控构建环境标记。

## 建议事件与属性契约

新增/扩展固定命名的 `studio_rescreen_*`、`studio_draft_save_*`、`studio_draft_duplicate_*`、`studio_rewrite_*`、`studio_download_saved/failed`、`vision_provider_test_*`。延续现有 import/confirm/export 请求生命周期，明确 accepted 与 finished 的区别。页面打开可用规范化路由，无需重复加每个按钮点击。

有限属性：source_type、analysis_mode、goal 或固定目标组合、recommendation_mode、outcome、error_code、duration_ms、候选/草稿数量、aspect、subtitle_enabled、固定模板名、runtime、app_version、build_environment。

- 多目标制作结果按本次运行保存 `requested/succeeded/failed` 目标集合，整体采用 success/partial/failed；不改变已有用户内容或任务执行策略。
- 区分真实后端执行耗时与 UI 首次观察耗时，不用轮询间隔伪造精确执行时间。
- 新增重试要有本地 attempt 边界。现有外发策略不发送真实项目/计划/任务 ID；如需精确跨阶段任务漏斗，设计单独随机、短生命周期的遥测 ID 并明确契约，不能偷偷复用内部 ID。未具备可靠关联前，只提供事件数与设备数信号，不宣称精确端到端任务转化。
- 终态本地去重及传输 insert_id 需要一起设计，避免重启补观察、SDK 重送、重复导出受理造成重复计数。
- 采用独立的新版 Studio 契约标记，例如 `studio_schema_version=1`；原版缺此属性。更改 outcome 语义后不与旧事件直接混算，旧 1.3 图表保留为历史。

Sentry 建议保留经过枚举验证的 area/phase/analysis_mode/goal/error_code/runtime/build_environment。错误栈继续脱敏。配置缺失、用户取消、无合适候选与内部异常分开归组；正常“没有字幕”不应触发高优先级工程事故告警。为前端已捕获的保存/改写/原生下载故障补对应安全分类，但避免前后端对同一请求重复报错。

不新增视频/字幕/提示词正文、文件路径、来源 URL、密钥、模型回答、录屏或自动 DOM 捕获。不因使用视觉/LLM 能力就默认开启 AI 会话内容追踪。沿用独立统计/崩溃开关，关闭后进行中任务不得补报。

## 看板安排

1. 保留现有 1.3 历史基线；为 1.4 单独建 Studio 业务信号/漏斗视图，按 app_version、runtime、契约版本筛选。
2. 新能力采用：字幕/视觉，各制作类型，人工调整与改写。
3. 失败与恢复：初筛/制作/渲染/下载各阶段的固定错误分类及重试结果。
4. 价值终点：渲染完成与桌面保存完成分开；浏览器下载意图单列。发布上传另列。
5. Sentry 工程健康：版本回归、未预期后台异常、阶段分布；常见配置问题与高频连接噪声单列。
6. UI 关闭、观察列表 TTL/容量、统计关闭导致的缺失继续明示；没有收到事件不等于没有使用。

## 实施优先级与验收

**第一批：补可见性。** Studio 后台错误安全上报及白名单、桌面保存结果、重试登记、local 推荐分类和规范化路由；同时准备新版看板查询。

**第二批：补决策指标。** 分析路线/目标/本次部分成功、编辑/改写/视觉模型设置，以及社交发布链路。

**第三批：正式包验收。** 同一次生产构建，在明确测试标记下对照操作与两平台实际接收：正常导入、缺模型、网络失败、部分成功、重试、编辑、导出、原生保存成功/失败；重复轮询与重启只产生正确次数，隐私关闭后不收数。先验 macOS，Windows 真机覆盖仍需明确跟进。

实施进度：Studio 事件、后台错误捕获、Sentry 标签白名单及新版 PostHog 图表已更新；通过真实隔离应用验证两平台接收。未发布新包，未改通知规则，原生双平台正式包验收仍待完成，详见实施记录。
