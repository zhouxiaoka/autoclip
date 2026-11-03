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

（本文件为 harness 记录位；真机结果填入下方）

| 项 | 平台 | 包哈希 | 源 SHA | 结果 | 日期 |
|---|---|---|---|---|---|
| A1-5 | | | | 待补 | |
| A1-6 | | | | 待补 | |
| A2-5 | | | | 待补 | |
| A3-5 | | | | 待补 | |
