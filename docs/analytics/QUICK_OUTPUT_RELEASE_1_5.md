# 1.5 发布前客户端埋点复核（2026-10-01）

本轮复核实际 UI → API → 后台任务观察 → 交付结果，不把按钮点击、请求受理和文件保存混为成功。已有启动/版本/匿名设备、页面导航、首次引导、模型发现/测试/保存、示例、导入、制作、渲染、原生下载、平台发布、评分和反馈链路保留。

## 本轮补齐

| 路径 | 可观察结果 |
|---|---|
| 竖版版式 | import requested/accepted 与 generation finished 的 `portrait_style=auto/interview/podcast`；不改变平台语言 |
| 片尾设置 | `output_branding_save_requested/finished`；`brand_outro_enabled` 只记录请求意图或已保存值 |
| 自动成片片尾 | `outro_applied_count` / `outro_fallback_count` / `outro_unknown_count`；只有已完成视频纳入，关闭设置不是失败 |
| 取景降级 | generation finished 分开 `full_frame_count` / `framing_pending_count` / `framing_captions_count`；与 speaker_framed_count 联合观察 |
| 发布包下载 | 原生 `studio_download_requested/saved/failed` + `artifact_type=publish_kit`；浏览器只报 requested；视频为 video |
| 发布文案编辑 | `studio_post_save_requested/accepted/request_failed`，不上传正文 |
| AI 重新设计封面 | `studio_cover_redesign_requested/accepted/request_failed/finished`；后台任务终态可跨页面/重启补报，受理不等于完成 |
| 单条重试/备选生成 | 原请求事件 + `studio_variant_finished`，按本次 render job 匹配，旧失败不会消费新重试；实际片尾和警告数量随结果报告 |
| 编辑器导出 | `studio_export_finished` 增加 `outro_applied` / `warning_count`，不上传警告原文 |

修复旧误报：导入未传片尾参数时，不能假定开启；完成时以后台 generation/job 为准。新增属性是 Studio schema 2 / experience schema 1 的追加字段；旧事件缺字段按未知处理，不能补成 false。

隐私：只允许枚举、布尔、计数和匿名关联 token；内部 ID、路径、标题、字幕、文案、URL、模型响应和密钥留在本机。关闭统计会清理待观察任务并作废进行中的请求；再次开启不回放。CLI/MCP 不新增自动采集。

## 验收

- 前端 198 tests passed；typecheck / lint / production build 通过。新增用例覆盖实际 API、后台任务重启恢复/去重、旧失败与新重试隔离、片尾关闭/失败/未知、发布包保存/失败/浏览器意图与中途关闭统计。
- GitHub 正式构建已配置公共 PostHog client key、前后端 Sentry DSN 和 sourcemap 上传凭据；复核只读取 Secret 名称，不读取其值。
- 已打开既有 PostHog 新用户/Studio V2 看板，确认存在引导与模型发现的生产收数；原有交付图还不覆盖快速出片新事件，不能据其空结果判断 1.5 无用户。新增查询见 [快速出片交付](quick_output_release.sql)，发布后按版本与 production/validation 分开检查。
- 独立 validation 页面使用实际 SDK 与当前埋点模块发送合成状态；PostHog 接收端已确认片尾设置、发布包保存、AI 封面完成事件，以及 app_version=1.5.0、analytics_environment=validation、artifact_type=publish_kit、outro_applied=false、Studio schema 2。合成状态不作为实际制作/磁盘交付证据；正式包仍需持续看真实收数。
- AI 封面也用界面已收到的终态结算，防止再次重做覆盖前一次记录；与后台观察共用去重。Sentry 排除 telemetry_test 后当前无 1.5 错误样本，不据此宣称零错误。原有看板历史口径保留。
