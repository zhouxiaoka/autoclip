# AutoClip 完整诊断与迭代判断

日期：2026-09-30。代码基线：`c2625752`（main / #232）。本报告在隔离 worktree `worktree-project-diagnosis` 完成；只读分析，不修改产品代码、远端、Issue 或 Release。

## 一句话结论

AutoClip 现在最稀缺的不是功能，而是**让下载桌面版的用户在第一次真实素材任务中稳定得到可用成片，并证明这件事正在发生**。

项目已经有足够强的产品面：Studio、模型配置、示例工程、字幕与视觉路线、编辑、导出、发布、CLI/MCP。继续扩模型、做游戏买量工作流或补更多编辑能力，会进一步扩大验证面，却不会解决当前最主要的用户信号：Windows 用户在导入、转写、处理与预览阶段失败后只得到泛化反馈。

接下来六周应该只服务一个北极星指标：

> 在已同意匿名统计的桌面设备中，首次使用**用户自己的素材**发起任务后，24 小时内成功保存一条成片的比例。

示例工程、预置项目、浏览器下载意图、网络请求成功都不能计作这个指标的成功。当前埋点不足以可靠计算它，必须先补齐口径和关联。

## 证据快照

| 信号 | 实测 / 已知事实 | 判断 |
| --- | --- | --- |
| 社区触达 | GitHub 最近 14 天 43,130 views、18,268 uniques；6,558 clones、2,747 unique cloners；星标 9,050、fork 1,668 | 获客不是眼下瓶颈，流量已足以暴露产品可靠性问题 |
| 来源结构 | GitHub、X、Google 是前三来源；README overview 有 16,070 unique visitors | README 和下载链路是高价值入口，首页首屏必须优先服务第一次成功 |
| 版本下载 | v1.4.0 在 9/27 发布后已有 911 Windows installer 下载、200 DMG 下载 | Windows 下载约占已知安装包下载的 82%，必须以 Windows 为发布基线 |
| 反馈结构 | 40 个开放 Issue：18 Windows、18 bug、24 from-app、11 duplicate、5 needs-triage；近期大量标题为“processing failed”“无法导入”“not working” | 反馈不是零散边缘案例，而是主流程失败的重复信号 |
| 工程测试 | 当前 worktree 的后端完整测试：`721 passed, 1 skipped`，92 秒 | 后端回归保护较强，但不能代替用户设备、安装包和真实网络验证 |
| 静态检查 | `ruff check backend` 报 3,943 项，其中 2,503 项可自动修复；CI 将 Ruff 设置为 `continue-on-error` | 静态债务很高。当前不应全仓清理，先把新增代码与高风险规则纳入门禁 |
| 发布流程 | `RELEASE_CHECKLIST.md` 已明确 Pre-release → 双平台真机冒烟 → 观察期 → promote | v1.4.0 于 9/27 已直接作为 latest 发布；之后仍持续出现 Windows 导入/处理反馈。流程已经写下，但还未成为硬执行习惯 |

GitHub 流量只保留近 14 天窗口；下载计数含重复下载与 updater 的 `latest.json` 下载，不能当活跃用户数。

## 当前产品状态

### 已经做对的部分

1. **Studio 的交互方向正确。** 当前入口是统一的 `CreativeImport → /studio/import → 推荐/确认 → 制作 → 草稿编辑 → 导出`，并在确认前不启动正式制作，见 [HANDOFF.md](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/HANDOFF.md:8) 和 [CreativeImport.tsx](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/frontend/src/features/studio/CreativeImport.tsx:24)。这比旧的“一键处理后才发现结果不对”更接近真实剪辑流程。
2. **新手的空白页被填上了。** 首次配置弹窗与可编辑的示例工程降低了“我下一步做什么”的不确定性。示例工程是体验入口，不该作为真实激活证据。
3. **对近期 Windows 故障已有针对性修复。** 已补 ffprobe timeout、缩略图提取、本地导入缩略图、兼容预览、子进程清理，详见 [反馈排查](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/docs/FEEDBACK_TRIAGE_2026-09-28.md:7)。方向正确，但这些修复尚未被 Windows 实机的端到端路径验证。
4. **Auto-frame 的产品判断合理。** 新实现按镜头切换、人脸与说话嘴部活动选择 crop，未识别到人物时回退完整画面 + 模糊背景，而不是强行把屏幕/课件裁掉，见 [framing.py](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/backend/services/studio/framing.py:1)。这是质量提升，不是当前可靠性问题的替代品。
5. **隐私边界总体谨慎。** PostHog 不自动抓 DOM、不录屏、禁用 URL/referrer；Studio 对外字段采用白名单，见 [posthog.ts](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/frontend/src/analytics/posthog.ts:73) 与 [workflow.ts](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/frontend/src/analytics/workflow.ts:8)。后续扩埋点应继续保持这条边界。

