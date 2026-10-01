# 快速出片重构进度

本记录在每个独立工作包完成时更新。工作分支：`worktree-project-diagnosis`。主计划：[快速出片与平台策略重构计划](../../../../.claude/plans/nifty-purring-hejlsberg.md)。

## 包 1：平台策略 registry 与旧预设兼容

状态：已完成，待合入。

### 完成内容

- 新增 `backend/services/platform_strategy.py`，作为平台输出策略唯一来源。
- 定义抖音、TikTok、Instagram Reels、YouTube Shorts、YouTube 长视频、B站、小红书和原画策略。
- 明确区分 `youtube_shorts` 与 `youtube_long`：两者可共用 YouTube 传输能力，但画幅、时长和视觉策略不同。
- `backend/services/publish_export.py` 的旧 `PRESETS` 改为 registry 的兼容投影，保留 `douyin`、`xiaohongshu`、`shorts`、`bilibili`、`original` 既有键。
- `backend/services/upload_post_publisher.py` 的旧默认预设判断改为读取 registry，不再维护第二份“竖屏平台”规则。
- 新增 `GET /studio/platform-strategies`，供后续首页平台选择器读取受控策略摘要。
- 新增 registry 单测与 Studio API 回归测试。

### 已验证

```text
/Users/zhoukk/autoclip/venv/bin/pytest \
  backend/tests/test_platform_strategy.py \
  backend/tests/test_publish_export.py \
  backend/tests/test_upload_post_publisher.py \
  backend/tests/test_studio.py -q

124 passed in 72.35s
```

```text
/Users/zhoukk/autoclip/venv/bin/ruff check \
  backend/services/platform_strategy.py \
  backend/tests/test_platform_strategy.py

All checks passed
```

### 兼容边界

- 不改变首页、导入、Studio 确认页或渲染行为。
- 历史发布请求未指定策略时，保持旧行为：含 Upload-Post 竖屏目标时默认 `shorts`，否则原画；B站独立为横屏策略。
- 没有新增账号、credits、自动发布或品牌片尾。

### 下一包

Studio v2 数据契约与自动编排：导入选择平台后，自动完成理解、候选草稿生成和渲染，结果页直接显示 OutputVariant；旧 `awaiting_confirmation` 项目继续兼容原流程。

### 主要风险

- 目前 registry 只统一“规则定义”，尚未让发布系统按不同 OutputVariant 分组上传。
- `youtube_long` 的 3 分钟以上要求是内容资格的软门槛，不能用导出层截断或填充处理；需要在候选生成层实现。
- 后续自动编排必须保证一次多平台请求只做一次理解，且单个 variant 失败不覆盖已完成结果。

## 包 2A：Studio v2 数据契约与兼容状态

状态：已完成，待合入。

### 完成内容

- `ImportOptions` 新增规范化的 `platforms`、显式 `auto_start`、`BrandingOptions`。
- 新增 `OutputVariant` 与 `AppendPlatformsRequest` 类型，为后续不可变交付版本和追加平台 API 准备契约。
- `/studio/import` 接收平台、自动启动和品牌片尾偏好，并将规范化结果写入项目设置与 Studio workspace。
- 新导入的 workspace 写入 `schema_version=2`、`generation` 与空的 `output_variants`；历史 workspace 读取时惰性补默认字段，不做强迁移。
- 仍保持 `auto_start=false` 默认值，筛查完成后继续进入旧的 `awaiting_confirmation` 流程；`generation.status` 与该旧状态同步。
- 修复 `jobs._analyze()` 失败路径的 Python 异常闭包错误：错误消息与诊断在异常作用域内固化，保证失败状态能持久化。

### 已验证

```text
/Users/zhoukk/autoclip/venv/bin/pytest \
  backend/tests/test_smart_import.py \
  backend/tests/test_studio.py \
  backend/tests/test_platform_strategy.py -q

154 passed in 84.65s
```

### 下一包

包 2B：仅在首页新客户端显式传 `auto_start=true` 时，自动从筛查进入理解、候选草稿、平台 variant 和渲染。需增加 output variant 聚合状态、单版本重试和历史确认流兼容回归。

### 主要风险

- 当前 `OutputVariant` 只是数据契约，尚未关联 render job 或用户可见结果卡，不能提前在 API/UI 暴露“追加平台”。
- 自动路径必须把理解、制作和渲染分成可恢复阶段，不能将一次 executor 中断误报为所有结果失败。
- 多平台必须共享理解结果；平台差异只在草稿派生与渲染阶段产生。

