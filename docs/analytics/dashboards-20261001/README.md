# 线上看板登记（2026-10-01）

- PostHog：[AutoClip｜创始人三数日报](https://us.posthog.com/project/450605/dashboard/2158541)
- 口径：[DAILY_FOUNDER_REPORT.md](../DAILY_FOUNDER_REPORT.md)
- Sentry 旁注：[出片稳定性](https://autoclip-ts.sentry.io/dashboard/10252510/?statsPeriod=7d) · [昨日新增 Issue](https://autoclip-ts.sentry.io/issues/?query=is%3Aunresolved+firstSeen%3A-24h+%21telemetry_test%3Atrue+%21environment%3Adevelopment)

旧 Studio V1 / V2 看板保留历史口径，不改它们的 SQL。

## 图表

| 图 | short_id |
| --- | --- |
| 昨日三数快照 | [8BVp7oWq](https://us.posthog.com/project/450605/insights/8BVp7oWq) |
| ① 1.5 应用内故障 14 日 | [YmQp9dNt](https://us.posthog.com/project/450605/insights/YmQp9dNt) |
| ② 真实首次出片 vs 示例 14 日 | [8NvQvFeC](https://us.posthog.com/project/450605/insights/8NvQvFeC) |
| ③ 1.5.0 Windows vs Mac 日活 | [YAOHkseZ](https://us.posthog.com/project/450605/insights/YAOHkseZ) |
| 1.5 制作结果对照 | [pwg24Oyl](https://us.posthog.com/project/450605/insights/pwg24Oyl) |
| 1.5 收数覆盖 | [9sfL8lU2](https://us.posthog.com/project/450605/insights/9sfL8lU2) |

SQL 固定滚动窗口，不受看板日期覆盖器影响。

## 发送

PostHog 订阅每天 00:30 UTC 发邮件：

- 看板图：[订阅 158547](https://us.posthog.com/project/450605/subscriptions/158547)
- 文字日报：[订阅 158548](https://us.posthog.com/project/450605/subscriptions/158548)

2026-10-01 16:14 UTC 测试邮件已发送完成。GitHub Action `daily-founder-report.yml` 同一时间跑脚本；配置了 `FEISHU_WEBHOOK_URL` 才发飞书。不要把这些数写进公开 Issue。合并到默认分支后，定时任务才会真正每天跑。
