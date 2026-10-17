# 成片卡片

Q5、Q6、Q7。默认全部关闭。统计关闭时不发这些事件，也不请求开关。

## 开关

| 开关 | 默认 | 打开后 |
|---|---|---|
| `publish_pack_v2` | `separate` | `combined` 时卡片上一个动作：复制文案（带出处行）、保存视频和封面。小红书封面按 3:4 显示 |
| `render_top_first` | `limit10` | `top3` 时每个平台自动只做得分最高的 3 条，并先渲染得分最高的一条。没有得分的草稿仍然全部渲染 |
| `clip_reasons` | `false` | 每张卡片一行选片理由 |

`limit10` 保持现在的前 10 条。分组只有在开关被真正赋值（本机覆盖、远程、开发变量或未过期缓存）之后才发新事件。

## 和方案的差别

- 封面地址本来就会返回小红书的 3:4 设计图。之前卡片把它缩成约 56px 的缩略图，zip 里才是完整封面。这次在 `combined` 下把同一张图按 3:4 摊开，不另做一套封面。
- 普通「复制发布文案」仍然不附加出处行。出处行只加在合成动作上。
- 系统分享、AirDrop、二维码交接没有做，所以 `share_target` 没有加上 `system_share`、`airdrop`、`qr_handoff`。
- 选片理由用片段上已有的 `recommend_reason`（内容切片）或画面 `evidence`（高光）。没有时用取景说明，再没有就用一句固定的「按内容完整度选出这段」。整次导入的方案理由不复制到每张卡片上。这句话只显示在本机，不进入事件。
- `studio_first_clip_ready.ttfc_ms` 用 `generation.created_at` 到渲染任务的 `finished_at`。下载、转写、分析没有单独的阶段时间戳，所以不填 `stage_ms_download`、`stage_ms_transcribe`、`stage_ms_analyze`。有渲染耗时才填 `stage_ms_render`。
- 没有在 PostHog 里创建远程开关，也没有 validation 环境的真实事件截图。默认关闭，未进实验的设备不发新事件。

## 事件

| 事件 | 何时 | 属性 |
|---|---|---|
| `studio_output_shared` | 点「复制文案并保存视频和封面」并且复制成功，且 `publish_pack_v2` 已赋值 | `share_target=copy_and_save`，以及已有的 `strategy_id`、`template`、`packaging_style` |
| `studio_download_requested/saved/failed` | 同一次保存 | `artifact_type=combined`；小红书另有 `cover_3x4` |
| `studio_first_clip_ready` | 观察器看到第一条成片完成，且 `render_top_first` 已赋值 | `ttfc_ms`、`strategy_id`、`template`、`stage_ms_render` |
| `studio_output_rated`、既有下载事件 | `clip_reasons` 不新增事件 | 用评分和下载率对比 |

查询见 `ux_results.sql`。