## 包 2B-Backend：自动生产、平台 variant 与终态聚合

状态：已完成，待合入。

### 完成内容

- 仅当导入请求显式传 `auto_start=true` 时，筛查完成后直接进入自动生产；旧客户端仍停在 `awaiting_confirmation`。
- 自动路径将一次字幕/视觉理解的候选转为独立的每平台草稿和 `OutputVariant`，并自动提交既有 Studio render job。
- 每个 variant 使用独立 draft ID 和 revision，避免多个平台共享可编辑快照或重试状态。
- 自动路径按策略应用画幅、布局、字幕样式、标题样式与动效默认值。
- 对 YouTube 长视频等长内容策略，候选不足软下限时不渲染、不填充、不拼凑；generation 保留受控 skipped 原因供结果页解释。
- render job 完成/失败会同步到对应 variant；全部完成、部分成功和全部失败分别聚合为 `completed`、`partial`、`failed`。
- 修复自动内容路径的时间解析，支持流水线返回 SRT 时间而非秒数。
- 自动 executor 提交失败会写入可见失败状态，不会永久停在 production。

### 已验证

```text
/Users/zhoukk/autoclip/venv/bin/pytest \
  backend/tests/test_smart_import.py \
  backend/tests/test_studio.py \
  backend/tests/test_platform_strategy.py -q

157 passed in 82.37s
```

### 下一包

前端快速入口和结果页：首页平台选择显式传 `auto_start=true`，新项目不再去确认页；结果页用 OutputVariant 展示自动进度、播放、下载、编辑和失败重试。随后加入品牌片尾的统一 finalization。

### 主要风险

- 当前浏览器页面仍不会传 `auto_start=true`，因此线上默认体验尚未改变。
- 自动多平台任务目前独立编码每个 variant，后续需要策略去重以避免对视觉相同的平台重复渲染。
- 尚未实现追加平台 API、品牌片尾、variant 专用下载入口和跨平台发布按 variant 分组。

## 包 2C：快速入口与自动结果页

状态：已完成，待合入。

### 完成内容

- 首页导入改为选择具体发布平台后直接发送 `auto_start=true`，成功后跳到项目结果页，不再默认进入方案确认页。
- 新增 `PlatformPicker`，从 `/studio/platform-strategies` 读取策略；后端暂时不可用时使用受控 fallback，入口不会消失。
- 默认选择抖音，用户可以多选平台；请求会重复提交 `platforms` form field，后端复用同一次内容理解。
- 快速入口提供默认开启的 `Made with AutoClip` 片尾开关；该开关目前已持久化，实际渲染片尾将在后续 branding 包实现。
- 新增 `OutputVariantCard`，自动版本直接显示生成状态、下载入口和 Studio 编辑入口；自动项目不再显示“继续确认方案”。
- workspace 类型与 API 扩展为 generation、output variants 和平台策略摘要。
- 新增平台选择和自动跳转的前端静态行为测试；八个语言目录补齐快速出片静态文案键。

### 已验证

```text
frontend: npm run typecheck && npm run lint && npm run build
frontend: npm test
backend: 731 passed, 1 skipped
```

构建仍报告已有的 Ant Design/Tauri 动态导入与主 bundle 体积警告，本包未新增该类警告。

### 下一包

品牌片尾与统一 finalization：在 Studio 和 legacy/publish 导出的最终合成阶段各追加一次 1 秒、可关闭的 `Made with AutoClip` 片尾，并为带/不带片尾的输出建立独立缓存与回归验证。

### 主要风险

- UI 已暴露片尾开关，但渲染层尚未消费它；这必须作为下一个包优先完成，不能在发布前停留在“只存设置”。
- 结果卡当前为自动 variant 提供下载/编辑，但尚未有“追加平台版本”与单 variant 重试 API。
- 自动项目的真实桌面端导入、渲染和原生保存还需要在 branding 完成后做端到端冒烟。

## 包 3：可关闭的品牌片尾与统一输出收口

状态：已完成，待合入。

### 完成内容

