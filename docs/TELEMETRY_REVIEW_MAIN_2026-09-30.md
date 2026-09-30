# 最新 main 埋点复核：首次引导、示例、设置与 Studio

> 后续进展：本轮缺口已在本地分支补齐，具体实现、查询与边界见 [实施说明](analytics/NEW_USER_STUDIO_V2.md)。本文保留修改前的审查证据。

日期：2026-09-30。代码基线：`c26257521138ccbe2a0d65a2cc56963b9aa8b356`（#232）。

## 1. 同步和评审范围

本地已经在 main，只有未跟踪文档、素材和本地 data。SSH fetch 超时后，通过同一仓库 HTTPS 地址成功 fetch，未修改远端配置。HEAD 与最新获取的 origin/main 相同，ahead/behind 为 0/0，无需 merge。所有原有文件保留。

本次核对最新代码中的真实调用路径、事件字段、后端结果、相关测试；没有重新查询线上收数，因此结论是“当前 main 会怎样采集”，不表示用户已安装该版本或线上已收数。此次仅更新评审/设计文档，没有改埋点代码。

## 2. 结论

新功能补齐了首次体验，但采集体系没有同步覆盖这条新旅程。新增的示例入口事件和赞助来源字段有用；新的统一模型配置绕开了旧测试埋点，示例身份未贯穿导出，自动取景没有业务采用数据，Sentry 的新 phase 又被旧白名单过滤。

应在已确认的业务需求上调整实施优先级：**先辨别用户是在体验示例还是真实出片，接通引导到可用配置，再观察新 Studio 能力是否改善实际交付。** 不应把全部新按钮都加成点击事件。

## 3. 最新覆盖矩阵

| 新流程 | 当前已有信号 | 缺口 / 不能回答的问题 |
|---|---|---|
| 首页首次配置引导 | 引导内赞助链接带 placement=home_setup；保存后有 api_key_configured | 无引导实际展示、稍后、更多选项、导入拦截、保存校验失败；无法计算引导完成率 |
| 统一模型发现 | 业务响应有 live/cache/catalog、preview、warning | 新接口未接分析；不知道自动发现、默认选择是否卡住 |
| 统一连接测试 | UI 根据 success/ok 展示测试结果 | 新测试路径无 provider_test_*；旧图可能下降但不代表用户不测试 |
| 统一配置保存 | 每次成功保存，对全部 connections 发 api_key_configured | 不是一次配置完成，不区分首页/设置、用途、首次/修改；保存不是连通 |
| 示例工程 | example_project_opened | 在 create API 成功后、跳转前发送；不是页面成功显示；无失败/复用区别 |
| 示例后续编辑/导出 | 沿用通用 Studio / legacy 事件 | 无 material_origin/example_version，示例可与真实交付混合 |
| 设置页导航 | $pageview 仍存在 | query section 被清洗为 /settings，分栏跳转无法区分 |
| Studio 原有制作/导出 | requested/accepted/finished、原生 saved 等仍在 | 旧关联、恢复、成功证据边界仍未解决 |
| Studio 自动取景/依赖准备 | 后端部分异常 capture_studio_exception | 无安装/就绪、自动或手动触发、有效结果/零检测/失败、采纳到交付 |
| Studio 镜头取景与样式 | 草稿保存/导出带 aspect/subtitle_enabled/title_style | 不知道 crop/fit、自动取景保留或手工修正；仅保存不能证明功能有效 |

## 4. 关键发现

### P1-A：首次引导决定导入入口，但漏斗从拦截之后才开始

- `frontend/src/pages/HomePage.tsx:158` 挂载 FirstRunSetup，向 CreativeImport 传 blocked。
- `features/settings/FirstRunSetup.tsx:17` 判断是否需要引导；稍后本 session 隐藏，更多选项跳转设置；没有引导事件。
- `features/studio/CreativeImport.tsx:25` 在 blocked 时直接返回，尚未触发 studio_import_requested。

因此“打开应用但没有导入”既可能是配置被拦，也可能没找到入口、暂时没素材或主动离开，现有数据无法区分。needsSetup 是配置状态，不是安装身份：已有用户配置迁移/重置也可能进入引导，不得将所有引导曝光当新用户分母。

建议最小补充：setup_presented（真实可见，每次展示一个受控 presentation_id）、setup_action（later/open_settings）、import_blocked（reason=setup_required）；配置操作由统一适配器记录 placement。不要记录键盘输入或 API Key 编辑过程。

