# 1.5.9 真机验收占位（A1-5 / A1-6 / A2-5 / A3-5）

装包后在 Windows x64 + macOS arm64 各跑一次。记录：包哈希、源 SHA、OS。

## A1-5 杀后端进程
1. 开始制作中 `taskkill /F /PID <python>` 或 `kill -9`。
2. 壳自动拉起 → 首页「应用刚重启」+ 重试。
3. PostHog validation：`studio_generation_finished` 带 `restart_reason=crash`、`crash_exit`、`crash_stage`。
4. Sentry validation：一条 `service_restarted`（fingerprint 含 crash_exit × crash_stage）。

## A1-6 正常退出
Cmd+Q / 托盘「仍然退出」→ `restart_reason=user_quit`，Sentry 不收。

## A2-5 unexpected 命名（装包）
用会触发 Unsupported URL / 坏 recommend 的链接导入 → 失败卡为有名码（非「请重试」），反馈带 `unexpected_type` 枚举。

## A3-5 额度预检
88API 余额为 0 的 key 导入 → 门口提示余额不足 +「去充值」；充值 / 换 key 后测试连接通过，重试可用。

（本文件仍是操作提纲。2026-11-06 装包 `001acd8e` 的已证、待证和阻断见 [RELEASE_1_5_9_ACCEPTANCE_REMEDIATION.md](RELEASE_1_5_9_ACCEPTANCE_REMEDIATION.md)。2026-11-07 新 Mac 包 `653f8f54` 的实机结果见 [RELEASE_1_5_9_MAC_653F8F54.md](RELEASE_1_5_9_MAC_653F8F54.md)。下表不是把整包写成通过。）

| 项 | 平台 | 包 | 源 SHA | 结果 | 日期 |
|---|---|---|---|---|---|
| A1-5 | macOS arm64 | DMG `f58f98f9…da7e28b5` | `001acd8e` | 重启与 screening 现场已见到；遥测是 production，不是 validation | 2026-11-06 |
| A1-5 | Windows x64 | EXE `9adb59b0…` | `001acd8e` | 14:24 重启已见到且 `crash_stage=idle`；补采同一 instance 有 idle（旧 30 秒）和 analyze。源码已修写盘滞后，此包装包未含该修复，也没有新的强杀链 | 2026-11-06 |
| A1-6 | macOS arm64 | 同上 | `001acd8e` | 仅空闲 Cmd+Q 写出 `user_quit`。活动中的「仍然退出」未测：本会话窗口不能截图、不能送键 | 2026-11-06 |
| A1-6 | Windows x64 | 同上 | `001acd8e` | 阻断：需要交互桌面。AMSI 拦住托盘 helper。早先 `CloseMainWindow` 不是托盘。源码审查未发现「退出应用」绕过 QuitGuard | 2026-11-06 |
| A2-5 | macOS arm64 | 同上 | `001acd8e` | `source_not_found` 与 `source_blocked` 已见到；主按钮是「选择已登录的浏览器」 | 2026-11-06 |
| A2-5 | Windows x64 | 同上 | `001acd8e` | 两条 URL 都是 yt-dlp `timed out` → `connection`/`ingest`，卡片误用模型服务文案。源码已改下载句；此包未含该修复。没有 unavailable/sign-in 原文 | 2026-11-06 |
| A3-5 | 双平台 | 同上 | `001acd8e` | 未测：没有真实零余额 key | 2026-11-06 |
| A1-5 | macOS arm64 | DMG `ee65b388…baeb786` | `653f8f54` | 证据已入库 `docs/qa/evidence/653f8f54/`。杀前 hb stage=screening、pid=31788、age 0.042s。恢复字段与卡片一致。PostHog/Sentry 由 parent 按同秒 production 字段独立核 | 2026-11-07 |
| A1-6 | macOS arm64 | 同上 | `653f8f54` | 对话框与 `user_quit` 已见到，但是 fixture-assisted。只复查了 `PYTHON-FASTAPI-5Z` 的 last seen，不是全域 Sentry 无事件 | 2026-11-07 |
| A2-5 | macOS arm64 | 同上 | `653f8f54` | PARTIAL。YouTube 直连是 `source_not_found`。套接字挂起后下载器超时，中英页面有下载句。项目页仍有「模型设置」。没有 sign-in 原文 | 2026-11-07 |
| #565 | macOS arm64 | 同上 | `653f8f54` | PARTIAL。`doubao-seedream-5-0-flash-260915` 的保存接口 422 且含「生图」，但界面没有把该 id 选进槽位。readiness 不是 `image_model_in_analysis` | 2026-11-07 |
| A3-5 | macOS arm64 | 同上 | `653f8f54` | 未测 | 2026-11-07 |