- 新增 `backend/services/output_branding.py`，在内容视频最终完成后追加一次 1 秒 `Made with AutoClip` 片尾；不叠常驻水印，不在每个镜头重复覆盖。
- 自动平台 variant 的 `branding.outro_enabled` 已传入 Studio render job；旧手动 Studio 导出默认保持不带片尾，避免改变历史行为。
- `ExportRequest.brand_outro` 让 legacy/publish 导出也使用相同 finalization；输出缓存文件名包含 `autoclip-outro-v1`，带/不带片尾不会错误复用。
- 输出合成使用独立 `.branding.part.mp4` 临时文件和原子替换，避免覆盖 Studio 内容渲染的 `.part.mp4`。
- 片尾关闭时只原子移动内容文件，不增加时长；带片尾时保留同画幅、视频与音频 stream，并增加约 1 秒。

### 已验证

```text
backend/tests/test_output_branding.py
backend/tests/test_publish_export.py
backend/tests/test_studio.py

99 passed in 69.03s
```

并新增自动 variant branding 参数传递回归，待全量后端套件完成后一起确认。

### 下一包

追加平台版本与单 variant 重试：复用 ContentProfile/候选草稿，只派生和渲染新增平台，不重新下载、转写或调用内容理解；结果页提供“追加平台版本”和失败版本重试。

### 主要风险

- 片尾目前使用运行时 `drawtext`，还没有专用透明品牌图形资产；视觉设计可在后续包替换资源，但输出语义与缓存版本必须保持稳定。
- legacy/publish API 尚未公开片尾开关，当前只为服务层和自动 variant 接通。
- 仍需进行桌面端真实导入、自动渲染、原生下载与片尾逐帧验收。

## 包 4：追加平台版本与单版本重试

状态：已完成，待合入。

### 完成内容

- 新增 `POST /studio/{project_id}/platforms`：仅对自动项目的已保存草稿派生新平台版本，绝不调用 `run_content()` 或视觉 `analyze()`。
- 新增 `POST /studio/{project_id}/output-variants/{variant_id}/retry`：只重试失败 variant，保留该版本自己的平台策略和片尾设置，已完成版本不变。
- 追加逻辑按“平台策略 + 镜头范围”去重，避免同一内容重复编码成相同平台版本。
- 结果页提供“追加平台版本”面板和失败卡片的“重试这条”，复用现有 platform picker、workspace polling 和项目的片尾偏好。
- 为新增 API、禁止二次理解、partial 状态保留、前端 endpoint 绑定和八语文案键补充回归。

### 已验证

```text
backend: 156 passed
frontend i18n / quick output / variant actions: 11 passed
```

### 下一包

自动输出的可解释性与匿名增长观测：将结果页展示为何选中/为何跳过某平台的受控结构化理由，并补全 material origin、平台版本、片尾与下载/分享的匿名白名单事件。之后进行真实桌面端冒烟。

### 主要风险

- 追加 API 当前从已保存草稿派生，尚未单独标记 ContentProfile 版本；后续理解策略升级时要加 analysis version 以判断能否复用。
- 多平台派生仍逐个编码，策略等价时的共享渲染可作为性能优化，不应在可靠性工作包中提前合并。
- 尚未实现系统分享、案例征集与远端公开链接，当前增长能力仍是品牌片尾与可直接下载的成片。

## 包 5：可解释性与匿名增长观测

状态：已完成，待合入。

### 完成内容

- 自动结果页在素材不足以生成长内容时显示受控原因，例如“未生成 YouTube：素材没有足够完整的长内容”，不暴露内部策略 ID、模型输出或素材文本。
- Studio analytics schema 升级到 v2，新增且仅允许：平台策略枚举、素材来源枚举、平台/variant 数量、片尾开关、受控 generation reason 与复用理解布尔值。
- 快速入口记录平台数量和片尾开关；结果页只在自动 generation 到 `completed/partial/failed` 时本地去重上报一次聚合结果。
- 追加平台与单版本重试复用既有 request lifecycle 埋点，追加明确带 `reused_content_profile=true`，不上传 project/variant/draft ID。
- 增加隐私白名单回归，断言 project ID、文件名、URL、自由理由与未知策略不会进入 payload；旧 Studio 去重与 consent 行为继续覆盖。

### 已验证

```text
frontend analytics / i18n / quick output: 33 passed
frontend typecheck: passed
```

### 下一包

真实桌面端端到端验收：从新首页导入受控素材，选择平台，验证自动出片、片尾、原生保存、追加平台、失败版本重试与关闭分析统计。验收前先启动本地桌面运行时或等价的开发环境。

### 主要风险

