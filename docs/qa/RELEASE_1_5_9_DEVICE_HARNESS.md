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

（本文件仍是操作提纲。2026-11-06 装包 `001acd8e` 的已证、待证和阻断见 [RELEASE_1_5_9_ACCEPTANCE_REMEDIATION.md](RELEASE_1_5_9_ACCEPTANCE_REMEDIATION.md)。下表不是通过结论。）

| 项 | 平台 | 包 | 源 SHA | 结果 | 日期 |
|---|---|---|---|---|---|
| A1-5 | macOS arm64 | DMG `f58f98f9…da7e28b5` | `001acd8e` | 重启与 screening 现场已见到；遥测是 production，不是 validation | 2026-11-06 |
| A1-5 | Windows x64 | EXE `9adb59b0…` | `001acd8e` | 重启已见到；`crash_stage=idle` 根因未证；当时 Sentry 不可核验 | 2026-11-06 |
| A1-6 | macOS arm64 | 同上 | `001acd8e` | 仅空闲 Cmd+Q 写出 `user_quit`；活动中的「仍然退出」待证 | 2026-11-06 |
| A1-6 | Windows x64 | 同上 | `001acd8e` | `CloseMainWindow` 写出 `user_quit`；不是托盘确认 | 2026-11-06 |
| A2-5 | macOS arm64 | 同上 | `001acd8e` | `source_not_found` 与 `source_blocked` 已见到；主按钮是「选择已登录的浏览器」 | 2026-11-06 |
| A2-5 | Windows x64 | 同上 | `001acd8e` | 两条 URL 都是 `connection/ingest`；缺 yt-dlp 原文，未改分类 | 2026-11-06 |
| A3-5 | 双平台 | 同上 | `001acd8e` | 未测：没有真实零余额 key | 2026-11-06 |
