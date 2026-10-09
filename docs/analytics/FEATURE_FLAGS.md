# 功能开关

新界面默认关闭。只有用户打开「设置 → 应用 → 匿名使用统计」时，桌面端才会向 PostHog 请求开关。统计关闭、没有配置 key、或请求失败时，每个开关都用 `frontend/src/analytics/flags.defaults.json` 里的安全默认值。

## 取值顺序

1. 本机覆盖：设置 → 应用 → 实验功能，只存在这台电脑。
2. `autoclip_safe_mode` 为开时，其余新功能回到默认关闭。本机对某一个开关的覆盖仍然优先。
3. 统计开启时，使用已经加载的 PostHog 值，并写入 7 天本机缓存。
4. 开发构建里的 `VITE_FLAGS`（`name=value`，逗号分隔）。正式包忽略。
5. 统计开启且没有更新的远程值时，使用未过期的缓存。
6. 构建默认值。

统计关闭时不读取缓存，也不调用 `getFeatureFlag` / `reloadFeatureFlags`。关闭统计会暂停已初始化 SDK 的开关轮询。

读取远程值只用已经加载的 `getFlagVariants()`，辅助函数自己不会发起请求。

## 这一批开关

| 开关 | 默认 | 打开后 |
|---|---|---|
| `autoclip_safe_mode` | `false` | 其余新功能关闭 |
| `remember_platforms` | `false` | 记住上次的平台 |
| `one_click_paste_start` | `button` | `autostart` 时粘贴即开始 |
| `link_import_without_whisper` | `false` | 链接导入不等待本地转写 |
| `notify_on_done` | `false` | 完成通知 |
| `publish_pack_v2` | `separate` | `combined` 时复制并保存 |
| `render_top_first` | `limit10` | `top3` 时只自动做前 3 条 |
| `clip_reasons` | `false` | 卡片上的选片理由 |
| `hide_legacy_entrypoints` | `false` | 隐藏旧流程入口 |
| `import_drop_zone` | `false` | 首页居中拖放区 |
| `track_overrides` | `false` | 记录用户对自动决定的修改 |

`import_drop_zone` 和 `track_overrides` 不在产品方案的开关表里。方案写 Q9 不需要开关；这次任务要求每一项都有默认关闭的开关，所以修改埋点也先关着。拖放区是导入页改版，单独一个开关，避免和「粘贴即开始」绑死。

模板、质检、雷达、关注频道、手机交接这些开关还没有对应实现，没有放进默认表。

## 后端

导入请求可以带 `features` JSON。后端只保留已知键，非法值丢弃，结果写进 `generation.features`。CLI、MCP 和 Docker 没有 PostHog SDK，读环境变量 `AUTOCLIP_FLAGS`（同样的 `name=value` 列表），它覆盖请求里的同名键。`autoclip_safe_mode` 打开后，其余键回到默认值，除非 `AUTOCLIP_FLAGS` 明确设置了那一项。

成片卡片（Q5–Q7）的行为和事件见 [UX_RESULTS.md](UX_RESULTS.md)。

## 还没做

- 没有在 PostHog 项目里创建这些开关，也没有在 validation 环境截到真实请求。全量之前默认值保持关闭，所以未创建远程开关不影响当前用户。
- 没有把 B1–B6 的开关接进产品。