- 当前“分享/案例征集”尚未落地，不能把品牌片尾展示次数解释为真实外部传播。
- 浏览器下载只表示下载请求；成功交付率仍以桌面原生保存为主证据。
- 全部新版指标需要在独立 validation 环境和真实安装包中验证收数，不能从本地测试推断线上已生效。

## 包 6：结果页真实成片预览

状态：已完成，待合入。

### 完成内容

- 自动 variant 完成后，结果卡直接播放 immutable render job 的真实 MP4，不再只显示占位图。
- 排队/失败版本继续显示稳定状态占位，完成后自动切换为视频播放器。
- 保留下载、Studio 编辑和单版本重试入口；预览不新增后端截图缓存。
- 增加静态回归，确认完成 variant 使用 `/studio/{project}/exports/{job}/video`。

### 已验证

```text
frontend: npm run typecheck
frontend: npm run lint
frontend: npm run build
frontend: npm test
```

全部通过。构建继续保留既有动态导入和主 bundle 体积警告。

### 下一包

发布路径按 variant 路由：Upload-Post/B站发布时选择正确的短竖版或横版长视频输出，不再将一个文件盲目发给所有平台。

## 包 7：发布路径按 variant 路由

状态：已完成，待合入。

### 完成内容

- Upload-Post 与 B站发布请求新增可选 `output_variant_id`。传入时直接复用该版本已完成的不可变 MP4，不再调用 `export_clip` 重新导出；未传时保持旧的 clip/preset 导出行为。
- 新增 `studio.publishing.output_variant_meta()`：只接受状态为 completed 且有 render job 的 variant，缺失或未完成返回 404 语义错误。
- 新增 `platform_strategy.incompatible_transport_platforms()`：横版 variant（YouTube 长视频、B站、原画）不能发给只收竖屏的 TikTok / Instagram，发布前明确报错，不会发出请求。
- B站只接受 `bilibili` 策略的 variant；其他策略 variant 在 B站入口报“请选择 B站横版成片版本”。
- 发布记录与返回结果写入 `output_variant_id` 与 `strategy_id`，便于后续按版本统计投递。
- 结果卡为完成的 variant 增加“发布”入口，跳到 `/project/:id/publish/studio-{job}?variant=&strategy=`；发布页把 variant 传给 Upload-Post，仅当策略是 B站时才传给 B站，否则 B站继续走旧的横版重导出。

### 已验证

```text
backend: 740 passed, 1 skipped
frontend: npm run typecheck && npm run lint && npm run build && npm test（163 passed）
```

### 下一包

真实桌面端端到端验收（包 5 记录的清单）与七个非中文语言目录的新文案正式翻译。

### 主要风险

- 多平台一次发布仍只能选一个 variant；从一个竖版 variant 同时勾选 B站时，B站会走旧导出重新生成横版，而不是自动挑选同项目的 B站 variant。后续可在发布页按平台自动匹配同内容的其他 variant。
- 竖屏平台清单目前只包含 TikTok 与 Instagram；如 Upload-Post 平台规格变化需同步 registry。

## 包 8：真实素材验收发现的出片上限 bug 与渲染资源控制

状态：已完成，待合入。

### 发现经过

第一轮内部 E2E 用真实素材（WIRED 小岛秀夫 17 分钟、YC Sam Altman 39 分钟）走自动出片。系统按内容分别挑出 8 条和 15 条版本，但两条项目都在提交第 4 个渲染时失败：旧的“单项目同时最多 3 个导出任务”规则把自动生成整体判为 failed，其余版本永久停在排队。同时两路 ffmpeg 合计约 880% CPU，风扇明显。

### 完成内容

- 删除单项目 3 个导出任务的上限。成片数量只由素材内容决定；所有自动版本一次进入渲染队列，按顺序完成。重复提交同一草稿快照仍由既有去重返回同一任务。
- 新增 `jobs.render_executor`（单 worker）：同一时刻全机只做一个本地编码，素材筛查与理解仍用原有线程池，不会排在渲染队列之后。
- 新增 `backend/services/render_limits.py`：ffmpeg 解码、滤镜图与编码线程上限为 CPU 核数的 1/3（至少 2），并以低优先级运行（POSIX 用 `nice -n 10`，Windows 用 BELOW_NORMAL；不使用多线程下不安全的 `preexec_fn`）。
- 追加平台与单版本重试改走同一派发函数，不再因并发上限报错。
- 结果卡对尚未轮到的版本显示“排队生成中”。
- 测试：20 个版本全部进入队列且幂等；ffmpeg 参数有上限且不使用 `preexec_fn`；测试环境下 `render_executor` 跟随测试替换的 executor，避免后台线程串测。

