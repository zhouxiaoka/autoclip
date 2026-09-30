# 1080p60 导出规格（#114）

在切片「导出成片」里选择 **1080p60**，或向 `POST /api/v1/projects/{project_id}/clips/{clip_id}/export` 提交 `preset: "1080p60"`。

- 固定 1920×1080 横屏、60 fps 恒定帧率、H.264（libx264 / CRF 20）、AAC 160 kbps（源视频有音轨时）、MP4 / faststart。
- 等比缩放、居中补黑边，不拉伸或裁掉竖屏画面。此规格不接受 `layout` 覆盖。
- 不限时长；字幕和标题卡开关沿用既有功能。默认预设与流水线原始切片不变。
- 低于 60 fps 的源素材通过重复帧适配；不生成新的运动细节，不进行 AI 插帧。低分辨率素材放大也不会恢复原本缺失的细节。
- Studio 成片从已渲染视频重编码，保留原有文字和声音，不重复叠加字幕/标题。其他 Studio 预设仍沿用既有成片。
- 与其他预设使用独立缓存文件；首次及缓存返回都包含实际探测的 `width` / `height` / `fps` / `video_codec`。

验收：`backend/tests/test_publish_export.py` 用真实 ffmpeg 从竖屏 24 fps 素材导出 1920×1080 / 60 fps / H.264/AAC，并检查一秒视频为 60 帧、原画导出仍为 24 fps、缓存规格一致、Studio 不重复加字。没有捆绑界面语言切换或外部 PR #82。