### P1-B：连接测试埋点迁移断开，保存事件语义变宽

- `features/settings/modelSettingsApi.ts:37` 的 get/save/discover/test 都直接调用 api。
- `features/settings/useModelSettings.ts:129` 的 test 调用新接口，没有 observeOperation。
- `services/api.ts:255` 的旧 testApiKey 仍带 provider_test_finished，但当前前端检索未找到使用它的 UI 调用方。
- `useModelSettings.ts:118` 每次保存对返回的全部 connections 各发一次 api_key_configured，即使用户只改了封面/转写或高级参数。
- `backend/api/v1/settings.py:61` 的测试存在 HTTP 200 + success=false；不能将请求受理当连接成功。
- `backend/services/ai_model_settings.py:222` 的 save 负责校验与落盘，不进行实际连接测试。首页“连接并保存”按钮调用这条 save 路径。

建议：统一 configuration_save 的 requested/resolved，一次用户保存计一次；另带受控 changed_roles、placement、initial/update。Provider 测试单独记录业务 success/failed/transport_unknown。旧 api_key_configured 降为兼容信号，不能跨版本比较成“新增配置人数”。

模型发现建议只记录一次有效发现的结果：source=live/cache/catalog、preview、结果数量区间、是否应用默认选择、受控错误类别和触发原因。当前加载、Provider 切换、650ms debounce 都可能触发发现，要区分自动与手动并忽略过期响应；不能把每次后台发现计作用户主动采用。

模型名、连接名称、地址、API Key、warning 原文均不上传。区分聊天/视觉/转写/封面角色，不用自由模型字符串做分析维度。

### P1-C：示例已能产生真实导出，必须沿全链路排除在真实激活外

- `backend/services/example_project.py:93` 将 processing_config.example=true、example_version 写入项目，并从内置素材建立真实原片/字幕/切片。create 可返回已有示例。
- `pages/HomePage.tsx:113` create 返回后发 example_project_opened，再 navigate；多次打开可重复发送。直接从已有项目卡打开不经过该函数。
- `ProjectDetailPage.tsx:279` 能识别 isExample，但 `features/studio/api.ts:26` 以后草稿/导出没有携带该属性，`analytics/workflow.ts:8` 白名单也没有素材用途字段。
- `StudioDownloadLink.tsx:24` 只观察保存，不传示例上下文。旧下载路径同样需要分类。

风险：目前无法证明哪次导出来自示例。不能依据“此设备曾打开示例”把该设备所有后续真实出片都排除。

建议以项目的明确示例标记建立 material_origin=sample/user/unknown，继承到草稿、重渲染、下载和发布；sample_version 使用受控版本。后端字段已有，但不是已完成采集。用同一 flow/artifact 的属性区分，缺属性保留 unknown。

示例最小路径：打开请求→可用/失败（created/reused）→详情实际可见→可选预览/编辑→示例交付→随后独立真实素材任务交付。不要把示例完成的预置项目状态当模型制作成功。

`events.ts` 与 `services/api.ts` 仍有“无原片”注释，与现在有原片、可再剪辑/渲染的实现不符，应在实现埋点时同步修订，防止后续统计设计继续按静态演示理解。

### P2-D：设置页分区丢失，但不需要记录所有控件

`SettingsPage.tsx:55` 根据 section query 导航，App pageview effect 监听 search，但 `analytics/workflow.ts:58` routeName 去掉 query，最终都记 /settings。这会产生多条无法分辨分区的页面事件。

建议按实际可见 active section 记录受控 settings_section_viewed（ai/publish/app/feedback），旧 deep link 映射为对应 role/anchor；首次引导进入设置保留 entry_source。AIModelSettings 即使在其他 section 时仍挂载（hidden），不能用组件 mount 代替用户看见 AI 设置。

仅采集用于判断配置障碍的设置结果：分析模式、转写 local/cloud、封面 frame/AI、是否独立服务、相关角色是否已配置。无需每个开关点击都上传；区分未保存编辑与已保存配置。

### P2-E：自动取景无业务闭环，Sentry 新 phase 被剥离