### 已验证

```text
backend: 742 passed, 1 skipped
frontend: typecheck / lint / build / test（163 passed）
```

### 仍待验收

- 用新代码重跑两条真实素材，确认 8 / 15 条全部完成、CPU 占用与耗时可接受，并抽帧检查画幅与片尾。
- 17 分钟素材产出 8 条抖音版本是否偏多，需要结合成片质量判断候选筛选阈值。

## 包 9：片尾时间戳、平台真实时长规则与原片字幕检测

状态：已完成，待合入。

### 完成内容

- 片尾：Studio 成片视频时间基为 1/16000，旧片尾按 ffmpeg 默认参数编码，stream copy 拼接后 30 帧挤进约 2 ms，播放器只剩 1 秒静音。现在片尾读取正片的时间基、帧率和音频参数后编码；新增测试断言片尾帧跨度约 1 秒，并用真实成片复验。
- 平台时长（负责人决定：内容完整优先，只有平台硬限制才截断）：registry 拆分 `recommended_max_duration_sec`（建议值，不截断）与 `max_duration_sec`（平台硬上限）。抖音、TikTok、Reels、小红书无硬上限；YouTube Shorts 硬上限由过时的 60 秒改为 180 秒，超出时在最后一个字幕句末截断，结果卡说明原因。旧发布导出不再把抖音/小红书截到 90 秒。
- 原片自带字幕：新增本地检测 `studio/burned_subtitles.py`（不调用 OCR、不上传画面），抽 12 帧画面下部，识别“亮字 + 暗描边且随时间变化”的区域，固定台标不会误判。检测到时，自动版本不再叠加 AutoClip 字幕，竖版裁切布局改为完整画面 + 模糊背景，避免切掉原字幕。结果按项目缓存，追加平台复用。
- 真实素材校准：WIRED 小岛秀夫原片 12 帧文字占比 0.6%–1.0%、相邻帧重合≈0 → 判定有字幕；YC Sam Altman 原片 ≤0.16%、右下角台标未误判 → 判定无字幕。阈值 0.4%。

### 已验证

```text
backend: 752 passed, 1 skipped
frontend: typecheck / lint / test（163 passed）
```

### 仍待验收

- 用新代码重跑小岛秀夫，确认 8 条全部完成、无双层字幕、片尾可见、CPU 可接受。
- 竖版模糊背景里仍会出现被放大模糊的原字幕虚影；若观感不佳，可加大背景模糊或压暗。

## 包 10：长素材、取景与资源控制补强

状态：已完成，待合入。

- 去掉筛查阶段 2 小时上限（Dario × Dwarkesh 2h22m 曾被直接拒绝）；字幕路线分块理解、按小时扩展条数；视觉逐帧分析保留 2 小时费用上限，超出自动改走字幕路线。
- 自动竖版接入按说话人取景（YuNet + 口型运动）：原片无烧录字幕且有人脸时裁成真竖屏，无人脸镜头逐镜头回退完整画面；OpenCV 在导入时后台按需安装；失败或未就绪不阻断出片。
- 模糊背景改为 1/8 尺寸模糊 + 压暗到约 35%，消除原字幕放大虚影并降低 CPU。
- 取景切镜检测、抽帧、整片预览转码与旧发布导出全部接入 `render_limits`（线程上限 + 低优先级），渲染线程上限降到核数 1/4。
- 修复自动生成/追加/重试写入 running 状态缺少进程标识、被误报“服务已重启”的问题。
- yt-dlp 改为 `yt-dlp[default]`（带 YouTube JS 校验组件 yt-dlp-ejs），并把本机可用的 deno/node/bun/quickjs 全部交给 yt-dlp；Studio 下载路径同样启用，并记录原视频标题与频道供名牌核对。

真实验收：Dario 2h22m → 37 段 × 抖音 + B站 = 74 个版本全部进入队列并顺序渲染；37 个抖音版全部使用说话人取景。

风险：用户机器没有任何 JS 运行时时，YouTube 链接仍可能失败；后续考虑随包内置 QuickJS。

## 包 11：自动包装模板（中文访谈式 / 英文播客式）

