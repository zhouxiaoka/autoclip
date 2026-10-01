# 1.5.0 快速出片迭代 · 交接文档

> 维护规则：每完成一个工作包、做出一个产品决定、或发现一个坑，就在对应小节更新，并改顶部日期。接手的人先读「现状一页纸」和「待办」，再按需看后面的细节。
>
> 最后更新：2026-10-01（正式发布与 issue 收口）· 分支 `worktree-project-diagnosis`（worktree `.claude/worktrees/project-diagnosis`）。接手基线 `723eefbd` 当时比 `origin/main` 多 69 个提交；本轮已合入 main，**1.5.0 已正式发布为 latest**，固定 tag `v1.5.0` 指向 `e940f5ae`。

## 现状一页纸

- **目标**：贴一个视频链接、选平台 → 自动出可直接发布的成片，每条成片带「发布包」（视频 + 封面 + 各平台标题/简介/话题）。
- **完成度**：后端链路、前端结果页 / 发布包卡片 / 设置页都已实现并有测试；17 条真实素材回归集跑过；demo 成品在 `/private/tmp/autoclip-e2e/demos`（本机临时目录，含测试 key，测完要删）。
- **效果**（详见 [成本与时间](COST_PER_VIDEO.md)）：2 小时访谈从链接到成片 65 分钟 → 有作者字幕 7–8 分钟、云端语音识别 5–18 分钟；模型费用 ¥0.64 → ¥0.02–0.2。
- **测试**：本轮全量与真实 CLI / MCP 结果见 [1.5 验收记录](RELEASE_1_5.md)。前端 198 passed，typecheck / lint / build 通过；Rust 下载回归 5 passed。
- **发布入口**：PR #250 已合入 main，tag `v1.5.0` 固定为 `e940f5ae`，最终 PR / main CI 全绿，后端 1106 passed、2 skipped。双平台构建、签名、安装升级和 CLI/MCP 同源资产已核对，Release 已转为 latest，应用内更新返回 1.5.0。证据见 [验收记录](RELEASE_1_5.md#正式-tag-与交付入口) 与 [Release](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0)。Windows 缺人工界面验收及未完成观察期已在 Release 中明确；官网由负责人更新。

## 负责人已拍板的产品决定（不要擅自改）

| 主题 | 决定 |
|---|---|
| 链路 | 旧的「大纲 / 时间线 / 评分 / 标题」四步，以及 5、7 步，合并为一次挑片（今天的模型上下文足够）。旧项目页链路保留不动 |
| 出片数量 | 自动只渲染评分最高的 10 条，其余为「备选片段」，点击再生成 |
| 字幕语言 | 抖音 / 小红书 / B站：中文或中英双语；原片已有硬字幕就不加。TikTok / Reels / Shorts / YouTube：**全英文**，原片没字幕必须补英文字幕。**任何平台都不能中英混杂**（英文平台不能出现中文标题或字幕） |
| 封面 | 及格线是清晰、没有错人错名牌；目标是有设计感、能提高点击率。**默认用免费的本地设计**；AI 封面需要用户自己选生图服务和模型 |
| 模型推荐 | 选模型的自由交还给用户。内部测试 GPT Image 效果最好，但产品里不推荐具体模型；**产品里不推荐 fal**（推荐位只给赞助商，如 88API、Infistar） |
| 配色 | 产品 UI 按 `DESIGN.md`；成片包装的内容配色按情绪变化，不受 DESIGN.md 限制（负责人确认） |
| 片尾 | 用负责人提供的 1.8 秒动画（源文件在 `design/outro-v5/`）；设置 → 应用有开关，默认开启，编辑自动草稿后导出也继承 |
| 复制文案 | 只留「复制发布文案」，不附 AutoClip 署名；片尾独立保留 |
| 竖版布局 | 默认仍按平台；本版增加「访谈式（人物窗口）/ 播客式（满屏）」选择，平台继续决定语言与规格，CLI / MCP 同步支持 |
| CLI / MCP | 本版接入 1.5 完整一键出片、平台包装及发布包，不仅更新版本号 |
| 发布包 | 1.5.0 随版发布 |

## 迭代过程（按时间）

