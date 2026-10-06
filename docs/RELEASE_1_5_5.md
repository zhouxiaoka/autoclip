# 1.5.5 发布记录（含未公开的 1.5.4）

状态：**负责人豁免发布**。2026-10-06 产品负责人决定：不再补完安装包验收矩阵，直接发布，出问题往前修。此前线上 latest 停在 v1.5.0；1.5.1–1.5.3 保持 Pre-release。

## 为什么是 1.5.5

1.5.4（`90edc851`）通过 Internal Acceptance [37429155325](https://github.com/zhouxiaoka/autoclip/actions/runs/37429155325) 后打了 `v1.5.4` 标签，但 tag 构建 [37429280728](https://github.com/zhouxiaoka/autoclip/actions/runs/37429280728) 在 candidate-gate 被拦：`actions/checkout` 在 tag 事件下用 `+SHA:refs/tags/$TAG` 把带注解标签改写成轻量标签，`tag-run` 读不到 `Internal-Acceptance-Run`。这个门禁加入后从未在真实 tag 上运行过，任何版本都会被拦。`v1.5.4` 标签保留、没有 Release；按不重打同名标签的规则，修复后以 1.5.5 发布。

1.5.5 = `90edc851` + workflow 先强制取回带注解标签 + 版本号。产品代码与 1.5.4 完全相同。

## 修复范围

见 CHANGELOG `[1.5.5]`：云转写失败归因、封面收尾同步、发布简介虚构职务护栏、Windows 静音检测编码、弹窗下拉遮挡、隐私开关慢响应、模型目录缓存写失败、Windows CRT/Whisper、低帧率尾帧与视觉失败终态、Sentry 环境标签、本地超时分类、视觉项目首页状态、统计关闭不初始化、SenseVoice 便携路径、无口播视觉字幕误报，以及 1.5.1–1.5.3 的全部热修。

## 豁免范围

全部 20 个场景、52 条回归和观察期为 `waived`，每行写明现有证据范围（见 `docs/internal-builds/<1.5.5 commit>/internal-acceptance.json` 与 `docs/releases/v1.5.5/acceptance.json`）。豁免不是通过。

已有的真实证据（来自 1.5.4 及更早候选包，产品代码相同或更早）：Mac 当前包干净安装；Mac 1.5.0/1.5.1 覆盖升级与 SQLite 占用恢复、真实云 ASR/视觉/B 站/YouTube 出片；Windows 当前包安装身份、真实 Cloud ASR 转写、持续 500 后同项目重试出片、原生 ZIP 校验。

从未在任何包上完成的：Windows 真实视觉两阶段出片、Windows 真实链接导入、长音频跨块转写、生产包隐私关闭全流程抓包。

## 上线后盯的信号

转正后第一天按以下顺序看，出现集中失败就用 Promote / Halt Release 的 halt 退回 v1.5.0，再发补丁版往前修：

1. Sentry `release:1.5.5 environment:production`：新的高频 issue，特别是 Windows 启动/CRT、SenseVoice/Whisper 准备、SQLite 升级。
2. PostHog `studio_generation_finished`：1.5.5 自动出片成功/失败比与失败码分布，对比 1.5.0 同期；重点看 `provider_error`、`timeout`、视觉路线失败。
3. GitHub `from-app` issue 与 #96：升级后设置丢失、链接导入、Windows 视觉出片的反馈。
