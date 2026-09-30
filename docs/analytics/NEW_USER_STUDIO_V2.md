# 新用户与 Studio 数据闭环：本轮实现与验收

2026-09-30。基于 main `c26257521138ccbe2a0d65a2cc56963b9aa8b356`，实现分支 `codex/telemetry-new-user-studio`。本文件说明代码与可审查查询，不代表安装包已发布或线上看板已迁移。

## 从负责人要做的判断出发

| 要回答的问题 | 本轮数据来源 | 解释边界 |
|---|---|---|
| 用户是否看到配置引导，是否跳过，是否被导入门槛挡住？ | `setup_presented`、`setup_action`、`import_blocked` | 引导实际显示才报曝光；跳过、更多选项分开；曝光不能当安装数 |
| 配置卡在读取、模型发现、保存还是连接测试？ | `model_settings_load`、`model_discovery`、`provider_configuration_save`、`provider_connection_test` 的 requested/finished | placement 区分首页与设置；保存成功不表示模型可用；HTTP 200 且 success=false 记失败；发现区分 live/cache/catalog、preview、自动/手动 |
| 新设置页哪些分类被访问？ | `settings_section_viewed` | ai/publish/app/feedback；隐藏但保持挂载的组件加载不算分类访问 |
| 示例是否打开、真实显示、导出？ | `example_project_open_requested/finished`、`example_project_viewed`，下游 `material_origin=sample` | API 创建/复用成功与页面实际展示分开；项目卡直接进入也记录；示例不进入真实素材激活指标 |
| Studio 使用后是否交付？ | 导入、初筛、确认、制作、导出、原生保存、发布事件，以及 flow/attempt/artifact 标记 | 渲染完成、文件保存、平台发布分别呈现；浏览器只知道下载请求，不能认定落盘 |
| 自动取景是否有效、是否保留？ | `studio_auto_frame_*`、`studio_framing_install_*`，保存/导出上的构图摘要 | auto/manual/portrait_preset 分开；无检测结果是 no_detection；保留定义为 crop 布局下至少一段有自动轨迹且未手动调整，是采用代理指标，不是质量评分 |
| 失败恢复有没有误计、漏掉前一次？ | 后端 run_id + 精简 analysis_history；前端按运行观察 | 初筛不再消费制作失败；同方案重试、重新识别、服务重启后的旧终态可以恢复；仅限已登记且未过期的观察 |

## 事件契约和关联

保留公共 `schema_version=2`；Studio 新事件为 `studio_schema_version=2`；引导/模型设置事件为 `experience_schema_version=1`。原有 schema 1 历史数据不回填。旧 `api_key_configured` 不再由统一设置保存触发，示例的新请求/展示事件替代原来过早触发的 `example_project_opened`。

- `operation_id`：一次调用的请求与结果。连接测试、保存、模型发现分别独立。
- `presentation_id`：一次引导展示与跳过/更多选项动作。
- `flow_id`：客户端为项目分配的随机流程标记，串联制作与交付。不是跨设备用户 ID。
- `attempt_id`：已登记后台执行的随机观察标记。同方案重试拥有不同标记。
- `artifact_id`：同一导出作业的随机成片标记，用于渲染与原生保存去重关联。
- 后端内部 run_id、项目/作业 ID 只用于本地查找；新增 Studio/experience 事件不上传这些原始 ID。旧 legacy 事件仍保留历史契约，不宣称已全面迁移。

枚举、有限数字、布尔和符合格式的随机标记经过白名单；不上传 API Key、Base URL、模型名、文件名、字幕、提示词、模型回答和原始异常正文。Sentry 增补取景阶段的允许标签，保留原有脱敏与独立崩溃开关。

映射上限 500 项目、每项目 100 成片，35 日活动窗口；观察仍为 7 日/50 项。本地项目保留最新 100 次精简分析终态，和业务状态原子写入。关闭统计会立即清空前端映射与观察，阻止在途结果重新上报；不删除业务项目及其本地历史。关闭时存储写入失败也不会让当前进程继续采集。

## 查询和使用口径

- `new_user_experience.sql`：新手/设置阶段、placement、结果统计。
- `studio_business.sql`、`studio_adoption.sql`、`studio_results.sql`：迁移到 Studio 2，按 material_origin 分组。
- `studio_delivery.sql`：示例/真实/未知素材分别统计渲染、原生保存、平台完成；按设备、流程、成片去重。
- `sample_to_real.sql`：7–14 日前看过示例的设备，在随后 7 日内是否观察到真实素材渲染完成；成熟观察窗口，非安装队列，也不能说明因果。
- `studio_validation.sql`：验收环境与 production 隔离。

这些查询都是滚动 7 日的观察结果，不是完整安装队列漏斗。上线后需在 PostHog 验证语法与实际属性类型，再更新已有 insight；本轮没有改线上看板、发送生产测试事件或发布客户端。schema 1 与 2 应分版本并列，不能直接跨迁移日比较事件总量。

负责人优先看真实素材成功交付设备数、首次体验各环节失败构成、样例到真实素材使用的设备转换、按系统/版本拆分的故障。首次交付率与 D7 回访应在后续定义完整首次启动队列、观察窗口、统计同意覆盖后计算，不能拿本周事件相除冒充转化率。

## 尚不保证的事情

这是本次审查缺口的补齐，不是上一版设计里全部基础设施已上线。仍依赖 UI 观察和 SDK best-effort 发送，没有事务 outbox/服务端送达确认；关闭应用、超过容量/期限、网络断开可能造成未观察或未送达。被新输入取代的模型发现请求不会上报旧结果，未完成不等于失败。web 下载无落盘证据，排期/收件箱接受不等于发布成功。尚未增加成片质量问卷、完整增长归因或实际内容评分。

## 验证

离线回归覆盖真实模型设置 hook（保存与测试分离、200 负结果、过期模型发现）、存储失败时关闭统计、白名单脱敏、示例流程/成片关联、原生保存与浏览器请求区别、同方案重试、旧运行恢复、后端重启终态保留与去重。前端全量测试、类型/静态检查及构建，以及 Studio、示例、取景、Sentry 后端相关测试作为交付门槛。没有付费模型调用、正式桌面包实机验收或线上收数验收。

最终结果：前端全量 **167/167**、后端相关 **124/124** 通过；typecheck、lint、关闭 Sentry 上传的生产构建与 diff 空白检查通过。构建保留既有大包体积提示；第一次构建自动上传 Sentry 调试文件因 DNS 失败，随后关闭上传重新构建成功。SQL 尚未在在线 PostHog 执行验证。

## 看板落地更新（2026-09-30）

用户确认后已建立新版 PostHog 看板及专用 Sentry 看板，查询在线执行与保存已验证；[入口、查询备份与维护流程](dashboards-20260930/README.md)。前文“尚未建立/未在线验证”是本轮代码交付时状态，以本节后续进展为准。客户端尚未发布，新契约端到端收数仍待验证。
