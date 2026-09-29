# AutoClip

## Design System
做任何视觉/UI 决策前，先读 `DESIGN.md`。所有配色、字体、间距、圆角、状态表达、按钮样式都以它为准。
未经明确同意不要偏离。代码审查时，发现不符合 `DESIGN.md` 的实现要标出来。

方向一句话：**克制专业 / Calm Premium（参考 Dia Browser）**——安静、留白多、近乎全单色、只用一个克制的蓝做强调。不要玩具撞色、彩色 chip、紫色渐变、霓虹、死黑。

## Roadmap
产品长期规划见 `ROADMAP.md`（账号 / 埋点 / 商业化分阶段）。当前阶段与现状见 `HANDOFF.md`。公开社区看板见 `docs/COMMUNITY_BOARD.md`（Discussions 收想法，Issue 只收已确认需求）。

## 发版
所有发版严格按 `RELEASE_CHECKLIST.md`：问题先分级（S1 热修 / S2 进周版 / S3 排计划）；常规版每周最多一版；打 tag 只出 Pre-release，Windows + macOS 真机冒烟和观察期通过后，才用 `promote-release.yml` 转正推给所有用户；坏版本用同一 workflow 的 halt 撤回，再发补丁版往前修。不要跳过 Pre-release，不要重打同名 tag。