## 关键诊断

### P0：发布纪律与实际发布脱节

`RELEASE_CHECKLIST.md` 要求 tag 先成为 Pre-release、Windows 与 macOS 均完成安装/导入/出片/保存、观察 24 小时后才 promote，见 [RELEASE_CHECKLIST.md](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/RELEASE_CHECKLIST.md:40) 和 [RELEASE_CHECKLIST.md](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/RELEASE_CHECKLIST.md:47)。但 v1.4.0 已是 latest；其后仍出现 #224、#225、#230、#231 等 from-app 的主流程失败反馈。

这不代表 v1.4.0 必然有同一根因，但说明“构建与 CI 通过”仍在替代“真实用户设备可完成任务”的发布判断。Windows 约占 82% 已知安装包下载，Windows 不是次要平台。

**判断：停止下一轮功能发版。** 仅合入能改善 Windows 首次出片、错误诊断与发布门禁的 S1/S2 修复。下一次常规发版应为 `1.4.x` 可靠性批次，不夹带新产品能力。

### P0：用户主流程没有可解释的失败闭环

首页阻止未配置用户导入时，只显示“请先连接 AI 服务，再导入视频”，见 [CreativeImport.tsx](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/frontend/src/features/studio/CreativeImport.tsx:24)。首次配置弹窗里的“连接并保存”只调用保存，不做连接测试；错误 Key 往往到实际制作才暴露，见 [FirstRunSetup.tsx](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/frontend/src/features/settings/FirstRunSetup.tsx:46) 与 [useModelSettings.ts](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/frontend/src/features/settings/useModelSettings.ts:108)。

这与 README 所写“测试连接后保存”也不一致，见 [README.md](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/README.md:156)。用户自然会把“已保存”理解成“已可用”。

当前常见失败路径至少有：后端未启动、模型凭据无效、模型不支持所选能力、Whisper 未安装、下载受 Cookie/地区/站点限制、ffprobe 或编码卡住、原始素材无法由 WebView 解码、LLM 结构化响应失败、渲染失败、系统下载未保存。它们不能继续被压成“处理失败”。

**判断：下一个版本应给每一类失败一个动作。** 例如重新测试连接、安装语音组件、改用 SRT、选择浏览器 Cookie、生成兼容预览、查看本地诊断包、重试当前阶段。不要只增加更多错误码或更多 toast。

### P0：核心成功指标尚不可测，且会被示例工程污染

main 新增 `example_project_opened`，但事件只在 create API 成功后、页面跳转前发出；无法区分创建/复用，也不表示页面真实可见。更重要的是，示例工程可编辑、渲染、下载，却没有把 `sample/user/unknown` 贯穿到 Studio 草稿、导出和保存事件。

已有 Studio 工作流为了隐私不上传项目/任务 ID；这使并发制作、重试、再次导出与终态恢复无法可靠关联。`workflow.ts` 还会把当前 `analysis.status=failed` 直接记为筛选失败，未校验它是否属于 production，见 [workflow.ts](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/frontend/src/analytics/workflow.ts:144)。

**判断：埋点不是“再加按钮点击”。** 必须先修数据契约：本地随机 `flow_id / attempt_id / artifact_id`，受控 `material_origin`，不可变终态摘要，和明确的 `unknown`。不上传文件名、URL、字幕、模型自由文本或项目内部 ID。

### P1：产品战略文档发生冲突，容易消耗仅有的维护时间

`ROADMAP.md` 顶部仍将游戏买量、Seed、Jev 和六周样片视为“当前方向”，见 [ROADMAP.md](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/ROADMAP.md:3) 与 [PRODUCT_PLAN_2026_Q4.md](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/docs/PRODUCT_PLAN_2026_Q4.md:1)。但负责人后续已明确：目标是开源影响力、万星与赞助；每周仅 5–10 小时；游戏买量暂缓；优先让更多人第一次切出可用片子。