每一步的细节和验证在 [快速出片重构进度](FAST_OUTPUT_REFACTOR_PROGRESS.md)（包 1–12）和 [链路 V2 计划](PIPELINE_V2_PLAN.md)。

1. **包 1–10（1.4 之后）**：平台策略注册表、Studio v2 数据契约、自动出片 + 平台版本、品牌片尾、追加平台 / 单条重试、埋点、结果页预览、发布按版本路由、渲染资源控制、长素材与说话人取景。
2. **包 11：两套包装模板**。`interview_zh`（抖音 / 小红书：两行标题、4:3 说话人窗口、双语字幕、左下名牌、点评标签），`podcast_en`（TikTok / Reels / Shorts：全屏取景、逐词高亮、hook）。
3. **包 12：切点与风格**。片段结尾落在讲完的句子之后、真实音频停顿处；按内容情绪选配色和动效（7 套）。
4. **链路 V2：按今天的模型能力重做**。
   - 每块模型调用并行（`pipeline/concurrency.py`，默认 4 路，本地模型串行）。
   - 一次挑片（`pipeline/clip_finder.py`）：整段字幕按 60 分钟窗口并行，一次返回片段；时长 60–300 秒（最好 90–180 秒）。
   - 硬件编码（`services/video_encoder.py`）。
   - 自动出 10 条，其余备选；作者上传的 YouTube 字幕直接用，跳过语音识别；包装预取并行。
   - 按项目和阶段记录 tokens 与用时（`core/llm_usage.py` → `metadata/llm_usage.jsonl`）。
5. **成本与时间**实测，写入 [COST_PER_VIDEO.md](COST_PER_VIDEO.md)。
6. **发布包**（`studio/post_copy.py`、`cover_design.py`、`publish_kit.py`，前端 `PublishKit.tsx`）。
   - 各平台文案规则。
   - 本地封面设计：人脸居中裁切、标题条、长英文标题重排。
   - 视觉模型选嘉宾帧，名牌只给确认的嘉宾。
   - AI 封面后台生成，视觉模型核对标题文字。
   - 打包 zip；去发布时带上文案。
7. **新片尾动画**：按输出规格适配，结果缓存。
8. **修 360p 模糊**：YouTube 的 SABR 实验只给 360p 时，换播放器客户端重下到 720p 以上。
9. **回归集**：`benchmarks/fast_output/cases.json`（17 条），脚本 `scripts/fast_output_benchmark.py`，说明见 [FAST_OUTPUT_BENCHMARK.md](FAST_OUTPUT_BENCHMARK.md)。
10. **云端语音识别**：百炼 `qwen-audio-3.1-asr-flash`，8 路并行上传。2h52m 的中文音频从本地 Whisper 23 分钟降到 3.6 分钟；DashScope 连接支持专属接口地址。
11. **字幕规则落地**。
    - 硬字幕检测：取样条带 960×192，忽略左右各 15%（避开台标和 PPT）。
    - 视觉模型 `qwen3-vl-plus` 判断字幕是哪种语言，可以否决（答 none）；判断不了时按标题语言兜底。
    - 包装按「受众看不懂原字幕才加字幕」决定是否加字幕。
    - 英文平台的标题、兜底文案一律不出现中文。
12. **封面质量迭代**。
    - 修模糊：选最清晰的人脸帧并锐化。
    - 修错人：视觉选帧，否则不放名牌。
    - 修 3:4 构图切脸。
    - AI 不再写人名，名牌由我们叠加。
    - 不裁切：按尺寸请求，生成后补边。
13. **生图模型对比**（同一帧、同一提示词，结果在 `demos/_cover-compare/`）：
    - qwen-image 和 Seedream 文字常出错；Seedream 会拦截名人帧。
    - GPT Image 2.5 文字 6/6 全对，每张 22–37 秒。
    - 结论：本地设计和 GPT 最稳。
14. **生图服务接入**。
    - 产品新增 fal 生图接口：`image_api: fal`，地址填 `fal.run` 时自动识别。产品里不推荐。
    - 设置文件遇到未知的 `image_api` 回退为 `auto`，不会让整个设置作废（旧服务器读新设置时曾因此导致全部任务失败）。
    - 封面默认改回本地设计（`cover_enabled: false`），提示文案不点名任何服务。
