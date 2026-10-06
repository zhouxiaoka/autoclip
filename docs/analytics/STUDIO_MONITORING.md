# Studio 1.4 监控契约与验收

> 历史验收记录。2026-09-30 的新增实现使用 Studio schema 2，契约、关联标记和本地 SQL 迁移见 [新版说明](NEW_USER_STUDIO_V2.md)。以下 schema 1 与线上看板描述保留为历史记录，不能视为本轮已发布或线上看板已更新。

2026-09-27，分支 `codex/recent-feedback-fixes`。代码已实施，尚未合入或发布；已安装的 1.4.0 不会自动获得这些改动。

## PostHog

- 新看板：[1.4 Studio 使用与交付](https://us.posthog.com/project/450605/dashboard/2140564)。
- [业务信号](https://us.posthog.com/project/450605/insights/AnApzd81)：新契约、production；旧 1.3 图表数据不覆盖；旧看板说明已链接新看板并澄清历史“代码待发布”字样。
- [来源与能力采用](https://us.posthog.com/project/450605/insights/Tiw4nBRZ)：文件/链接来源、字幕/视觉路线、制作目标与推荐模式。
- [结果与耗时](https://us.posthog.com/project/450605/insights/zbfS3Va8)：渲染/保存/发布结果、每次制作产出和执行耗时。
- [验收收数](https://us.posthog.com/project/450605/insights/nsKnzRm4)：validation 单列，不能加入生产转化率。
- 同目录 SQL 为可审查的查询来源。滚动 7 日；SQL 固定日期范围，不受看板日期覆盖器影响。

所有新增事件保留 `schema_version=2`，另带 `studio_schema_version=1`。`app_version` 来自构建版本，`analytics_environment` 区分 production/development/validation。只有显式 `VITE_TELEMETRY_VALIDATION=true` 的验收进程才使用 validation。

| 事件 | 语义 |
| --- | --- |
| `studio_import_*` | 导入请求、受理、请求失败；固定来源与是否自带字幕 |
| `studio_plan_update_*` / `studio_rescreen_*` | 修改方案或重新识别，并替换该项目本地观察记录 |
| `studio_confirm_*` | 确认制作；记录分析路线、目标布尔值、画幅 |
| `studio_screen_finished` | 初筛终态；local/ai 为 recommended，manual/fallback 分开；旧 plan 不算正在重试的完成；复用页面快照避免快速确认漏报，旧在途响应不能完成新 attempt |
| `studio_production_finished` | completed/partial/failed，本次 requested/succeeded/failed 目标、结果数量、后端耗时 |
| `studio_draft_create/save/duplicate_*` | 用户显式编辑动作；不记录按键、字幕、标题或镜头正文 |
| `studio_rewrite_*` | 改写接口结果和请求耗时；不上传提示词/模型回答 |
| `studio_export_*` / `studio_export_finished` | 导出受理与渲染终态分开；画幅、固定模板、字幕开关和渲染耗时 |
| `studio_download_requested/saved/failed` | web 只有 requested；native 只有实际保存非空文件成功才 saved |
| `vision_provider_save/test_*` | 视觉设置保存和测试结果；不上传模型名、地址、key |
| `studio_analysis_preferences_*` | 字幕/视觉偏好及快速视觉判断开关 |
| `social_publish_*` / `social_publish_finished` | 发布渠道受理与平台结果分开；固定 source_type=studio/legacy；scheduled/inbox/unknown 不算 completed |

`*` 表示 requested / accepted / request_failed。同步保存/改写/测试的 accepted 表示接口成功返回；导入/确认/导出的 accepted 只表示后台受理。`social_publish_finished` 每个网关在当前发布页面的观察期只报一次；关页后不做后台补报，排期之后是否真的发出需看平台记录。

页面路由仅发送 `/import/:id`、`/project/:id/studio/:draftId`、`/project/:id/publish/:clipId` 等固定模板。所有 Studio 属性通过枚举/数字/布尔白名单。项目、草稿、计划、作业 ID 留在本地；终态 `$insert_id` 是独立随机观察 token，保持重启去重，不能关联内部 ID，也不能用于跨阶段精确任务漏斗。同一不可变导出作业重复受理不重复计终态。

制作 `result_count` 仅为本次内容片段/草稿产出数，不是历史草稿数或已渲染文件数。`duration_ms` 为后台执行耗时，不含排队；请求事件另用 `request_duration_ms`。部分失败保留原有后端 `status=failed`，新增 `outcome=partial`，避免改变产品恢复流程。

观察列表仍受 UI 在线、7 日 TTL、50 项容量和隐私选择约束。新契约没有数据不能推断无人使用，也不能回填旧版本的缺失字段。

## Sentry

捕获边界覆盖 Studio 初筛、快速视觉推荐降级、制作、渲染、任务提交、文案改写和视觉连接测试；原生保存故障由前端上报。HTTP 请求的工程异常由后端负责，前端不重复上报同一次保存/改写请求。

保留固定标签 area=studio、phase、analysis_mode、goal、error_code、runtime、app_mode、build_environment。后端保留 desktop/web 的 environment，桌面启动器显式注入 production/development 的 build_environment，其他部署可设置 `AUTOCLIP_BUILD_ENVIRONMENT`，未设置时 unknown。前端 environment 延续 production/development。

1.5.2 候选的告警补充修复增加后端 `pipeline_stage` 标签，只允许 INGEST、SUBTITLE、ANALYZE、HIGHLIGHT、EXPORT、DONE。内容任务返回有阶段但没有错误码的结构化失败时保留该阶段；仍按原有异常规则上报，不隐藏未知故障。大纲模型请求失败使用已有的受控失败码，无法解析的回答归为 invalid_response；不增加请求重放。快速视觉推荐的抽帧进程失败、超时或文件错误会保留 screening 告警并降级到字幕方案，不能阻止导入。此补充尚未发布，已存在的 1.5.1 安装包不会自动获得这些改动。

未公开 1.5.4 的补充修复把本地 `subprocess.TimeoutExpired` 归为已有 `timeout` 代码，保留 `render`、`screening` 等实际阶段。模型服务和本地进程都可能超时，因此查询须同时按 `phase` 和 `error_code` 分组，不能把全部 timeout 计为供应商故障；原有枚举及 SQL 不变。普通 I/O/权限错误或仅含 timeout 字样的正文不改类。补充验收用真实本地子进程超时验证分类、渲染终态、原素材/已完成文件保留和重新生成，并核对统计终态只记录受控代码且重复观察去重；原用户的视频合并超时原因仍待确认，不能用这些边界回归宣称消除了全部渲染超时。

验证查询按 `release` 与 `build_environment` 筛选，并分组查看 `phase`、`error_code`、`pipeline_stage` 和事件数。生产事件可能没有 `telemetry_test` 标签，不能通过 `-telemetry_test:true` 查询为空认定没有生产故障；需用 `build_environment:production` 正向筛选。新增阶段只用于定位失败边界，不推断具体模型回答或素材内容。回归应覆盖抽帧失败不调用视觉服务、字幕降级、无错误码的阶段传递以及脱敏白名单，且用新安装包验证正常制作与失败后恢复。

ValueError 校验、素材缺失、视觉鉴权/限流/拒绝为 warning；其他工程异常保留 error。此分类依据异常类型及受控代码，不解析或上传异常正文。内容管线保留 llm_not_configured、字幕/转写、timeline_empty 等结构化失败码并按 warning 分类，不再包装成无分类的 RuntimeError。普通 ValueError 只能归为 validation；旧导入的 typed failure 分类继续保留。没有屏蔽 ConnectionResetError，也没有调整现有通知接收人或阈值。

- [Studio 工程异常](https://autoclip-ts.sentry.io/issues/views/226393/)
- [Studio 配置/素材警告](https://autoclip-ts.sentry.io/issues/views/226394/)
- [本轮验收异常](https://autoclip-ts.sentry.io/issues/PYTHON-FASTAPI-17)

`before_send` 继续去掉正文、变量、请求、上下文和面包屑，保留文件名/函数/行号。每次发送重新检查崩溃报告开关。共享分析错误在一次多目标制作中只显式捕获一次；监控异常不影响主操作。

## 验收及限制

使用独立 `/private/tmp` 数据目录、真实应用工厂与 Vite 页面。仅加载已有监控 DSN/公开项目 key，没有复制用户素材、模型配置或发布账号。用自制损坏 MP4 从真实首页导入：Sentry 收到 PYTHON-FASTAPI-17，栈可读为 jobs.py `_inspect` → planning.py `recommend`；area/phase/build_environment/telemetry_test 标签保留，正文脱敏。PostHog 的 validation 查询实际收到导入受理、修改方案、初筛失败/正常推荐、确认制作和制作失败事件；最终制作失败带 llm_not_configured。替换为自制纯色视频和测试字幕后，重新识别恢复到正常字幕推荐；确认制作后触发真实缺模型配置失败。最初该失败误归 RuntimeError，修复结构化错误码传递后再验，Sentry 收到 [PYTHON-FASTAPI-19](https://autoclip-ts.sentry.io/issues/PYTHON-FASTAPI-19)，warning、phase=production、error_code=llm_not_configured。中间的 PYTHON-FASTAPI-18 为测试样本，两个保存视图均排除测试标记。

自动化验证：全量后端 619 项通过；最后目标计数顺序调整另跑相关 58 项通过。前端 136 项通过，typecheck/lint/build 通过。构建仍有原有大 chunk 提示。

没有发布新安装包。原生桌面保存已验证代码与回归桩，未在本轮重打 macOS/Windows 正式包；多目标部分成功、隐私关闭与重复观察通过离线回归。未向真实社交账号投稿，也未进行付费模型验收。Sentry 页面首次加载报错，重试后恢复；已保存工程异常与配置/素材警告两个 Issue View，排除 telemetry_test=true。未创建通知规则。

自动制作在生成任何版本之前失败时，结果页的「重试」重新使用该项目已保存的导入选项和原素材；已有版本失败继续使用单条重试。恢复尝试沿用 flow_id，但重新登记 studio_generation_finished 的 attempt_id，终态按尝试去重。验收必须先看到真实失败码，再修正前置条件、从页面重试成功，并在 validation 查询中看到同一 flow 的失败与成功；不能把两个事件计成两个独立流程。