这两条路线服务不同用户、不同质量标准和不同商业路径。当前公开流量与 Issue 也指向内容创作者的桌面首用问题，不是缺少游戏投放编排。

**判断：冻结游戏买量路线。** 保留已有研究与 auto-frame 的通用价值，不继续投入 Seed/Jev/HyperFrames/买量素材变体，直到以下两个门槛同时满足：

- Windows 的真实素材首出片路径有稳定证据；
- 连续四周的数据表明主用户确实有游戏录屏高光需求，且不只是一次性讨论。

### P1：工程边界过大，旧入口和设计债务持续抬高修复成本

代码约 78,921 行，其中后端约 63,317 行、前端约 14,327 行、Rust 约 1,047 行。主线入口已转为 Studio，但旧 `BilibiliDownload.tsx`（506 行）、`FileUpload.tsx`（493 行）、复杂的旧 `ProjectCard.tsx`（692 行）以及多处发布/合集模态仍保留大量 Ant Design 默认界面和重复逻辑。

`HANDOFF.md` 已承认旧导入组件没有前端引用，见 [HANDOFF.md](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/HANDOFF.md:23)。设计系统则明确要求避免渐变、彩色 chip 与多色状态，见 [DESIGN.md](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/DESIGN.md:13)。当前 `CreateCollectionModal.css`、`AddClipToCollectionModal.css`、旧 `index.css` 仍有渐变、青色和按分数变色的 UI。

**判断：不要全面重构。** 先在可靠性批次结束后，用一次受控清理移除不可达旧前端入口，并把首页、项目卡与高频错误/进度组件迁到 `ui/` 原语。移除前必须核对 API/CLI/深链接依赖，不能仅凭“组件没有 import”删除后端路径。

### P2：静态质量债务真实存在，但不能抢占用户主流程

`ruff check backend` 当前报 3,943 项，CI 以 `continue-on-error` 运行 Ruff，见 [.github/workflows/ci.yml](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/.github/workflows/ci.yml:37)。其中大量是可机械修复的 import、typing modernization 和格式问题，也夹有 blind exception、未使用变量、潜在错误闭包等。

**判断：不要全仓 `ruff --fix`。** 单开一个低风险清理批次：

1. CI 先对新增/修改文件启用阻断的 `F`, `E9`, `F821`, `F811`, `B` 子集；
2. 后续再机械整理，不把几千行格式 diff 混入产品修复；
3. 修复每个高频 Sentry/用户故障时，同时消除该路径的 blind exception 与泛化错误输出。

### P2：auto-frame 是有价值的实验，但现在的运行时与可观测性还不完整

auto-frame 在用户机器上按需 `pip install opencv-python-headless`，标称约 45 MB，见 [framing.py](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/backend/services/studio/framing.py:12)。这增加了新的网络、代理、磁盘与安装失败面。API 已用 `auto_frame` 调 Sentry，见 [studio.py](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/backend/api/v1/studio.py:352)，但提交版本的 Sentry phase 白名单不含该值，见 [sentry_setup.py](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/backend/core/sentry_setup.py:131)，因此 phase 会被剥离。

前端也没有区分自动触发、用户手动触发、无人物检测、成功取景、手动修正、最终保留或导出的行为。

**判断：本功能不扩大范围。** 先补 runtime install、auto-frame 结果与最终采纳的最小观察链，再根据真实使用判断是否继续优化人脸/说话人算法。

## 接下来六周的单线程计划

每周最多 5–10 小时，按顺序推进；任何未通过的验收都阻塞后续项。这里的“周”是工作量桶，不以日历承诺。