15. **88API 跑通 GPT Image**：`gpt-image-2.5-flare`，37 秒，1024×1536，标题与名牌正确。
    - 之前不通，是因为 token 在「Claude 官转」分组，没有生图渠道；需要「生图模型」分组的 token。
    - 产品里用 `api88` 预设、自动走 OpenAI images 接口（`https://88api.ai/v1`），无需额外配置。

## 关键代码地图

| 关注点 | 位置 |
|---|---|
| 平台策略（画幅、时长、模板、受众语言） | `backend/services/platform_strategy.py` |
| 一次挑片 / 并行 | `backend/pipeline/clip_finder.py`、`concurrency.py`；接入点 `services/simple_pipeline_adapter.py`（`clips_only`） |
| Studio 主流程 | `backend/services/studio/jobs.py`：`_automatic_drafts`、`produce_variant`、`_prefetch_packaging`、`_burned_caption_language`、`_ensure_source_resolution`、`_fetch_platform_subtitles`、`request_ai_cover` |
| 包装（字幕、翻译、标题、情绪风格） | `backend/services/studio/packaging.py`、`packaging_render.py` |
| 发布包 | `studio/post_copy.py`（`RULES`）、`cover_design.py`（`pick_frame`、`design`）、`publish_kit.py`（`ai_prompt`、`ai_cover`、`kit_zip`） |
| 生图 | `backend/core/image_providers.py`（`generate_image`、`generate_fal`） |
| 模型设置 | `backend/services/ai_model_settings.py`（`image_endpoint` 决定生图走哪种接口） |
| 用量和用时 | `backend/core/llm_usage.py` |
| 硬字幕检测 | `backend/services/studio/burned_subtitles.py` |
| 编码 / 片尾 | `services/video_encoder.py`、`services/output_branding.py`、`backend/assets/outro/` |
| API | `backend/api/v1/studio.py`：`/output-variants/{id}/produce`、`/cover`、`/cover/ai`、`/post`、`/kit` |
| 前端 | `frontend/src/features/studio/PublishKit.tsx`、`OutputVariantCard.tsx`、`StudioResults.tsx`；设置在 `features/settings/` |

## 怎么复现 / 测试

- **单测**：`/Users/zhoukk/autoclip/venv/bin/pytest backend/tests -q`；前端 `cd frontend && npm run typecheck && npm run lint && npm test && npm run build`。
- **端到端**：按 [FAST_OUTPUT_BENCHMARK.md](FAST_OUTPUT_BENCHMARK.md)，用独立数据目录起后端（`nice -n 15`，端口 18765），跑 `scripts/fast_output_benchmark.py --cases ...`。
- **本机 E2E 目录** `/private/tmp/autoclip-e2e`：
  - 数据：`ai-model-settings.json` 配好了百炼（分析 `qwen-plus`、ASR、视觉 `qwen3-vl-plus`）和封面（当前为 88API `gpt-image-2.5-flare`）。
  - 工具脚本：`collect_demos.py`（汇总 demo）、`cover_compare.py`（多模型封面对比）、`set_bailian_models.py` / `set_fal_cover.py` / `set_88api_cover.py`（切换配置）、`cost_report.py`、`try_88api.py`。
  - 日志：`bench1.log`、`bench3.log`。
  - `.env` 是另一个项目的完整环境文件，**只读需要的几项**（`88API_*`、`FAL_KEY`、Ark），不要打印任何 key。
  - 测完要删除整个目录（里面有 key）。
  - 原来的 `settings.json` 已被负责人覆盖，文字模型改由 `ai-model-settings.json` 的百炼连接提供。

## 踩过的坑

- worktree 的守卫会拦复杂 shell 命令：改文件用 Edit 或小 python 脚本。
- 不要动主仓库 checkout 的 WIP；git stash 和其他 worktree 共用，别用裸 `git stash`。
- 设置文件版本向前兼容：新增枚举值要让旧版本能容忍（见 `known_image_api`）。改完后端要**重启测试服务器**，不然旧进程读新设置会报错。
- 并行后，依赖调用顺序的测试会偶发失败：mock 要按内容匹配，不能按调用次序。
- Whisper 词级时间：整份文件里任一词时间重叠，就会整体作废，实测从未产出。要先清洗词时间再接入（已延后）。
- 硬字幕检测灵敏度高了会把台标、PPT 当字幕：靠边缘排除 + 视觉否决解决，调参数后用 Dafoe、DevDay、TIM 三条回归。
- 生图：模型自己写的人名经常错 → 不让模型写名字；裁切会切掉标题 → 按尺寸请求后补边。
- 用户拒绝过整目录 `rm -rf` 重建 demo：重建要就地覆盖或换新目录，删除前先确认。

