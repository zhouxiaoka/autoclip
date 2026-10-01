# 1.5.0 快速出片迭代 · 交接文档

> 维护规则：每完成一个工作包、做出一个产品决定、或发现一个坑，就在对应小节更新，并改顶部日期。接手的人先读「现状一页纸」和「待办」，再按需看后面的细节。
>
> 最后更新：2026-10-01 · 分支 `worktree-project-diagnosis`（worktree `.claude/worktrees/project-diagnosis`），相对 `main` 72 个提交，**尚未合入、尚未发版**。

## 现状一页纸

- **目标**：贴一个视频链接、选平台 → 自动出可直接发布的成片，每条成片带「发布包」（视频 + 封面 + 各平台标题/简介/话题）。
- **完成度**：后端链路、前端结果页 / 发布包卡片 / 设置页都已实现并有测试；17 条真实素材回归集跑过；demo 成品在 `/private/tmp/autoclip-e2e/demos`（本机临时目录，含测试 key，测完要删）。
- **效果**（详见 [成本与时间](COST_PER_VIDEO.md)）：2 小时访谈从链接到成片 65 分钟 → 有作者字幕 7–8 分钟、云端语音识别 5–18 分钟；模型费用 ¥0.64 → ¥0.02–0.2。
- **测试**：后端 1015 passed（最后两处后端修复前跑的全量；这两处的针对性测试已通过，合并前需要再跑全量）；前端 192 passed。
- **下一步**：前端 QA → 同步 `main` → `/review` → 升版本号 1.5.0 → 按 `RELEASE_CHECKLIST.md` 出 Pre-release（**打 tag 前要问负责人**）→ 负责人做双平台冒烟 → promote。

## 负责人已拍板的产品决定（不要擅自改）

| 主题 | 决定 |
|---|---|
| 链路 | 旧的「大纲 / 时间线 / 评分 / 标题」四步，以及 5、7 步，合并为一次挑片（今天的模型上下文足够）。旧项目页链路保留不动 |
| 出片数量 | 自动只渲染评分最高的 10 条，其余为「备选片段」，点击再生成 |
| 字幕语言 | 抖音 / 小红书 / B站：中文或中英双语；原片已有硬字幕就不加。TikTok / Reels / Shorts / YouTube：**全英文**，原片没字幕必须补英文字幕。**任何平台都不能中英混杂**（英文平台不能出现中文标题或字幕） |
| 封面 | 及格线是清晰、没有错人错名牌；目标是有设计感、能提高点击率。**默认用免费的本地设计**；AI 封面需要用户自己选生图服务和模型 |
| 模型推荐 | 选模型的自由交还给用户。内部测试 GPT Image 效果最好，但产品里不推荐具体模型；**产品里不推荐 fal**（推荐位只给赞助商，如 88API、Infistar） |
| 配色 | 产品 UI 按 `DESIGN.md`；成片包装的内容配色按情绪变化，不受 DESIGN.md 限制（负责人确认） |
| 片尾 | 用负责人提供的 1.8 秒动画（源文件在 `design/outro-v5/`） |
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

## 待办（按顺序）

1. [ ] demo 目录用最新结果和 88API GPT 封面重建，告诉负责人路径。
2. [ ] 前端 QA（gstack `/qa` 或 `/browse`）：发布包卡片、备选片段生成、导出发布包、设置页封面来源默认值、88API 生图。
3. [ ] 同步 `main` 并解决冲突，后端全量测试 + 前端四件套，`/review`。
4. [ ] 文档收尾：CHANGELOG 去掉任何对 fal / 具体生图模型的推荐；COST_PER_VIDEO 补上云端语音识别的数据；PIPELINE_V2_PLAN 补上最终状态。
5. [ ] 升版本号到 1.5.0。**先问负责人**，再打 tag 出 Pre-release；负责人做 Windows + macOS 冒烟 → 观察期 → `promote-release.yml` 转正。
6. [ ] 删除 `/private/tmp/autoclip-e2e`。
7. 延后到下一版：Whisper 词级时间；讲解动画、录屏、分屏带货类模板。
