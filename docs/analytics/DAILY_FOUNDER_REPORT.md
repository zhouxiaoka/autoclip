# 创始人三数日报

日期：2026-10-01。代码基线：main `1.5.0`。

埋点契约已经写过好几轮，线上真正卡住日报的不是“没事件名”，而是**同一句话在不同版本、不同系统里并不是同一个数**。这份文档把三个数钉死，并说明哪些看板看起来像答案但不能用。

## 结论先说

口径文档是清楚的。不清楚的是拿哪条线上数据当“成功 / 故障 / 日活”。

| 容易误读的信号 | 为什么不能当日报 |
| --- | --- |
| 旧 Studio V1 / 业务健康看板 | 1.3 链路，导出漏记，下载收到文件 ≠ 保存 |
| [Studio V2 看板](https://us.posthog.com/project/450605/dashboard/2152007) 的“示例后 7 日真实出片” | 查询依赖 `example_project_viewed`，线上没有这个事件，只有 `example_project_opened` / `example_project_open_finished` |
| 1.4 `studio_export_finished` completed | 没有 `material_origin`，示例和真实素材混在一起 |
| Sentry `count()` | 7 日约 1.7 万次，主要是 `ConnectionResetError` 等连接噪音；Users 经常是 0，不是失败任务数，也不是受影响用户 |
| `studio_generation_finished` failed | 说明 1.5 有人在做片，但失败不是第二个数里的“出片” |

三个数只认下面的定义。空数表示没收到符合口径的事件，先看收数覆盖，不要解释成转化率为零。

## 每天的三个数

时间窗：UTC 日历日。项目时区是 UTC。北京时间早上 08:30 发出的是**昨天**完整日。

### ① 1.5 应用内故障

- **事件**：`feedback_submitted`
- **过滤**：`category = 'bug'`，`app_version` 匹配 `^1\.5`，`feedback_id` 非空
- **去重**：`uniq(feedback_id)`
- **不是**：Sentry 事件量、Sentry 未解决问题总数、旧版本反馈、想法（`idea`）
- **旁注**：GitHub `from-app` Issue 是这条事件的收件箱，可能晚一小时；Sentry 只看**当日新增 Issue**（`firstSeen` 落在该日），不并进这个数

点「发送」不看匿名统计开关，所以这个数比 `app_opened` 更接近“用户主动说坏了”。

### ② 真实首次出片（对照示例）

设备第一次完成交付时的 `material_origin`。

**完成交付**（必须同时满足）：

- `analytics_environment = 'production'`
- `material_origin ∈ {user, sample}`
- 下列之一：
  - `studio_download_saved`（原生实际保存了非空文件）
  - `studio_export_finished` 且 `outcome = completed`
  - `studio_generation_finished` 且 `outcome = completed`

**第一个数取 user，对照取 sample。** 该设备更早的失败、示例打开、浏览器 `studio_download_requested`、1.4 无素材字段的导出，都不算。

回看窗口 35 日，只为判断“是不是第一次”；日报只报完成日落在昨天的设备。

2026-10-01 复核：生产里还没有符合这条的完成交付。1.5 已有 `material_origin=user` 的 `studio_generation_finished`，但 outcome 全是 `failed`。这会显示在对照表，不抬高第二个数。

### ③ 1.5.0 Windows / Mac 日活

- **事件**：`app_opened`
- **过滤**：`analytics_environment = 'production'`，`app_version = '1.5.0'`，`os ∈ {windows, macos}`
- **去重**：`uniq(person_id)`
- **不是**：安装量（`app_installed`）、全版本日活、出片量、`$os` 浏览器解析值。客户端 super property 是 `os=windows|macos`。

旧版本日活仍很大（1.4 Windows 一天一百多台），不并进这个数。要看旧版本去原业务看板。

## 线上复核（2026-10-01，UTC）

| 数 | 昨日 2026-09-30 | 今日到下午（未完整） | 读法 |
| --- | --- | --- | --- |
| ① 1.5 应用内故障 | 0 | 0 | 1.5 还没有人从应用里提交 bug；旧版本昨天 4 条，今天 1 条，进收件箱但不进第一个数 |
| ② 真实首次出片 / 示例 | 0 / 0 | 0 / 0 | 没有完成交付。今天 4 台设备（Windows 3 + Mac 1）真实素材制作失败 |
| ③ 1.5 Windows / Mac | 0 / 0 | 18 / 1 | 1.5 生产收数从今天开始；昨天完整日确实是 0，不是查询漏了 |

Sentry：7 日 error 事件约 17682，不能当①。今天新增未解决问题约 9 个（含 `PipelineFailure` / `VisionRequestError`），只作旁注。GitHub 仍有开放的 `from-app` Issue（例如 #247、#249），版本以帖子正文为准。

## 现有埋点哪些能用

能用，而且 1.5 已经在生产到达：

- 生命周期：`app_installed` / `app_opened` / `app_updated`，带 `app_version`、`os`、`arch`
- 引导：`setup_presented`、`setup_action`、`import_blocked`
- 示例：`example_project_open_finished`（有 `material_origin=sample`）
- 1.5 快速出片：`studio_generation_finished` 带 `studio_schema_version=2` 和 `material_origin`
- 应用内反馈：`feedback_submitted`（分类、版本、系统、反馈编号）

还不能支撑“示例 → 真实”成熟队列：

- 没有 `example_project_viewed`
- 1.4 Studio 终态没有 `material_origin` / `studio_schema_version`
- CLI / MCP 不采集
- 网页下载没有落盘证据
- PostHog 治理指标目录是空的，这三个数目前不是 catalog metric

Sentry 工程异常看板仍可用，但必须排除 `telemetry_test` / `development`，并且**用新增 Issue 而不是事件次数**。`PYTHON-FASTAPI-3` ConnectionResetError 单独看，不要放进日报分子。

## 发送

1. **邮件（主通道）**：PostHog 每天 00:30 UTC（北京时间 08:30）发到维护者邮箱。看板 [AutoClip｜创始人三数日报](https://us.posthog.com/project/450605/dashboard/2158541)，订阅 [图表](https://us.posthog.com/project/450605/subscriptions/158547) 和 [文字](https://us.posthog.com/project/450605/subscriptions/158548)。2026-10-01 16:14 UTC 测试邮件已发送完成。
2. **飞书（可选）**：仓库 secret 已有 `FEISHU_WEBHOOK_URL` 时，`.github/workflows/daily-founder-report.yml` 同步发一条。没有 webhook 就只打印，不在公开 Issue 里写这些数。
3. **本机**：`python3 scripts/daily_founder_report.py`；`--date YYYY-MM-DD` 指定 UTC 日；`--post` 发飞书。

查询原文：[daily_founder_report.sql](daily_founder_report.sql)。脚本与线上看板用同一套口径，日期过滤在脚本里参数化。

## 不要做的事

- 不要把 1.4 `studio_export_finished` completed 补成 `user`
- 不要把 Sentry 日事件量加成①
- 不要用设备数当安装转化率或自然人
- 不要改旧看板的历史口径；这个日报是新板