## 发版前审查（2026-10-01）

做法：gstack `/review`，四个并行审查（正确性与并发、安全、前端与 DESIGN.md、对抗式红队）。本机没有 Codex，所以只有 Claude 一方。前端 QA 用 gstack `/browse` 在测试数据上过了结果页、备选片段、设置页。

已修（提交 `0fc14a61`、`a0108d88`、`3b8088c8`、`6931bc1c` 及之后一笔）：
- **英文平台不再出现中文**。包装、发布文案、横屏 YouTube 字幕和开头、追加平台和备选片段的标题、发布标题兜底、发布包文件名、分享署名，这些路径都会把中文挡掉或重试。回归测试在 `backend/tests/test_english_only.py`。
- **备选片段**：新增 `preparing` 状态，渲染调度看不到它，不会再渲染出没取景、没包装的成片；认领是原子操作，连点两次不会重复准备；准备失败后整次生成状态会收尾，重试会重新准备；服务重启后中断的版本可以重试，不会永远排队；结果页在准备、渲染期间持续刷新。
- **前端**：16:9 缩略图会裁掉竖屏封面，发布包里改为显示完整封面；一键出片项目去掉了打不开的原始切片卡片；AI 封面超时不再提示成功；文案保存后立即显示；标题两行输入时不跳位。
- **稳健性**：
  - AI 生图下载：拒绝本机和内网地址，每次跳转都检查，上限 40 MB。
  - 云端语音识别：单段遇到 429 或 5xx 退避重试，失败后不再继续发送剩余分段。
  - 硬件编码：卡住时回退到软件编码；坏素材不会把硬件编码关掉。
  - 片尾：做失败时交付不带片尾的成片，Windows 字体路径也已修正。
  - 不允许发送画面时不调用 AI 封面，避免模型编出一张脸再挂上嘉宾名牌。
  - 1.4 用户为百炼配的中转地址不再被改写。

负责人已决定并实现：
- **1.4 老用户的 AI 封面**：升级时改回本地设计。`ai_model_settings.cover_choice_version`：1.5 起每次保存都会写入 1；没有这个标记的文件（1.4 写的）读出来时 AI 封面是关闭的，模型保留，在设置里选「AI 生成」后保存即可恢复。
- **原片烧有中文字幕，投英文平台**：模糊掉原字幕带，再加英文字幕。检测时一并记下字幕带的位置（`generation.burned_caption_band`），英文版的 `Draft.caption_mask` 会在任何版式处理前模糊这一条（`render._mask_captions`）；取景和字幕按原片无字幕处理。李诞 × 王祖贤素材上实测：字幕带约占画面高度 74%–98%，原字幕已看不清。模糊块上沿是硬边，需要在真机冒烟时看效果。

延后（影响小，记录在案）：
- 并行包装下，各片段配色避让失效（风格差异变小）。
- 同一条成片的分镜可能混用不同编码器，然后流复制拼接（本机 ffmpeg 7.1 验证可正常解码，打包版 ffmpeg 未验证）。
- 封面设计占用渲染线程，拖慢后续成片。
- 打分弹窗的关闭按钮用的是字符 ×，不是 Icon。

## Codex 验收补充（2026-10-01）

本轮依据负责人反馈修复：重复复制按钮、全局自动片尾及编辑导出继承、横版长字幕分页 / 源时间轴裁切、AI 封面平台流程与任务状态、源视频尾部容错、发布包及下载内存占用。
CLI / MCP 新增完整一键出片入口；默认共享桌面设置、允许独立 demo 数据目录，查询不会把另一制作进程误判为服务重启。
竖版选择已解耦语言，模板缓存按场景 / 版式 / 语言隔离，中文满屏字幕两行分页，英文访谈点评过滤中文。
真实 DevDay 原 case 重新渲染通过；CLI 出 3 条 Shorts，MCP 出中文抖音 + 英文 Shorts 共 6 条，均有视频 / 封面 / 文案 / ZIP 和实际片尾。授权范围与剩余验收见 [RELEASE_1_5.md](RELEASE_1_5.md)。
本轮已修的项不再按下一版待办跟踪；并行配色避让、跨编码器拼接专项验证、封面设计线程优化、反馈关闭图标继续延后。

