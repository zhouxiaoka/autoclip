# AutoClip 数据分析体系系统评审

日期：2026-09-29。代码基线：本地 `b7f7e11b`，分支 `feat/settings-ai-unified`；工作区存在其他任务的未提交修改。本次只新增评审材料，没有修改产品代码、线上看板或通知规则。

## 结论

现有体系已经具备认真设计过的隐私保护、事件分层、部分去重、错误分类和自动化测试。问题不在“完全没有统计”，而在于它目前主要是一套**使用信号和工程故障监测系统**，还不足以支持“新用户在哪里流失、什么改动改善首次出片、用户是否持续得到价值”的产品决策。

“打补丁感”主要来自三处：旧流程与 Studio 各自形成契约；结果依赖前端观察而非持久化执行记录；指标定义、线上发布状态、看板与文档没有统一生命周期。继续零散添加事件会扩大这些差异。

最先需要回答的业务问题：在可观测的新设备中，有多少在规定时间内用自己的素材成功拿到第一条成片；失败发生在哪一步；成功后是否再次出片。Star、赞助询问和传播数据作为独立结果指标，不能代替这个闭环。

## 范围与验证边界

- 阅读：前端 analytics 全链路、Studio API/下载/发布接入、设置与生命周期、后端 Sentry 与 Studio 状态写入、SQL、反馈周报和已有监控文档。
- 线上只读：PostHog Studio 看板；Sentry 最近 7 天按项目/环境/版本和 Issue 聚合；一个高频 Issue 的栈。
- 运行：36 项前端相关测试通过；三个独立离线复现成立。后端 Sentry 测试未运行成功，因为当前 `.venv` 没有 pytest；没有安装依赖或套用旧文档的通过数。
- 未验证：所有历史 PostHog 看板、服务端保留期配置、告警投递、各正式安装包的真实成功出片链路、CLI/MCP 实际使用量。没有用本地源码推断已发布版本一定包含这些能力。

## 线上证据

