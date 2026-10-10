# 成片质检（shadow）

1.5.7 只记录，不拦截。成片状态写成 `completed`、封面收尾之后，渲染线程才把检查放进后台队列。子进程以低优先级运行（Windows `BELOW_NORMAL`，其他系统 `nice -n 10`），硬上限约 12 秒，超时会杀掉整个进程组。检查失败、超时或抛错都不改文件、不改任务状态。

## 开关

| 开关 | 取值 | 这一版 |
|---|---|---|
| `qa_gate_blocking` | `off` / `shadow` / `block` | 构建默认 `shadow`。`block` 与 `shadow` 相同，只记录 |
| `autoclip_safe_mode` | 布尔 | 打开后强制 `qa_gate_blocking=off`，前端本地覆盖也不能把它留开 |

## 事件

后端在写完报告后发一条 `studio_qa_checked`。关着窗口、Docker、CLI、MCP 也会发。没有项目 key，或 `privacy.json` 里 `analytics` 为 false 时不发。属性是五项结果，不是五条事件：

| 属性 | 取值 |
|---|---|
| `qa_avsync` / `qa_face` / `qa_loudness` / `qa_jitter` / `qa_ending` | `pass` / `fail` / `skip` |
| `qa_*_bucket` | 下表里的桶，没有原始测量、路径或文案 |
| `qa_mode` | `shadow` |
| `duration_ms` | 整份报告花了多少毫秒 |
| `strategy_id` | 已有平台枚举 |
| `runtime` | `python` |
| `studio_schema_version` | `2` |

检查器抛错时，Sentry 用 `phase=qa`。上报前只留检查器名，`before_send` 去掉路径和原文。

## 阈值

响度单独 3–5 秒（按成片时长，60 秒约为 4.8 秒）。其余检查更短。合计不超过 11.5 秒，父进程在 12 秒杀掉子进程。超时记 `skip` / `timeout` 或 `budget`。

| 检查 | 通过 | 失败桶 |
|---|---|---|
| 音画同步 | 输出音频和源音频对应段的互相关：中位偏移和段间漂移都 ≤ 40 ms | `40_80` / `80_200` / `gt200` |
| 挡脸 | 字幕或标题和检测到的脸没有重叠 | `lt10` / `10_40` / `gt40`（占脸的比例） |
| 响度 | 综合响度 −14 ± 1 LUFS，真峰值 ≤ −1 dBTP。只解码音频（`-vn -sn -dn`） | `quiet_1_3` / `quiet_gt3` / `loud_1_3` / `loud_gt3` / `peak` / `peak_and_level` |
| 抖动 | 取景路径每分钟来回闪跳不超过 1 次，且静止镜头位移 RMS ≤ 0.30 px | `flash` / `rms` / `flash_and_rms` |
| 结尾 | 词还剩超过 80 ms 算切在词中；句末没有标点且 0.6 秒内还有下一个词，算切在句中 | `mid_word` / `mid_sentence` |

没有可对齐的源音频时，容器 `start_time` 差在 40 ms 以内记 `skip` / `start_only`，不算通过。差得更大仍按上面的失败桶记。没有音频、没有检测器、没有词时间、文件读不了，分别记 `no_audio` / `no_detector` / `no_words` / `unreadable`，不算失败。

## 这一版没做

- 不阻断、不重渲、不降级到经典模板，成片卡片上也不显示质检徽章。
- BGM 低于对白 15–18 LU 还没做。
- 结尾气口和淡出还没查。
- 成片内部的剪切点还没查（`ending.py` 只看整段的起点和终点）。
- 抖动采样是 96×54，一个采样像素大约是成片上 11 像素，测不到 0.30 px 的晃动。
- 挡脸只抽 3 帧，字幕框是按版式估的，还没对着杂志风和街头快剪的实际画面核对。
- 文件大小和文案忠实度不在这五个检查里。