同事补测发现 **CLI / MCP wheel 漏了人物检测 ONNX**，原包的两种竖版取景回退；源码验收此前未覆盖这个打包缺口。
已补齐模型及 MIT 许可证，新增 CI：从源码目录外安装 wheel，用真实访谈素材重新抽帧并验证两种裁切轨迹。
原包与失败记录单独保留；修复后新安装的模型重新取景、渲染三个 DevDay 样片通过，补测未调用付费模型。
macOS 实际样片还暴露了 CoreText 中文字体匹配问题，已修字体家族名并增加真实 ASS 缺字检查；桌面正式 tag 构建也需要包含这个修复。
Windows 桌面候选已完成覆盖升级，安装后视频测试因检查脚本误用返回字段中断，修正后需重跑；详见 [RELEASE_1_5.md](RELEASE_1_5.md) 的 wheel 阻塞项记录。
复测收尾：代码 `ee73e594` 全量 CI 全绿（1101 passed、2 skipped）；Windows 完整覆盖升级 / 本地视频 / 新安装 wheel 的人物检测与中文字体检查全部通过。
同事应更新到 `dist/autoclip-1.5.0-cli-mcp-test-ee73e594.zip`，同版本必须强制重装；原包记录保留，补测模型费用为零。macOS 桌面新候选的源码为 `e3e57236`，后续提交只把同样的字体名称应用到其他平台，macOS 行为一致；正式 tag 使用最终源码。

## 待办（按顺序）

1. [x] demo 目录已重建（2026-10-01）：10 条素材 42 套成品，封面全部由 88API GPT 生成。
2. [x] 竖屏 AI 封面黑边：GPT Image 2.x 直接按平台比例出图；比例不符时用画面边缘延伸补齐。
3. [x] 前端 QA（`/browse`），问题已修。
4. [x] `origin/main` 没有新提交，无需同步。后端 1032 passed、前端 198 passed，typecheck、lint、build 全部通过；`/review` 已完成（见上节）。
5. [x] 文档收尾：CHANGELOG、COST_PER_VIDEO（云端语音识别数据）、PIPELINE_V2_PLAN 都已更新。
6. [x] 负责人决定的两件事已实现（见上节）。
7. [x] 桌面 / Python / CLI / MCP 版本统一为 1.5.0，候选包与验收说明见 [RELEASE_1_5.md](RELEASE_1_5.md)。
8. [ ] **先问负责人**，再打 tag 出 Pre-release；Windows + macOS 冒烟 → 观察期 → `promote-release.yml` 转正。
9. [ ] 清理测试敏感配置前由负责人确认；本轮按负责人要求不删除 / 提交 `frontend/node_modules` 软链接和 `benchmarks/fast_output/reports/`。新增真实模型验收临时配置在 `/private/tmp/autoclip-1.5-cli-demo`，交付包不含密钥。
10. 延后到下一版：Whisper 词级时间；讲解动画、录屏、分屏带货类模板。

## 2026-10-01 发版收口

负责人已授权补齐客户端埋点后合并 main、打 v1.5.0 并发布；不再重复请求合并/tag 授权。新增流程复核见 [埋点验收](analytics/QUICK_OUTPUT_RELEASE_1_5.md)。正式 tag 构建同步发布 CLI/MCP wheel 和无密钥 ZIP，避免同事继续使用旧候选包。

同事新增 P1（YouTube 长视频无任务却持续 rendering）已修：每个平台先过滤时长资格，再选合格候选前十，分发无任务时明确终态。新增 5 个回归，原 case 03 独立重放与原始费用/失败记录分开；详见 [长视频阻塞项记录](RELEASE_1_5.md#youtube-长视频候选排序发布阻塞项2026-10-01)。旧 `ee73e594` 候选包未包含此修复，正式同事测试须安装最终 tag 的新 wheel。