1. [Studio 看板](https://us.posthog.com/project/450605/dashboard/2140564) 的“新契约·生产”业务图显示无匹配行；validation 图有导入、确认、筛选和制作失败等 10 组记录。看板说明仍写“2026-09-27…尚未发布”。这只能证明该查询下未收得生产记录，不能证明无人使用 Studio，也不能单凭这一点确定是未发布、无流量还是埋点故障。
2. Sentry 最近 7 天：后端多个版本的错误事件使用 `desktop` 环境；前端环境采用 production/development，验收后端使用 web。前后端同名 environment 的含义确实不同。
3. [PYTHON-FASTAPI-4](https://autoclip-ts.sentry.io/issues/PYTHON-FASTAPI-4) 抽样栈来自 `get_processing_status` → 配置目录创建失败。它说明查询状态也会反复触发错误；没有执行关联信息时，不能把事件次数当作制作失败次数。Issue 展示的 Users Impacted=0 也不能当作零影响，因为没有可靠的用户身份分母。

上述为查询时点快照，滚动窗口再次查询会变化。Sentry [聚合查询入口](https://autoclip-ts.sentry.io/explore/discover/homepage/?dataset=errors&queryDataset=error-events&field=project&field=environment&field=release&field=count%28%29&sort=-count%28%29&statsPeriod=7d&mode=aggregate&yAxis=count%28%29)。不在本报告保存反馈正文、邮箱、用户地理信息、原始事件标识或凭据。

## 发现与优先级

### F1 · P1：Studio 无法串起同一次导入、制作、导出和交付

证据：`frontend/src/analytics/studio.ts:7` 的请求事件没有 operation ID；`workflow.ts:8` 的白名单不接收执行关联字段；`workflow.ts:128` 只有每个 watch 的去重 token；`features/studio/api.ts:18` 开始的各阶段独立登记。

旧流程有 operation/project/task/export 标识，Studio 刻意采用仅聚合字段的隐私契约。设备 ID 可支持粗略的设备行为漏斗，但同一设备同时处理两个视频、重试、反复导出时，不能证明各步骤属于同一条流程。`$insert_id` 的用途是去重，不是跨阶段业务关联。

影响：不能可靠计算来源→成片转化、每次制作成功率、重试挽回率；简单用 finished/accepted 或两类设备数相除会产生错误解释。

建议：定义不包含内容的随机 `flow_id`、`attempt_id`、`operation_id`、`artifact_id`，在本地映射内部 ID。一次用户目标保留 flow，重试新建 attempt，重复轮询复用 event ID。同一成片重复保存不增加成片数。若扩展当前对外契约，必须同步字段白名单、隐私说明、测试和版本；不能偷偷上传内部项目 ID 或素材指纹。

### F2 · P1：结果来自可变快照，存在阶段误归因与终态丢失

证据：`workflow.ts:144–154`；`backend/services/studio/jobs.py:248,288,388`。

- 待结算的 studio-screen watch 只看到 analysis.status=failed 就上报筛选失败，不校验失败属于 screening 还是 production。离线复现：给它 production/llm_not_configured 的失败快照，得到 studio_screen_finished/failed。
- production watch 必须匹配当前 plan.id。如果旧制作终态尚未被观察，新一轮筛选已经替换 plan，旧 watch 无法恢复结果。离线复现中它一直未结算。
- 已有 `observeStudioWorkspace` 能在常规页面读取时及时观察结果，并防止旧响应结算新 watch。这是有效保护，但不是不可变执行历史，不能覆盖错过快照、其他客户端推进等情况。

建议：短期校验 phase 与 attempt；长期让后端为每次执行保留不可变的终态摘要。前端读取摘要补报，不从“当前页面状态”猜历史。缺失结果标为 unknown，不能补成 failed 或 completed。

### F3 · P1：关闭统计在“存储可读、不可写”时存在应用层失效

证据：`posthog.ts:49–55,102–115`。setAnalyticsEnabled 写入内存 override，但 isAnalyticsEnabled 仅在读取抛错时使用它。

复现：getItem 返回旧值/null，setItem 因配额等原因失败；执行 setAnalyticsEnabled(false) 后 isAnalyticsEnabled() 仍为 true。工作流观察和应用层采集门禁因此没有可靠关闭。

范围：已验证应用层判断错误；没有证明真实 SDK 一定继续联网。SDK 的 opt_out_capturing 是独立防线，不能以桩测试断言真实数据泄漏。

建议：与 `desktop/sentry.ts:13` 一致，优先使用内存 override。覆盖“读写均失败”“仅写失败”“旧值为开启/关闭”“切换时请求仍在途”四类测试。

### F4 · P1：可观测覆盖率未知，不能把未观察到当作没有发生

证据：`observer.ts:15` 仅观察 UI 登记的工作；轮询间隔 15 秒、逐个请求、每请求最多 5 秒；`workflow.ts:5,96` 最多 50 条、保留 7 天、静默移除；`workflow.ts:128` 在 SDK 接受 capture 后即记 seen。

关窗、未同意统计、未登记的 CLI/MCP 操作、观察过期与服务不可达都可能形成缺口。localStorage 保存的是 watch 和 seen，不是已被远端确认的业务结果日志。SDK 接受入队不等于 PostHog 已收到。现有文档已明确这一限制，不能把它包装成新的网络可靠性保证。

建议：先建立“已登记且成熟的 attempt 中，有终态/仍进行/未知”的完整性看板。再增加有界本地结果日志和补报机制，保证幂等与关闭统计后不追溯补传。桌面本地后端、浏览器远程后端的授权范围需分开设计，不能为了补齐 CLI 数据默认打开后端独立采集。

### F5 · P1：激活、成功交付、出片质量缺少独立定义

证据：`lifecycle.ts:103` app_installed 实际是该存储空间首次观测启动；`studio.ts:31–57` 浏览器只有下载意图，原生才有 saved；`docs/analytics/studio_results.sql` 统计事件/设备和执行平均耗时。

没有统一的首次出片 cohort、成熟窗口、示例素材排除、再次出片口径和质量验收。旧流程收到非空 Blob、Studio 渲染完成、原生保存成功、浏览器点击下载，是四种不同证据。制作出候选 result_count 也不等于用户最终接受的成片数。

建议：将“成功生成”“确认交付”“用户认可”分开；浏览器保存未知不要合并到桌面保存成功率。以设备作为当前可观测单位，明确不是自然人。质量先用固定样本人工评审与少量主动反馈，不急着把自动评分当真实质量。

### F6 · P2：诊断系统与产品分析的环境、维度、分母不一致

证据：`desktop/sentry.ts:44,57`、`backend/core/sentry_setup.py:179`、`analytics/lifecycle.ts:89`、`analytics/feedbackDraft.ts:78`。

- Sentry 前端 environment=production/development，后端=desktop/web；后端额外有 build_environment，但旧事件/非 Studio 保留情况需要分别看。
- 前端 Sentry 白名单没有 os/arch/runtime/validation 标记，产品分析的 OS/arch 又主要依赖生命周期异步注册。无法自然拼成“某版本 Windows 的制作失败率”。
- 反馈主动发送走独立 capture，字段中没有统一 schema/environment；不能与业务事件使用同一覆盖率查询后，把缺 schema 的反馈直接判为坏埋点。
- 请求错误通常降为 http_XXX/unknown，缺少稳定业务分类；后端已有较细的受控失败码，但两端契约没有统一。

建议：统一受控 envelope：环境、运行端、入口、版本、系统、契约版本；保留旧字段迁移映射。PostHog 衡量业务结果，Sentry 排查工程异常，反馈收件箱处理主动文字。失败率分母来自执行契约，不来自 Sentry count。跨系统排错如需关联，只用受控 attempt 标识，不发送原始正文。

### F7 · P2：报表偏“事件盘点”，缺少面向决策的指标层

证据：`docs/analytics/studio_business.sql`、`studio_adoption.sql`、`studio_results.sql` 按最近 7 天聚合，结果 LIMIT 100；后者仅平均执行时长。`scripts/weekly_digest.py:154` 是反馈摘要，最多读取 300 条，并非产品经营周报。

影响：平均值不能解释尾部等待；执行耗时不包括排队及用户停留；到达时间不等于实际发生时间；新版本渗透、未知结果占比、首次成功、复用没有连成固定复盘入口。截断表格也不适合人工相加当全量指标。

建议：先做三张决策看板：激活与复用、任务可靠性、埋点健康。每项显示样本量、契约/版本范围、分母、成熟窗口、未知数和采集时间。材料到成片耗时与后台执行耗时分别看 p50/p90，暂不扩展成庞大 BI 系统。

### F8 · P2：发布、文档、验证缺少同一份验收清单

证据：`docs/ANALYTICS.md`、`ANALYTICS_V2.md`、`TELEMETRY_AUDIT_1_4.md`、`analytics/STUDIO_MONITORING.md` 保留不同历史阶段与发布状态；线上仍有“尚未发布”说明。现有 CI 有相关测试，且本次 36 项通过，但这不等于正式包生产收数验收通过。

建议：建立单一索引，历史报告保留并标记基线，不继续写互相冲突的当前状态。每次发布登记 commit→安装包版本→契约版本→预期事件→实际收数→看板入口；验收至少包含成功出片、受控失败、重试、重启恢复、隐私关闭。数据保留期限在文档中已写，但后台配置核验仍未完成；本次也未核实，不做合规结论。

## 建议采用的最小指标字典

以下是待实施口径，不能用当前历史数据硬算。

| 指标 | 定义与边界 | 要回答的问题 |
|---|---|---|
| 首次真实交付设备数 | 首次产生自己素材的已确认交付；按设备去重、排除示例/验收 | 项目每周实际帮助了多少新增使用者 |
| 7 日激活率 | 可观测首次启动 cohort 中，7 日内首次真实交付的设备占比；只纳入满 7 日 cohort | 首次使用体验是否改善 |
| 首次尝试成功率 | 每个 flow 第一次 attempt 成功生成的占比；partial、unknown 分列 | 是否需要靠重试才能完成 |
| 重试挽回率 | 首次失败且发起重试的 flow 中最终成功的占比；固定观察窗口 | 重试机制有没有价值 |
| 任务终态覆盖率 | 成熟 accepted attempts 中有明确终态的占比；不能把运行中算丢失 | 数据是否足以支持成功率判断 |
| 首次交付耗时 | 从首次启动到首次真实交付的 p50/p90；另列导入到交付耗时 | 配置、处理、下载哪个环节耗时 |
| 7 日再次出片率 | 首次真实交付后 7 日内，不同 flow 再次交付的设备占比；成熟 cohort | 得到价值后是否回来使用 |
| 出片质量 | 固定素材集的边界完整性、字幕准确、构图、声音、节奏；配合自愿“可直接发布/需修改/不可用”反馈 | 输出是否足够好，而不只是生成了文件 |
| 赞助入口效果 | 点击、配置保存、连接成功、使用该受控 Provider 成功出片分别计数 | 入口是否帮助配置和出片 |

赞助注册链接点击不能证明外部注册或付费；本地配置保存不等于连接可用。本次已经看到 sponsor_link_opened、api_key_configured、provider_test_finished，建议复用并统一口径，而非重新加一套。示例 onboarding 成功单列为引导效果，不能抬高真实素材激活率。

## 最小目标结构

```text
用户操作 → flow / attempt → 后端不可变结果摘要 → 本地受控采集适配层
                                             ├→ PostHog：业务结果与健康信号
                                             └→ Sentry：受控工程异常
主动反馈 → 独立反馈契约 → 收件箱 / 经用户明确提交的公开反馈
契约 + 指标字典 → 版本化 SQL → 三张决策看板 → 每周一页复盘
```

业务状态先在本地可靠存在，再按同意范围采集。优先复用当前状态存储/SDK，不先建新数据库、消息队列或全量日志平台。保留发生时间与观察时间；内部运行 ID 与对外随机关联 ID 分开。所有行为指标都需说明仅覆盖启用采集且成功送达的样本，不能外推为全部用户。

## 建议实施顺序与验收

1. **先止住错误解释与具体缺陷。** 修 F3；修 F2 阶段校验；现有看板明确“使用信号/未知覆盖率”；统一当前发布状态。验收：新增边界回归通过，旧事件含义不变。
2. **完成一个可闭环的 Studio 竖切面。** 只做“导入自己的素材→制作→导出→桌面确认保存”；统一 flow/attempt/artifact 与最小结果历史。验收：两素材并发不串链、重复保存不增产量、重试可区分、重启能恢复、关闭统计不回放。
3. **上线指标字典与三张看板。** 先跑覆盖率与样本量，再逐步启用激活/复用。验收：能用一组已知合成样本核对每个分子分母；生产没有样本时明确显示无数据，不显示成功率 0%。
4. **补引导、Provider 与质量反馈。** 区分示例和真实素材；把配置测试与首次实际成功相连；固定少量视频样本作出片质量基准。
5. **再处理长期可靠性和其他入口。** 有界补报、CLI/MCP 授权设计、更多平台和赞助归因依实际缺口推进。不要让整套数据平台成为当前稳定性修复的前置条件。

按每周有限投入，以上应拆成独立可验收的小改动。最先交付的是“一个能够相信的首次出片指标”，不是更多事件或更多仪表盘。

## 本轮可复验材料

- 回归命令：`node --test frontend/tests/analytics.test.cjs frontend/tests/studio-native-download.test.cjs frontend/tests/sentry-build.test.cjs frontend/tests/feedback-draft.test.cjs`，36/36 通过。
- 后端尝试：`.venv/bin/python -m pytest backend/tests/test_sentry_setup.py -q`，环境缺 pytest，未执行测试。
- 独立复现：`node docs/evidence/analytics-review-repro-20260929.cjs`。它加载真实 TypeScript 源码并隔离网络/存储，验证 F2/F3 当前缺陷；修复后这些“确认缺陷存在”的断言应改为正式回归中的正确行为断言。
