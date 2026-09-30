# 线上看板登记（2026-09-30）

- PostHog：[AutoClip｜新用户到真实出片（Studio V2）](https://us.posthog.com/project/450605/dashboard/2152007)
- Sentry：[AutoClip｜出片稳定性与故障定位](https://autoclip-ts.sentry.io/dashboard/10252510/?statsPeriod=7d)

旧 PostHog Studio V1 与业务健康看板保留；新版单独建板，不改变历史图的统计口径。Sentry 既有 Studio 工程异常/配置警告 Issue View 保留。

## 每周如何使用

1. 先查数据覆盖：是否收到了目标版本、生产环境、新契约事件。没有收数先排查发布、同意开关与采集，不能直接判断产品无人使用。
2. 看真实素材交付设备/流程/成片：sample、user、unknown 分开；渲染、原生保存、发布分别看。浏览器点击下载不作为保存。
3. 看引导与配置障碍：跳过/更多设置、配置保存、模型发现来源、真实连接测试分别分析。保存成功不证明能调用模型，目录预览不证明连通。
4. 看成熟队列：7–14 日前看过示例的设备，观察其后 7 日内是否有真实素材渲染完成。分母为观察到的示例设备，非安装队列、非自然人；零分母不解释转化率。上线后需等待完整窗口。
5. 看 Sentry 的异常趋势、高频 Issue、版本与 Studio 阶段，选择影响主路径的问题处理。事件次数受轮询/重复报告影响，不能作为失败任务数；当前没有可靠用户分母，不用 crash-free users 冒充稳定性。
6. 每次迭代记录“发现—判断—行动—下次验证指标”。不要只追求事件数下降；结合交付证据与失败恢复情况复核。

## 发布时的验收

- 本次仅建立看板，没有发布客户端。experience 1 / Studio 2 的业务图当前无生产样本；这是待收数状态。
- 发布后用独立 validation 构建检查：引导、连接失败、示例导出、真实素材导出、原生保存、自动取景、关闭统计。业务图只纳入 production。
- 逐项核对 sample/user/unknown、flow/artifact、attempt、app_version、runtime、枚举与终态。无真实内容、模型名、密钥和地址。
- Sentry 排除 telemetry_test=true 以及明确 development，保留未知环境的历史事件以免静默漏掉故障。这是“非测试故障观察”，不是严格 production 失败率。新版 auto_frame 标签仍待安装包收数验收。
- SQL 使用自身固定滚动窗口；看板日期覆盖器不改变这些 SQL 的窗口。Sentry 默认检查链接使用 7d。

## 运维边界

本轮未创建订阅、通知接收人、自动告警或定时任务，没有更改采集同意、数据保留和公开分享权限。先积累新版基线，再按明确分母与持续窗口设置告警；单次失败、未知终态、样本量不足不直接触发业务红灯。已保存查询不等于客户端采集及送达链路已验收。

## 已建图表及校验

- [01｜新用户引导与配置障碍（7日·生产）](https://us.posthog.com/project/450605/insights/OEM1aRq2)
- [02｜示例与真实素材交付（渲染·保存·发布）](https://us.posthog.com/project/450605/insights/MKW3Cujb)
- [03｜制作结果与失败原因（7日·生产）](https://us.posthog.com/project/450605/insights/52q51Mkw)
- [04｜示例后7日真实出片（成熟设备队列·非安装转化）](https://us.posthog.com/project/450605/insights/XzZK8Afr)
- [05｜自动取景结果与最终采用（7日·生产）](https://us.posthog.com/project/450605/insights/S7FF0GVR)
- [06｜引导决策与模型发现诊断（保存≠连通）](https://us.posthog.com/project/450605/insights/R8M5o8fj)
- [07｜数据覆盖与最近收数（验收·未知环境单列）](https://us.posthog.com/project/450605/insights/2u7biycg)

7 条 SQL 均已在 PostHog 实际运行成功并保存到看板。业务新契约无匹配数据；成熟示例队列为 0/0；覆盖查询可返回版本/环境/契约组合。此为创建时快照，不是持续不变的结论。

Sentry 四个组件已通过 API 读回确认名称、过滤、聚合和分组：异常趋势（2249816）、Studio 阶段（2249817）、版本回归（2249818）、高频问题表（2249819）。默认 7 日过滤已保存，看板已收藏。

[线上 SQL 备份](posthog_queries.json) 为本次看板的准确查询来源；上一轮设计 SQL 保留为设计稿，不保证与线上展示列逐字一致。

PostHog 新看板已固定（Pinned），Sentry 已收藏。页面保存后的截图仅在本地保留，不随仓库公开。