- `features/studio/api.ts:14–16` framingStatus/install/autoFrame 都是直接请求。
- `StudioEditor.tsx:82` 处理取景结果，`104` 的 effect 会自动运行，portrait 操作也会触发；仅看请求数会把自动行为当主动采用。
- `backend/api/v1/studio.py:367` 用 phase=auto_frame 捕获异常；`backend/core/sentry_setup.py:133` 白名单不包含 auto_frame。离线调用 before_send 已确认 phase 被移除，但事件及 area=studio 仍保留，不是异常完全不上报。
- 现有 save/export 属性不含 layout、crop_track 来源或手工修正信息。

建议最小链路：取景依赖准备结果→取景操作结果（trigger=auto/manual/portrait_preset）→是否获得有效结果/零检测→保存或导出时是否保留该结果。保留 aggregate counts 和布局枚举，不上报人脸框、坐标轨迹、截图、字幕和场景 ID。

“未检测到人脸”与“请求失败”不同；“运行成功”与“用户采纳”不同；发生手动调整只能说明发生调整，不能直接标为自动结果质量差。手动滑动不逐帧埋点，可在保存时汇总 has_manual_adjustment。

## 5. 上轮系统问题是否仍存在

本次重新运行旧缺陷复现脚本，三个场景仍成立：存储可读不可写时应用层 opt-out 判断失效；未结算筛选观察消费制作失败；旧 plan 被替换后制作终态无法恢复。仍不据此断言 SDK 实际发生网络泄露。

Studio 无跨阶段业务关联、前端观察/队列确认语义、浏览器下载意图不等于保存等边界也仍在。此次功能更新没有实现此前的完整数据系统方案。

## 6. 对数据设计与实施顺序的修订

| 顺序 | 工作包 | 要回答的业务问题 | 验收 |
|---|---|---|---|
| 1 | 素材用途贯穿 sample/user/unknown，并修隐私门禁 | 首次出片是否真的来自用户素材 | 示例保存不进真实激活；随后真实项目能正常计入 |
| 2 | 首次引导 + 统一配置保存/发现/测试 | 引导是否减轻配置障碍，卡在何处 | 首页与设置分源；200+success=false 算测试失败；保存不冒充连接成功 |
| 3 | 统一 flow/attempt/artifact 和可靠终态 | 从配置完成到真实交付是否可追踪 | 并发/重试不串链；不丢阶段归属；未知明确 |
| 4 | Studio 取景与实际采用、Sentry phase | 取景是否改善可用成片，失败在哪里 | 自动/手动分开；零检测分开；phase 保留；最终交付属性可查 |
| 5 | 负责人查询与示例到真实转化 | 新版引导、示例、Studio 是否改善首次成功 | 新契约/新版本独立 cohort；成熟窗口后再看转化 |

顺序 1–2 先改善当前新版的可解释性，但精确任务漏斗要等顺序 3 完成。不能先画精确转化率再补关联。质量反馈、渠道与经营台账继续沿完整方案分阶段推进。

## 7. 验证记录与待补测试

实际执行：53 项前端测试通过（analytics、model-defaults、model-settings-logic、studio-draft、studio-native-download）。已有三个旧缺陷的离线复现仍通过；另用真实 before_send 函数、隔离同意读取和无关导入分类后验证 auto_frame phase 被过滤。均没有发送真实遥测。

这些测试覆盖已有路径，不证明新引导已被埋点。尤其 analytics 测试仍显式调用旧 settingsApi.testApiKey；旧测试通过不能证明新 UI 的 test 已被观察。

新增实现必须验证：

- 引导加载完成且实际展示才记曝光；重渲染不重复；重新触发有新展示标识。
- 稍后、更多选项、配置不完整拦截分别可识别；中途离开原因保持未知。
- 首次保存与修改封面/转写的保存不混；多连接保存不增加“配置完成次数”。
- 模型发现过期响应不产生有效完成事件；缓存/目录预览不冒充实时连通。
- 示例 create 的创建/复用/失败，直接从项目卡打开，均按实际语义记录。
- 示例经旧下载和 Studio 渲染/保存后仍为 sample；未知旧项目不默认为 user。
- 设置页 hidden 的 AI 组件不产生可见曝光。
- 自动取景触发来源、零检测、依赖安装失败、手动修正、最终采用分别有证据。
- 新事件字段经过白名单；旧事件按版本隔离；新安装包实际收数单独验收。

完整设计入口：[AutoClip 数据系统设计方案](DATA_SYSTEM_DESIGN_2026-09-29.md)。本稿是对新 main 的增量复核，不替代业务需求。
