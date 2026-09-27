---
workflow: general-video
flow: automation
storyboard: no
message: "看清障碍，预判下一步，想亲自试一次跑酷。"
destination: vertical-short-ad-preview
aspect: 1080x1920
language: zh-CN
length: 22s
narration: no
---

## Intent
用户要求实际跑出几条样片。沿用已讨论的一主两开头变体；直接渲染本地视频，作为内容与制作评审。渲染已由本次用户请求授权，不重复询问。

## Assets
- assets/gameplay.mp4：用户提供的 jzccuci8znM，源片 226.5–248.5 秒连续片段，包含原声音轨。
- assets/chinese.woff2：本地字体子集，仅用于本机样片预览。
- assets/gsap.min.js：固定版本 3.14.2。

## Customizations
三个版本只改变首 3.2 秒的文案。竖屏裁切保留人物、障碍和操作反馈。保留原声音轨，不调用配音。用户后续授权使用 .env 配置，已调用 Seed Pro 2.1 对 11 张按时间排序的抽帧做视觉复核；不是完整视频时序理解。

## Notes
Seed 已在本次制作脚本中调用，尚未接入产品后端；样片尚未验证投放表现。游戏画面原速连续，不虚构失败或通关。创作设置为本次默认，不写入个人偏好。
