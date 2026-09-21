# AutoClip 业务分析 V2：实现与验收

更新：2026-09-21。状态：本地实现，尚未发布。新看板仅准备查询，不意味着新版已经收数。

## 1. 已取得的历史基线

[业务健康与埋点验收看板](https://us.posthog.com/project/450605/dashboard/2117451)；[固定历史基线](https://us.posthog.com/project/450605/insights/Pc5JOGDb)。保留原 My App Dashboard。

时间：北京时间 2026-08-22 00:00（含）至 2026-09-21 00:00（不含）。这些是匿名 distinct_id 数，并未排除开发、示例或重复安装，不等于精确人数。

| 旧事件 | 次数 | 匿名设备/存储身份数 |
| --- | ---: | ---: |
| app_opened | 1,484 | 721 |
| video_imported | 964 | 400 |
| app_installed | 703 | 703 |
| api_key_configured | 308 | 150 |
| clips_exported | 64 | 18 |
| processing_failed | 43 | 14 |

旧导出事件缺少发布导出等路径；导入事件在链接场景下仅表示受理。不能把 18/400 当作真实出片转化率，也不能从失败事件计算全局任务失败率。新旧口径不拼成连续增长曲线。

本次另已在近 7 日覆盖查询中观察到 `app_version=1.3.0` 的启动、导入、配置和旧导出事件，确认这个版本有上报记录；这不替代 V2 正式包验收。

## 2. 本次覆盖与实现

- `posthog.ts`：显式业务事件、schema/environment/runtime/entrypoint 标记、SDK 异常隔离、统计开关；关闭 DOM autocapture、性能自动采集和 pageleave，保留归一化的页面路由事件。没有开启录屏。
- `operations.ts`：统一请求与文件接收观测，不改变原有 API 成功/失败语义。空文件响应作为下载失败。
- `workflow.ts`：有界的本地任务观察列表与事件去重；最多 50 个项目/下载/导出观察项，保留 7 天，每项最多 2,000 个已发送事件 ID。满额或到期可能失去覆盖，不能视为全量审计日志。
- `observer.ts`：应用开启且统计开启时，每 15 秒静默检查通过 UI 提交的任务；顺序请求，每次 5 秒超时。已观察到终态的项目不再持续轮询，下一次 UI 重试重新登记。网络错误仅表示本次未观察到，不产生伪造的任务失败。
- `api.ts`：上传、B 站/YouTube 下载受理、开始/重试/重启步骤、模型连通测试、发布导出，以及切片/合集/发布文件下载全部接入新事件。
- `lifecycle.ts`：禁用时不再写入首次上报标志；为后续事件注册版本和环境。Mac 的 CPU 架构无法可靠从 UA 判断，显示 unknown。

后台没有新增对外发送通道，因此 UI 关闭后不实时上报。重新打开后可补观察本地仍存在、且在观察期内的任务；纯 CLI/MCP、未通过此 UI 登记的任务不计入本次覆盖。共享服务端上其他入口创建的同项目任务可能进入观察范围，不将该视图称为严格的个人处理归因。

旧事件保留原触发范围。`processing_failed` 不再携带原始异常文本，保留阶段和状态码。新业务事件不采集原视频 URL、字幕、文件名、用户提示词、密钥或原始异常。现有用户主动提交的反馈是独立流程，不受此事件字段定义替代。

## 3. 新事件口径

通用属性：`schema_version=2`、`analytics_environment=development|production`、`runtime=desktop|web`、`entrypoint=ui`；生命周期注册 `app_version/os/arch/app_locale`。早期初始化尚未获取版本的事件可能缺失版本，需要在覆盖看板中检查。

| 事件 | 准确定义 | 关键属性 |
| --- | --- | --- |
| import_requested / import_accepted / import_request_failed | 请求开始 / API 受理 / API 拒绝或请求失败 | operation_id、source_type、request_duration_ms、error_code |
| import_finished | 上传字节已被接收，或链接下载任务被观察到终态；不是转写或分析成功 | 上传 stage=upload_received；链接 import_id；project_id、outcome |
| processing_requested / processing_accepted / processing_request_failed | 用户发起开始、重试或步骤重启的请求 | project_id、operation_id、action、step |
| processing_task_observed | 首次观察到登记后新创建的 video_processing 类型任务 | project_id、task_id |
| processing_started | 观察到 running，或有实际 started_at；未观察到启动且无时间戳时不补造 | task_id、occurred_at、time_basis |
| processing_finished | 后端任务记录为 completed / failed / cancelled | task_id、outcome；真实时间戳存在时才有 duration_ms |
| publish_export_requested / publish_export_accepted / publish_export_request_failed | 发布导出请求生命周期 | operation_id、project_id、preset、subtitles、title_card |
| publish_export_finished | 已登记的导出 job 被观察到 completed / failed | export_id、project_id、outcome |
| media_download_requested / media_download_accepted / media_download_request_failed | 文件请求、非空 Blob 响应、请求/空响应失败 | operation_id、project_id、artifact_type、error_code |
| media_download_received | 下载请求取得非空 Blob | 同上、size_bytes；发布导出额外 export_id |
| provider_test_requested / provider_test_accepted / provider_test_request_failed | 模型连通测试的 HTTP 请求结果 | provider、operation_id |
| provider_test_finished | HTTP 响应内的模型连通测试结果 | provider、outcome=success|failed |

**三种成功必须分开：** 后端任务完成、文件字节收到、用户认为片段可用。当前 `completed` 不证明生成了有效片段；`media_download_received` 不证明浏览器写盘成功、可解码或用户满意。未添加虚假的 `export_saved`。

`artifact_type` 为 clip、collection、publish_clip、original。价值代理指标只计前三类，原片下载排除。普通浏览器直接访问文件 URL、播放器自带下载不在 API 埋点覆盖内。

任务统计单位是后端 task_id，不是项目数，也不是完整业务 run；单项目可有多个任务。只观察登记时间之后创建的 video_processing 任务，不扫描历史完成项目。需要设备与后端时钟基本一致。旧 worker 缺失的 started_at/completed_at 显示未知；重用旧 task_id 的流程需另行增加 attempt 标识，目前不计作可靠的新增尝试。

## 4. 去重、隐私与离线边界

- 任务观察事件以任务 ID + 事件类型去重，并设置稳定 `$insert_id`；看板按 task_id 去重。请求和下载按 operation_id 区分新尝试。
- 关闭或重新开启统计清空观察列表，使进行中的旧请求失效，不因再开启而回放关闭期间的操作。
- PostHog SDK 接受入队不等于服务器收到了事件。离线发送依赖 SDK，当前没有新增可确认送达的持久化 outbox；突然退出可能丢事件。需要在正式包收数验收和覆盖看板中检查，不承诺严格一次送达。
- 发布导出的后端 job 目前存在内存中。应用后端重启后无法恢复的 job 不伪造成功或失败；端到端可靠性下一步需持久化 job/attempt 状态。
- 本地存储异常不阻塞剪辑。重新安装或清除存储会改变匿名身份、去重状态和首次启动含义。
- 开发环境事件仍可用于调试，但业务看板必须筛选 production；正式构建的手工测试须使用单独测试项目或明确测试标识，不能仅依赖 production 字段排除。

## 5. 看板与周复盘

第一张看板将历史基线、事件覆盖、V2 业务信号放在一起，先确保数据可信，再拆更多图表。

已保存分析：[近 7 日版本/环境覆盖](https://us.posthog.com/project/450605/insights/9WsQqENK)、[V2 近 7 日业务信号](https://us.posthog.com/project/450605/insights/MjbdVzZb)。对应查询保存在 `docs/analytics/coverage.sql` 和 `docs/analytics/business_signals.sql`。V2 查询本次成功执行且为 0 行，这是代码未发布阶段的预期状态。

- **覆盖：** 最近 7 天按事件、schema、环境、版本计数，检查空字段、旧口径和新口径是否混用。
- **业务信号：** 最近 7 天 V2 production 的请求失败、任务完成/失败/取消、非空文件收到设备数。观察事件使用到达时间，延迟补观察可能跨日；不能等同于真实执行日。
- **后续留存：** 以首次 `media_download_received` 为起点，另一个自然日再次收到有效类型文件。7 日窗口未满的 cohort 不纳入分母；先看计数与用户反馈。
- **质量：** 当前尚需人工抽查。下一批加入用户主动的可用/需调整/不可用反馈，不能用模型评分代替。

每周 30 分钟只选择一个产品问题：最大阻塞是否来自模型配置、素材下载、后台处理，还是结果使用？观察修复前后同版本口径的设备与任务数，不用 Star 替代。

## 6. 验证与发布验收

本地检查：

```sh
cd frontend
node --test tests/analytics.test.cjs
npm run typecheck
npm run lint
npm run build
```

测试覆盖重复轮询、重启恢复、历史任务排除、新 task 重试、取消和缺失时间戳、开关与进行中请求、SDK/存储异常、队列容量、空文件、隐私字段，以及真实 API 封装中的五种文件下载调用路径。

本次本地结果：10 项测试、typecheck、lint、build 均通过。构建仍提示已有的大包体与 Tauri 动静态混用警告。上述测试不连接真实 PostHog，也未进行新安装包的真机收数验收。

`.github/workflows/ci.yml` 已加入同一组 analytics contract tests，后续提交会随前端检查执行；本次未推送或触发远端 CI。

正式发布前仍需：

1. 与当前线上 1.3 分支及工作区其他未提交工作整合；本地 checkout 落后，不能直接打包替代已发布版本。
2. Windows/Mac 发布包分别执行模型测试、上传、链接导入、正常处理、模型失败、重试、发布导出和下载。
3. 在独立测试项目或明确验收标识下，对照本地动作、后端状态与 PostHog 收到事件；重复轮询只产生一个终态，关闭统计不收数。
4. 确认生产包有上报配置；业务看板再开始观察 7—14 天新口径基线。不能用本次离线单元测试宣称线上已接通。

下一批优先项：持久化统一 run/attempt 与导出 job、可确认发送的 outbox（统一隐私开关）、发布验证标识、可用性反馈，再扩展纯 CLI/MCP 覆盖与官网来源分析。暂不引入新数据仓库。
