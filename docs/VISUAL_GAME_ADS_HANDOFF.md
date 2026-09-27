# 视觉理解与买量视频功能开发隔离

- 功能分支：`codex/visual-game-ads`
- 基线：`aaf863bb`，创建分支时 main 的已提交版本。
- 工作目录：`/Users/zhoukk/.codex/worktrees/visual-game-ads/autoclip`
- 范围：Seed 视觉理解、游戏高光检索、广告创意编排、可配置语言/字幕、应用内编辑预览、后台渲染（当前确定性 FFmpeg；复杂包装按质量需要再扩展）。
- 其他功能：未带入原工作区中未提交的 Sentry、国际化、更新器、分析统计或其他改动。
- 已完成统一成片工作区和可配置视觉模型首版，详见 [实现说明](UNIFIED_STUDIO_IMPLEMENTATION.md)；1.4 发布进度以 [发布计划](RELEASE_1_4.md) 为准。

后续代码修改、测试与提交只在本 worktree 进行。以 [应用内交互与语言配置](GAME_AD_EDITOR_INTEGRATION.md) 和 [多模态接入计划](MULTIMODAL_HIGHLIGHTS_PLAN.md) 为实施依据。

现有媒体和字体已复制到本地 worktree，忽略入 Git；原目录保留已交付样片，确保历史视频链接可用。工程依赖的本地资产不随 Git 克隆自动出现，应按样片 README 准备。API 密钥没有复制或提交；已授权的开发调用可读取 `/Users/zhoukk/autoclip/.env`，不得输出其中密钥。
