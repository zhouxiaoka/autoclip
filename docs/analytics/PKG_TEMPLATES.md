# HTML 包装模板（`pkg_templates_v1`）

杂志风（editorial）和街头快剪（street）。默认关闭。`autoclip_safe_mode` 打开后回到关闭，除非操作者用 `AUTOCLIP_FLAGS=pkg_templates_v1=on` 明确打开。

没有同意统计时不请求这个开关。事件仍走 `captureBusinessEvent()`，统计关闭后不发送，也不会事后补发。

## 事件

语义已有的计数扩展原事件。模板渲染是新语义，单独一条。

| 事件 | 时机 | 属性 |
|---|---|---|
| `studio_template_render_finished` | 一条成片的模板渲染结束（含降级） | `template`，`encoder`，`downgraded`，`downgrade_reason`，`os`，`cpu_count`，`duration_ms`，`failure_reason`，`outcome`，`strategy_id`，`flow_id` |
| `studio_template_overridden` | 导入前把默认模板改成另一个 | `from_template`，`to_template`，`stage=pre_import`，`flow_id` |
| `studio_generation_finished` | 整次生成结束 | 沿用 `outcome`。另有 `editorial_count` / `street_count` / `classic_count` / `html_downgrade_count`，用来算生成成功和降级率 |
| `studio_output_shared` / `studio_download_*` | 复制文案或下载 | 沿用现有事件，`template` 增加 `editorial` / `street` / `classic` |

`downgrade_reason`：`none` / `over_budget` / `missing_runtime` / `intel_mac_unverified` / `rank` / `flag_off` / `capture` / `encode`。

`failure_reason`：`none` / `capture` / `encode` / `runtime` / `timeout` / `unknown`。不传 ffmpeg 原文、路径或字幕。

`encoder`：`libx264` / `h264_nvenc` / `h264_qsv` / `h264_amf` / `h264_videotoolbox`。

抓帧或编码抛错时，Sentry 用 `phase=packaging_html`，消息里的路径和文案按现有清洗丢掉。

## 看板

查询在 `pkg_templates.sql`。生成成功率看 `studio_generation_finished` 的 `outcome`。渲染 p90 看 `studio_template_render_finished.duration_ms`。改选率是 `studio_template_overridden` 除以带模板的生成。下载和复制沿用 `studio_download_saved` 与 `studio_output_shared`，按 `template` 拆开。

护栏（`pkg_templates_v1`）：生成失败率增加不超过 2 个百分点；渲染 p90 不超过 classic 的 2 倍；包装降级率不超过 10%。

## 1.5.7 接到成片上的范围

导入页在开关打开、并且选了竖版平台时，默认杂志风，可以改成街头快剪或经典包装。得分最高的 3 条自动竖版成片用所选 HTML 模板，叠加层是 ffmpeg 的第二路输入。其余自动竖版记 `rank`，走经典包装。超出自动渲染条数的片段仍是 on_demand，不抓 HTML。

每条成片的时间预算默认 90 秒，`AUTOCLIP_TEMPLATE_BUDGET_SEC` 可改（1–600）。超时、运行时缺失、抓帧失败、编码失败都降到经典，导出不会因为编码器失败。Intel（x86_64）Mac 固定经典，原因 `intel_mac_unverified`。这条路径没有在 Intel Mac 上跑过，标成未验证。

下载和复制文案沿用 `studio_download_*` / `studio_output_shared`。成片结果里有 `template_render` 时，`template` 用实际渲染的 `editorial` / `street` / `classic`。

## 这一版不做

没有播客 HTML 模板。没有智能推荐、`publish_pack_v2`、阻断式质检。贴纸不生成。CLI / MCP 还没有 `--template`。HTML 填充用现有包装字段（标题、字幕，以及已经有的 kicker / emphasis / numbers / gloss）。PostHog 项目里还没有创建这个开关，validation 环境也还没有截图。全量之前默认值保持关闭。
