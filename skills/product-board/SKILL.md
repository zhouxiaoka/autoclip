---
name: product-board
description: >-
  维护 AutoClip 的公开社区看板。当用户要看社区反馈、整理功能呼声、把一条讨论放进路线图、
  或问 GitHub Discussions、Projects、Quackback、Featurebase 该怎么接时使用。
  想法留在 Discussions，只有人确认后才开 Issue。
---

# AutoClip 产品看板

规则的正文在 `docs/COMMUNITY_BOARD.md`。商业化阶段仍以 `ROADMAP.md` 为准，当前工程状态以 `HANDOFF.md` 为准。

## 先读再动

1. 跑 `python3 scripts/feature_signals.py --days 30 --json`。
2. 用语义把讨论收成几条需求。脚本里的用词重叠只是提示。
3. 对照已有 `status:*` Issue，标出重复。
4. 给出排序和「建议停在哪一列」。不要在这一步创建 Issue。

## 什么时候可以写 GitHub

只有人明确说「放进某一列」或「开成 Issue」才写。

- 可以建议 Exploring 或 Researching。
- Planned、Building、Testing、Shipped 必须使用人说出的那一列，不能自己升级。
- 合并 PR 不算 Shipped。发版说明里写了才把卡移到 Shipped。

晋升时按 `docs/community/issue-body.md` 写正文，打 `feature` 和对应 `status:*`，加入名为 **AutoClip Roadmap** 的 Project，并回原讨论帖。

## 不要做的事

- 不要把 Q&A 和能复现的 bug 混进路线图。bug 用现有 bug 模板。
- 不要为了看板去部署 Quackback、Featurebase 或 Linear。触发条件写在 `docs/COMMUNITY_BOARD.md`。
- 不要编造票数。没有反应数时就说没有。
- 飞书表单和应用内反馈可以出现在周报里，不能直接变成路线图卡片。
