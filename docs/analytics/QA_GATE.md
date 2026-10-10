# 成片质检（shadow）

1.5.7 只记录，不拦截。渲染把成片写成 `completed` 之后，`studio/qa/` 才跑检查，结果写在 `OutputVariant.qa` 和同一条任务上。检查失败、超时或抛错都不改文件、不改任务状态。

## 开关

| 开关 | 取值 | 这一版 |
|---|---|---|
| `qa_gate_blocking` | `off` / `shadow` / `block` | 构建默认 `shadow`。`block` 与 `shadow` 相同，只记录 |
| `autoclip_safe_mode` | 布尔 | 打开后强制 `qa_gate_blocking=off` |

## 事件

观察器从工作区里已经写好的报告补报 `studio_qa_checked`。每条检查一次，按任务或版本去重。属性只经过 `safeStudioProperties`：

| 属性 | 取值 |
|---|---|
| `qa_checker` | `avsync` / `face` / `loudness` / `jitter` / `ending` |
| `qa_outcome` | `pass` / `fail` / `skip` |
| `qa_bucket` | 下表里的桶，没有原始测量、路径或文案 |
| `qa_mode` | `shadow` |
| `duration_ms` | 这一项花了多少毫秒 |
| `strategy_id` | 已有平台枚举 |

检查器抛错时，Sentry 用 `phase=qa`。上报前只留检查器名，`before_send` 去掉路径和原文。

## 阈值

每项单独最多 1 秒，五项合计最多 3 秒。超时记 `skip` / `timeout` 或 `budget`。

| 检查 | 通过 | 失败桶 |
|---|---|---|
| 音画同步 | 音视频 `start_time` 差的绝对值 ≤ 40 ms | `40_80` / `80_200` / `gt200` |
| 挡脸 | 字幕或标题和检测到的脸没有重叠 | `lt10` / `10_40` / `gt40`（占脸的比例） |
| 响度 | 综合响度 −14 ± 1 LUFS，真峰值 ≤ −1 dBTP | `quiet_1_3` / `quiet_gt3` / `loud_1_3` / `loud_gt3` / `peak` / `peak_and_level` |
| 抖动 | 取景路径每分钟来回闪跳不超过 1 次，且静止镜头位移 RMS ≤ 0.30 px | `flash` / `rms` / `flash_and_rms` |
| 结尾 | 词还剩超过 80 ms 算切在词中；句末没有标点且 0.6 秒内还有下一个词，算切在句中 | `mid_word` / `mid_sentence` |

没有音频、没有检测器、没有词时间、文件读不了，分别记 `no_audio` / `no_detector` / `no_words` / `unreadable`，不算失败。

## 这一版没做

- 不阻断、不重渲、不降级到经典模板，成片卡片上也不显示质检徽章。
- 音画同步只比较成片里音视频流的起始时间，没有做方案里的逐段 ORB 对齐。
- 挡脸用现有的 YuNet，抽几帧；没有 `occupiedRects`。检测器没装就跳过。
- 文件大小和文案忠实度不在这五个检查里。
