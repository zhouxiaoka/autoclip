# 1.5.4 发布记录

状态：**负责人豁免发布**。2026-10-06 产品负责人决定：1.5.4 不再补完安装包验收矩阵，直接发布，出问题往前修。线上 latest 此前停在 v1.5.0；1.5.1–1.5.3 保持 Pre-release。

- 源码：`90edc851b435c4d2bf5bd8fd5a47777183a3c625`（tag `v1.5.4`），内部构建 [37330742634](https://github.com/zhouxiaoka/autoclip/actions/runs/37330742634)，Internal Acceptance [37429155325](https://github.com/zhouxiaoka/autoclip/actions/runs/37429155325)。
- 修复范围见 CHANGELOG `[1.5.4]`：云转写失败归因、封面收尾同步、发布简介虚构职务护栏、Windows 静音检测编码、弹窗下拉遮挡、隐私开关慢响应、模型目录缓存写失败、Windows CRT/Whisper、低帧率尾帧与视觉失败终态、Sentry 环境标签、本地超时分类、视觉项目首页状态、统计关闭不初始化、SenseVoice 便携路径、无口播视觉字幕误报，以及 1.5.1–1.5.3 的全部热修。

## 豁免范围

验收记录：[internal-acceptance.json](internal-builds/90edc851b435c4d2bf5bd8fd5a47777183a3c625/internal-acceptance.json)。只有 Mac `clean_install` 在当前包上完整执行并标为 passed；其余 18 个场景、52 条回归和观察期为 `waived`，每行写明现有证据范围。豁免不是通过。

已有的真实证据（部分来自之前的候选包）：Mac 1.5.0/1.5.1 覆盖升级与 SQLite 占用恢复、真实云 ASR/视觉/B 站/YouTube 出片；Windows 当前包安装身份、真实 Cloud ASR 转写、持续 500 后同项目重试出片、原生 ZIP 校验。

从未在任何包上完成的：Windows 真实视觉两阶段出片、Windows 真实链接导入、长音频跨块转写、生产包隐私关闭全流程抓包。

## 上线后盯的信号

转正后第一天按以下顺序看，出现集中失败就用 Promote / Halt Release 的 halt 退回 v1.5.0，再发 1.5.5 往前修：

1. Sentry `release:1.5.4 environment:production`：新的高频 issue，特别是 Windows 启动/CRT、SenseVoice/Whisper 准备、SQLite 升级。
2. PostHog `studio_generation_finished`：1.5.4 自动出片成功/失败比与失败码分布，对比 1.5.0 同期；重点看 `provider_error`、`timeout`、视觉路线失败。
3. GitHub `from-app` issue 与 #96：升级后设置丢失、链接导入、Windows 视觉出片的反馈。
