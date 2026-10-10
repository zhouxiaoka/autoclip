# HTML 包装模板（`pkg_templates_v1`）

杂志风（editorial）和街头快剪（street）。默认关闭。`autoclip_safe_mode` 打开后回到关闭，除非操作者用 `AUTOCLIP_FLAGS=pkg_templates_v1=on` 明确打开。

没有同意统计时不请求这个开关。事件仍走 `captureBusinessEvent()`，统计关闭后不发送，也不会事后补发。

## 事件

语义已有的计数扩展原事件。模板渲染是新语义，单独一条。

| 事件 | 时机 | 属性 |
|---|---|---|
| `studio_template_render_finished` | 一条成片的模板渲染结束（含降级） | `template`，`encoder`，`downgraded`，`downgrade_reason`，`os`，`cpu_count`，`duration_ms`，`failure_reason`，`outcome`，`strategy_id`，`flow_id` |
| `studio_template_overridden` | 导入前把默认模板改成另一个 | `from_template`，`to_template`，`stage=pre_import`，`flow_id` |
| `studio_generation_finished` | 整次生成结束 | 沿用 `outcome`。后续接入会补 `editorial_count` / `street_count` / `classic_count` / `html_downgrade_count`，用来算生成成功和降级率 |
| `studio_output_shared` / `studio_download_*` | 复制文案或下载 | 沿用现有事件，`template` 增加 `editorial` / `street` / `classic` |

`downgrade_reason`：`none` / `over_budget` / `missing_runtime` / `intel_mac_unverified` / `rank` / `flag_off`。

`failure_reason`：`none` / `capture` / `encode` / `runtime` / `timeout` / `unknown`。不传 ffmpeg 原文、路径或字幕。

`encoder`：`libx264` / `h264_nvenc` / `h264_qsv` / `h264_amf` / `h264_videotoolbox`。

抓帧或编码抛错时，Sentry 用 `phase=packaging_html`，消息里的路径和文案按现有清洗丢掉。

## 看板

查询在 `pkg_templates.sql`。生成成功率看 `studio_generation_finished` 的 `outcome`。渲染 p90 看 `studio_template_render_finished.duration_ms`。改选率是 `studio_template_overridden` 除以带模板的生成。下载和复制沿用 `studio_download_saved` 与 `studio_output_shared`，按 `template` 拆开。

护栏（`pkg_templates_v1`）：生成失败率增加不超过 2 个百分点；渲染 p90 不超过 classic 的 2 倍；包装降级率不超过 10%。

## 还没接到界面上的部分

这一层先固定事件形状和开关。渲染耗时、编码器、降级原因要等抓帧和成片接入之后才会真正发出。PostHog 项目里还没有创建这个开关，validation 环境也还没有截图。全量之前默认值保持关闭。
