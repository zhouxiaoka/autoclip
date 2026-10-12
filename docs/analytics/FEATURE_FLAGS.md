# 功能开关

新界面默认关闭（1.5.7 起剪辑风格 `pkg_templates_v1`、风格卡片 `pkg_template_picker_visual` 和 `mcp_v2_tools` 例外，默认打开）。只有用户打开「设置 → 应用 → 匿名使用统计」时，桌面端才会向 PostHog 请求开关。统计关闭、没有配置 key、或请求失败时，每个开关都用 `frontend/src/analytics/flags.defaults.json` 里的安全默认值。

## 取值顺序

1. 本机覆盖：只在开发构建的「设置 → 应用 → 实验功能」里。正式包不显示这一节，避免用户误触。覆盖只存在这台电脑。
2. `autoclip_safe_mode` 为开时，其余新功能回到默认关闭。本机对某一个开关的覆盖仍然优先。`qa_gate_blocking` 例外：安全模式把它强制为 `off`，压过本地覆盖。
3. 统计开启时，使用已经加载的 PostHog 值，并写入 7 天本机缓存。
4. 开发构建里的 `VITE_FLAGS`（`name=value`，逗号分隔）。正式包忽略。
5. 统计开启且没有更新的远程值时，使用未过期的缓存。
6. 构建默认值。

统计关闭时不读取缓存，也不调用 `getFeatureFlag` / `reloadFeatureFlags`。关闭统计会暂停已初始化 SDK 的开关轮询。

## 按版本定向

每次开关请求都带 `app_version`：在 SDK 的 `loaded` 回调里（早于第一次开关请求）以及重新打开统计、重新拉取开关之前，调用 `setPersonPropertiesForFlags({ app_version })`，同时 `register` 为事件超级属性。值来自 `VITE_APP_VERSION`（默认取 `src-tauri/tauri.conf.json` 的 version），去掉前缀 `v`，格式是 `1.5.7` 这种 `主.次.补丁` 字符串，可以直接用 PostHog 的 semver 运算符，例如发布条件 `app_version` `>= (semver)` `1.5.7`。注意：桌面端是 `person_profiles: 'identified_only'`，匿名用户没有人物档案，这个属性只在开关求值时生效，不会写进人物档案；所以要在开关的发布条件里直接按人物属性 `app_version` 过滤，不要做成 cohort，cohort 匹配不到匿名用户。

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
| `qa_gate_blocking` | `shadow` | `off` 不跑；`shadow` 和 `block` 都只记录。1.5.7 不拦截成片 |
| `pkg_templates_v1` | `true`（1.5.7 起） | 剪辑风格（杂志风、街头快剪、经典） |
| `pkg_template_picker_visual` | `true`（1.5.7 起） | 导入页用三张卡片预览剪辑风格（封面和预览视频随安装包打包，离线可用；预览加载失败时显示静态封面）。关闭时是文字选择器 |
| `mcp_v2_tools` | `true`（1.5.7 起） | MCP 暴露 `cancel_job` 和 `list_styles`。关闭时工具列表里没有这两项 |

`import_drop_zone` 和 `track_overrides` 不在产品方案的开关表里。方案写 Q9 不需要开关；这次任务要求每一项都有默认关闭的开关，所以修改埋点也先关着。拖放区是导入页改版，单独一个开关，避免和「粘贴即开始」绑死。

`qa_gate_blocking` 按方案第 10.2 节先全量 shadow。构建默认值是 `shadow`，不是关闭。`block` 会被收下，但这一版和 `shadow` 一样只写报告。打开 `autoclip_safe_mode` 时，这一项一律变成 `off`，并且压过本地覆盖，也压过 `AUTOCLIP_FLAGS`：环境变量写了 `qa_gate_blocking=shadow` 或 `block` 仍然是 `off`。前端其他开关仍是本地覆盖优先；只有这一项，安全模式压过本地覆盖。

1.5.7 起 `pkg_templates_v1`、`pkg_template_picker_visual` 和 `mcp_v2_tools` 默认打开（`true`），剪辑风格、导入页风格卡片和 MCP 新工具对所有用户可用；关掉 `pkg_template_picker_visual` 时导入页改用文字选择器，风格照样能选。三个开关都保留：PostHog 远程值为 `false`（含 7 天缓存）、本机覆盖为关闭、或 `AUTOCLIP_FLAGS=pkg_templates_v1=off,mcp_v2_tools=off` 都能把它们关回去。因此 PostHog 里这些开关不能只定向内部人群，否则其他开了统计的用户会拿到 `false`（W157-F6）；应加一条按 `app_version` 定向 1.5.7 及以上为打开的发布条件。统计关闭、没拉到远程开关、缓存过期时用构建默认值，也就是打开。打开 `autoclip_safe_mode` 后它们一律回到关闭（`SAFE_OFF` 表，前后端各一份），不是回到构建默认值，除非 `AUTOCLIP_FLAGS` 明确写了对应的 `=on`。本地覆盖仍然优先于安全模式；统计关闭时不会向 PostHog 请求这些开关。`mcp_v2_tools` 只影响 MCP 工具列表，不改变桌面导入页。事件契约见 [MCP / CLI 工具调用](MCP_TOOLS.md)。

推荐、雷达、关注频道、手机交接这些开关还没有对应实现，没有放进默认表。

## 后端

导入请求可以带 `features` JSON。后端只保留已知键，非法值丢弃，结果写进 `generation.features`。CLI、MCP 和 Docker 没有 PostHog SDK，读环境变量 `AUTOCLIP_FLAGS`（同样的 `name=value` 列表），它覆盖请求里的同名键。`autoclip_safe_mode` 打开后，其余键回到安全关闭值（多数就是默认值；默认打开的风格开关为 `false`），除非 `AUTOCLIP_FLAGS` 明确设置了那一项。两条例外要分开看：`qa_gate_blocking` 在安全模式下一律写成 `off`，即使 `AUTOCLIP_FLAGS` 点名了它；`pkg_templates_v1` 和 `mcp_v2_tools` 默认打开，安全模式把它们关回 `false`（不是默认值），除非 `AUTOCLIP_FLAGS` 写了 `pkg_templates_v1=on`。

## 还没做

- 没有在 PostHog 项目里创建这些开关，也没有在 validation 环境截到真实请求。全量之前默认值保持关闭，所以未创建远程开关不影响当前用户。
- 没有把 B1–B6 的开关接进产品。
