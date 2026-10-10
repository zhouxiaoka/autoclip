# MCP / CLI 工具调用

`mcp_tool_called` 在每次工具调用结束时发一条。任务进入终态时再发一条 `mcp_job_finished`。同一次终态（同一个任务 id、成败和错误码）只发一次。发送成功之后才把哈希写入应用目录的 `mcp-events-seen.json`，内容不含任务 id；发送失败不记，下次还可以再发。进程重启后不会把已经发送成功的同一次终态再发一遍。发送放进后台队列，调用方不等待网络返回。进程退出时最多再等 2 秒把队列发出去。

没有 PostHog 项目 key，或数据目录 `privacy.json` 里 `analytics` 为 false 时，两条都不发。`distinct_id` 用本机已经记下的匿名 ID（`analytics.json`；还没有时才生成一次）。这和成片质检用的是同一个开关。

## 属性

只发下面这些。不发路径、文件名、密钥、参数原文或错误句子。

| 属性 | 取值 |
|---|---|
| `tool` | 已知工具名，不认识的记 `other` |
| `client` | 客户端名字，只保留短 token；路径和空值记 `unknown`。CLI 记 `cli` |
| `version` | 当前安装的包版本 |
| `duration_ms` | `mcp_tool_called` 是这次调用的毫秒数。`mcp_job_finished` 是任务从开始到结束的毫秒数。最大 3600000 |
| `ok` | 成败 |
| `error_code` | `none` / `unknown` / `interrupted` / `failed` / `cancelled` / `invalid_input` / `disabled` / `timeout` |
| `$feature/mcp_v2_tools` | 这次进程读到的开关，默认 false |

`completed` 和 `partial` 记 `ok=true`、`error_code=none`。查不到任务是 `unknown`，不发 `mcp_job_finished`。

## 开关

`mcp_v2_tools` 默认关闭。`cancel_job` 和 `list_styles` 只在它打开时注册。打开 `autoclip_safe_mode` 后它回到关闭，除非 `AUTOCLIP_FLAGS=mcp_v2_tools=on`。这个开关不改变桌面导入页。

PostHog 项目里还没有创建这个开关，也没有为这两条事件建看板。