状态：已完成，待合入。

### 完成内容

- 平台策略新增 `template` 与 `audience_language`：抖音、小红书 = `interview_zh`；TikTok、Reels、Shorts = `podcast_en`；B站、YouTube 长视频保持横版。
- `Draft.packaging`：标题两行、受众语言字幕与原文、名牌、评论标签、英文高亮词、降级标记；新增 `window` 布局。
- `studio/packaging.py`：每段内容 + 模板一次模型调用，只发送该草稿用到的字幕行；逐项校验，名牌只采用字幕或原视频标题/频道里出现过的人名；任何异常回退原字幕与草稿标题，不阻断出片。
- `studio/packaging_render.py`：逐场景 ASS（随包 Noto Sans SC，libass `fontsdir`），访谈式为暖近黑画布 + 4:3 跟随说话人窗口 + 固定两行标题（第二行强调蓝）+ 窗口底边中文字幕与原文 + 字幕上方评论标签 + 进度线；播客式为全屏 9:16 跟随说话人 + 1–3 词逐词高亮字幕 + 开头 hook。两者共用左下两层名牌（蓝色竖条，人物首次说话时滑入，不跨场景重播，不压脸）。
- 原片自带字幕：不画字幕层，访谈窗口改为完整 16:9 适配。
- 结果卡显示模板名与降级提示；Studio 对模板草稿只开放两行标题与评论标签开关，隐藏不再生效的字幕/片头/语言设置，保存时原样保留包装。
- 配色按负责人决定严格使用 DESIGN.md 暗色主题与品牌蓝。

### 已验证

```text
backend: 776 passed, 1 skipped（新增 test_packaging / test_packaging_render / test_auto_framing 扩展）
frontend: typecheck / lint / build / test（169 passed）
产品渲染器用 Sam Altman 真实片段分别渲染访谈式与播客式，抽帧确认名牌在左下、标签在字幕上方、Sam/Garry 切换正常。
```

### 下一步

- 播客式可选“上下分屏”版式（上全景、下说话人特写），需在取景检测中增加同框人数判断。
- 讲解动画、屏幕录制类包装：下一阶段结合生成式 AI。

## 包 12：切点落在完整表达与真实气口，包装按内容情绪变化

状态：已完成，待真实素材复验与合入。

### 发现经过

10 支 demo 验收：结尾常停在半句（"It seems like"）或带进下一个问题；逐行估算的切点仍会多出几百毫秒下一句（02、03）；日语源原片烧了英文字幕，抖音版缺中文字幕；包装样式单一。

### 完成内容

- `studio/boundaries.py`：切点先对齐完整句（行内句末直接切、无标点转写才用停顿判断、日语敬体句末、去掉结尾处只起了个头的下一个问题），再可选让文字模型挑“问题开头 / 回答讲完”的行，结果仍经规则校验。
- 用 ffmpeg silencedetect 对齐真实气口：切点只接受与前后文字语速相符的停顿（不会把“It seems like”之后的停顿当成句末）；句末没有停顿（说话人直接接下一句）则顺延到下一个带明显气口的完整句，最多 10 秒，且不越过下一个问题；紧接着出现 ≥1.2 秒长停顿时顺延到这段表达结束。开头可回溯 20 秒到问题的第一句，且不会被推进首个词。
- 包装：外语源 + 原片外语字幕仍生成受众语言字幕（放在窗口下方）；同语言字幕直接用原字幕行保证与声音同步；cinematic 改为 2–5 词一行。
- 模板多样性：版式骨架固定，模型返回内容情绪 `mood`（calm / serious / bold / warm / playful），按情绪在匹配的 7 套内容配色（azure / amber / coral / mint / lemon / rose / lilac）和样式中按片段种子挑选：不同片段各不相同，同一片段在各平台一致。内容配色不受产品 UI 的 DESIGN.md 约束（负责人决定）；浅色强调色的标签用深色字。

### 已验证

```text
backend: 973 passed, 2 skipped（test_boundaries 17 项，含真实 ffmpeg 停顿检测）
10 支 demo 真实素材切点逐条对照音频停顿：02 停在 "responsible." 后的停顿，03 延到 "diffusion." 后，08 延到长停顿（段落结束）。
```

### 下一步

- 有 ASR 词级时间戳时，字幕与切点改用真实词时间。
- 第二批 demo：中文源（TIM × 罗永浩）→ 抖音，不翻译。