| 顺序 | 工作包 | 用户结果 | 验收标准 | 规模 |
| --- | --- | --- | --- | --- |
| 0 | 立即：发布止血与 triage | 新用户不会继续被未验证版本推送 | 审计 v1.4.0 是否遵循 Pre-release/观察期；近期 from-app 反馈聚类成 1–3 个根因追踪 Issue；明确当前 latest 是否需要 halt | S |
| 1 | Windows 首出片验收包 | 真实 Windows 上能安装、配模型、导入、出片、保存 | Windows VM 或真机覆盖升级 + 干净安装；本地 MP4 与一个链接；保存的 MP4 完整解码；证据写入 release doc | M |
| 2 | 失败诊断与恢复 | 用户知道下一步怎么办，而非只看到失败 | 每个首次路径阶段给出受控错误类别、可执行按钮、可附到 Issue 的脱敏诊断摘要；至少覆盖模型、Whisper、导入、视频兼容、渲染、保存 | L |
| 3 | 新用户数据契约 | 能正确判断用户是否真的首次出片 | material_origin、flow/attempt/artifact、first-run 引导、配置保存/测试、终态/unknown；示例工程绝不进入真实首出片分子 | L |
| 4 | 可靠性 `1.4.x` Pre-release | 修复能先小范围验证再影响全部用户 | 两平台 smoke、Windows 测试者、24–48h Sentry 与 from-app 观察；符合清单后才 promote | M |
| 5 | 首屏与项目卡收口 | 从 README 下载后的用户更清楚、更能行动 | 首页明确“自己的短样片优先”、示例只是体验入口；项目卡统一真实状态、失败恢复和诊断；按 DESIGN.md 去除高频屏旧 AntD 风格 | M |
| 6 | 质量基线和收敛 | 改进出片质量时不再凭感觉 | 3–5 个可再分发且有授权的真实样本；人工评分表覆盖边界、标题、字幕、构图、可用性；每个产品改动至少回归其中一组 | M |

### 明确暂停

- Seed/Jev/游戏买量制作、HyperFrames 接入与广告变体。
- 新的 provider、模型、发布平台、账号、credits 和商业化。
- 1080p60、Intel Mac、全仓 UI 翻新、全仓 Ruff 清零。
- 以“更多埋点事件”代替业务关联和终态证据。

暂停不是删除。它们进入冰箱，等首次真实出片、Windows 发布门禁和数据口径稳定后再重新排序。

## 负责人应每周只看这五个数字

1. **设备级真实首次出片率**：首次 user material import 后 24 小时内 native saved 的独立 flow / 合格首次 user material flow。
2. **阶段失败率**：配置测试、Whisper、导入、筛查、制作、渲染、保存，未知单列。
3. **未知终态率**：已登记且成熟的 attempt 中，没有终态证据的比例。该值高时禁止解读转化率。
4. **Windows 与 macOS 的分版本失败密度**：用真实失败 flow 数或设备数，不用异常事件总数。
5. **示例到真实素材的跨越率**：体验示例后，在 7 天内另一次 user material flow 成功交付。示例导出本身不记成功。

先按设备分析，不假装知道“用户”或“自然人”。浏览器下载只表示已请求，不能计入 native saved；没有看到终态只能归 `unknown`，不能猜为失败。

## 当前建议的决策

1. 将主线对外定位锁回“让长视频快速变成可用高光”的创作者工具。README 当前定位与此一致，见 [README.md](/Users/zhoukk/autoclip/.claude/worktrees/project-diagnosis/README.md:7)；不要让游戏买量实验占据主产品叙事。
2. 把 PR #221 的反馈修复作为可靠性批次候选，先 code review，再在 Windows 实机/VM 验收，之后才决定是否进入 `1.4.x` Pre-release。
3. 将 v1.4.0 之后的反馈按阶段聚合，先拿到 #230/#231 的诊断材料。没有素材、日志、版本与步骤，就不要把它们当成同一个 bug，也不要关闭。
4. 下一次完整产品规划以本报告的六个工作包为入口，替换或显式归档旧的游戏买量“当前方向”文档。保证 README、ROADMAP、HANDOFF、社区看板只保留一个当前优先级。

## 验证记录与局限

- 本 worktree 基线为 `c2625752`，工作区在写入本报告前无产品代码改动。
- 本地运行：`/Users/zhoukk/autoclip/venv/bin/pytest backend/tests -q`，结果 `721 passed, 1 skipped in 92.05s`。
- 前端 `tsc`、ESLint 与 `node --test` 未能在本 worktree 独立运行，因为 worktree 没有 `frontend/node_modules`；尝试复用主目录二进制时，Node 模块解析仍从 worktree 查找依赖，因此出现缺包错误。这不作为源码失败结论。GitHub 的 #232 前端检查为成功。
- 未在真实 Windows、真实用户网络、付费模型或 PostHog/Sentry 线上数据上执行写操作。GitHub traffic/release/issue 数据是查询时点快照。
- 本报告不主张 v1.4.0 某个具体反馈一定由某段代码造成。对具体故障应先取得可复现输入与日志，再做根因修复。
