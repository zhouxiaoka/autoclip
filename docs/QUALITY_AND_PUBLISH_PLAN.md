# 出片质量工程化 × 产出物可直接发布 — 方案与推进

> 2026-09-07 起草并开始实施。状态见文末「推进记录」；日常进度以 `HANDOFF.md` 为准。

两条线一起看，因为它们共享同一个事实：**用户看到的不是「流水线跑成功」，而是切出来的东西能不能直接用**。
#59 里那句「一个 5 分钟的视频，剪出来三个视频每个 2 分钟，几个大章节都识别不出来」把两件事都说完了——
边界切得不对（质量），切出来也只是素材（发布）。

---

## 一、诊断：现在的流水线为什么会出这些片

读完 `backend/pipeline/step1–6` 与 `prompt/*.txt`，问题不在模型，在工程：

| # | 现象 | 根因 | 代码位置 |
|---|---|---|---|
| 1 | 5 分钟视频切出 3×2 分钟；长视频切得还行 | 提示词按 60 分钟播客写死：「硬性最小 90 秒」「目标 3–6 分钟」「30 分钟块提取 2–5 个话题」。**没有任何地方感知视频总时长**，短视频被硬套长视频参数 | `prompt/时间点.txt` 时长控制节；`prompt/大纲.txt` 数量控制节；`step1_outline.py:67` 固定 30 分钟分块 |
| 2 | 边界落在句子中间 / 早了几秒 | (a) 时间戳完全由 LLM 「算」，程序只做块内 clamp，不对齐字幕 cue；(b) `-ss` 放在 `-i` 前 + `-c:v copy` → 起点吸附到前一个关键帧，GOP 大时可提前数秒 | `step2_timeline.py:_parse_and_validate_response`；`video_processor.py:159–168` |
| 3 | 切片为 0（#11） | 三处「一错全丢」：评分返回数量与输入不等 → 整块丢弃；全部低于 0.7 → 0 片；JSON 解析失败 → 跳过块。没有任何兜底 | `step3_scoring.py:97–99`、`:160` |
| 4 | 评分不准 | 评分只看 `outline` + 要点列表，不看转写原文；「传播潜力」这种维度靶子太虚 | `step3_scoring.py:85–92`、`prompt/推荐理由.txt` |
| 5 | 选了「知识 / 商业」类型没区别 | 桌面端 `SimplePipelineAdapter` 从不传 `prompt_files`，`prompt/<category>/` 目录形同虚设 | `simple_pipeline_adapter.py:122,146,154` |
| 6 | 重叠 / 重复片段 | 各块独立定位，跨块无去重；同块内 LLM 也可能返回重叠区间 | `step2_timeline.py:182–208` 只排序 |
| 7 | 改了提示词不知道变好还是变坏 | 没有回归集、没有指标、LLM 输出不可复现 | — |

结论：**先把「程序能做的事」从 LLM 手里拿回来**（算时长、对齐边界、去重、兜底），再谈提示词与模型。

---

## 二、线 1：出片质量工程化

### 目标
- 5 分钟视频出 3–6 条 30–90 秒的片；60 分钟播客出 6–12 条 2–6 分钟的片（时长自适应）
- 每条片的起止都落在字幕 cue 边界，不切半句
- 「切片为 0」只在字幕为空时发生；其余情况至少保底 top-K
- 任何提示词 / 阈值改动都能在回归集上跑出数字

### 分期

**A. 时长画像（DurationProfile）** — `backend/pipeline/quality.py`
- 从 SRT 总时长算出 tier：`short`（< 8 min）/ `medium`（8–30）/ `long`（> 30）
- 每个 tier 给一组参数：`min_clip_sec / target / max_clip_sec / topics_hint / min_keep / max_clips`
- 生成一段中文「本次任务参数」追加到 step1 / step2 提示词末尾，**覆盖**提示词里写死的 90 秒 / 3–6 分钟
- 写入 `metadata/duration_profile.json`，后续步骤与质量报告复用

**B. 程序化校正（clip_refiner）** — 同文件，纯函数、可单测
1. 起点吸附到最近 cue 的 `start`、终点吸附到最近 cue 的 `end`（±3 s 内取最近，否则取包含点的 cue）
2. 时长下限：沿 cue 向后延到 `min_clip_sec`，撞到下一段或视频末尾就停；仍不够 → 与相邻段间隔 < 5 s 时合并，否则丢弃
3. 时长上限：按 cue 边界截到 `max_clip_sec`
4. 去重：按起点排序，重叠 > 较短者 50% → 合并（保留前者 outline，拼接 content）；小重叠 → 后者起点推到前者终点所在 cue
5. 重新编号；输出 `metadata/quality_report.json`（吸附偏移分布、合并 / 丢弃条目与原因、时长分布）
- 接入点：`run_step2_timeline` 末尾（所有调用方——桌面 / Celery / CLI——都经过这里）

**C. 评分兜底 + 类别提示词**
- 数量不匹配时按 `outline` 文本对齐，对不上的给 0.5 + 「未评分（自动兜底）」，不再整块丢
- 选片：`>= threshold` 的全留；不足 `min_keep` 时按分数补齐并标 `selected_by: "fallback"`；超过 `max_clips` 时按分截断
- 评分输入加入该段转写原文（截断到 ~600 字），让分数落在内容上而不是标题上
- `SimplePipelineAdapter` 读项目 `video_category` → `get_prompt_files(category)` 传给各步

**D. 回归集与指标** — `backend/eval/`
- `LLMClient` 增加录制 / 回放：`AUTOCLIP_LLM_CACHE_DIR` 设了就按 `sha1(prompt+input)` 落盘 / 读盘；CI 里只回放，零 API 费用、结果可复现
- `eval/cases/<name>/{input.srt, expect.json}`：`expect.json` 写约束而不是标准答案——片数区间、时长区间、最小覆盖率、`must_not_zero`、（可选）人工标的黄金区间
- `eval/metrics.py`：片数 / 时长分布 / 覆盖率 / 边界与黄金区间的平均偏移 / 零片率 / 兜底触发率
- `python -m backend.eval` 跑全部 case，打印表格 + 写 `eval/reports/<date>.json`；`--live` 真调模型并录制
- 首批 case：由维护者用本机 3 条不同长度的视频（75 s / 3 min / 8 min）录制；用户视频不进仓库，只进 `.gitignore` 掉的 cache

**E.（后续）** Step 3 评分后端可插拔（接纳 #75 思路），ASR 可插拔（#67），基于回归集做提示词 A/B。

---

## 三、线 2：产出物「可直接发布」

### 目标
用户拿到的是能直接上传抖音 / 小红书 / Shorts / B 站的成片，不用再进剪映一次。

### 原则
- **默认流水线不变**（仍出 16:9 原始切片，快）；发布导出是**按需、单条**，用户点了才编码
- 一个 ffmpeg 调用出一个成片，filter graph 由代码拼，不引入 MoviePy 之类的重依赖
- 预设即规格包：画幅 / 分辩率 / 时长上限 / 字幕样式 / 是否标题卡

### 分期

**A. 导出服务** — `backend/services/publish_export.py`
- 帧精确：`-ss` 前置快速定位 + `libx264 veryfast crf 20` + `aac 160k` + `+faststart` 重编码（同时解决线 1 的关键帧吸附问题）
- 竖屏 9:16 两种版式：`blur`（原片等宽居中 + 高斯模糊放大底）、`crop`（居中裁切）；`none` 保持 16:9
- 烧字幕：从项目 SRT 切出片段区间、平移时间、写临时 SRT → `subtitles=` filter + `force_style`（字号 / 描边 / 底部边距按预设）
- 标题卡：`drawtext` 前 4 秒显示 `generated_title`（`textfile=` 规避转义），半透明底条
- 字体：mac 用 `PingFang SC`，Linux / Docker 装 `fonts-noto-cjk`，Windows `Microsoft YaHei`；找不到时退回 `sans-serif` 并在结果里提示
- 预设：`douyin` / `xiaohongshu`（1080×1920 blur）、`shorts`（1080×1920 crop，≤ 60 s 时提示）、`bilibili`（1920×1080 重编码 + 字幕）、`original`（仅帧精确重编码）
- 输出到 `output/exports/{clip_id}_{preset}.mp4`，幂等（同参数已存在直接返回）

**B. 入口**
- API：`POST /projects/{id}/clips/{clip_id}/export`（后台线程，返回 job）、`GET /projects/{id}/exports/{job_id}`、`GET /projects/{id}/exports/{job_id}/download`
- CLI：`autoclip export <project_id> --preset douyin [--clip 2 --clip 5] [--no-subtitles] [--no-title]`
- MCP：`export_clip(project_id, clip_id, preset, ...)`

**C. 桌面端** — `ClipCard` 的占位「投稿」换成「发布导出」：`Dialog` 里 `Segmented` 选预设、开关字幕 / 标题卡，`ProgressLine` 显示进度，完成后一个 `Btn` 下载。全部用 `frontend/src/ui` 原语，按 `DESIGN.md`。

**D.（后续）** 说话人居中裁切（人脸检测轨迹 + 平滑），封面图（高能量帧 + 标题），多平台直传（B 站已有半成品）。

---

## 四、验收

| 项 | 怎么验 |
|---|---|
| 5 分钟视频不再出 2 分钟片 | eval case `short-*`：片数 3–6，时长 20–150 s |
| 边界对齐 | `quality_report.snap_offsets` p90 < 0.5 s；人工抽看 5 条无半句 |
| 零片率 | eval 全部 case `clips >= min_keep`；`fallback_rate` 有数但不为 100% |
| 发布导出 | 三个预设各导一条：ffprobe 分辩率正确、字幕可见、标题卡前 4 秒出现、时长与元数据一致（±0.1 s） |
| 不伤旧路径 | 现有 139 条单测 + docker-smoke 全绿；默认导出仍是 stream copy 的 16:9 |

---

## 五、推进记录

- 2026-09-07：方案起草并落地线 1 A–D、线 2 A–C。
  - 已合入：`backend/pipeline/quality.py`，step1/2/3 与 `SimplePipelineAdapter` 接入；LLM 缓存；`backend/eval`（`short-synthetic` 绿）；`publish_export.py` + API/CLI/MCP + ClipCard Dialog。
  - 单测 149 过（含 `test_quality` / `test_publish_export`）；frontend `tsc` 干净。
  - 未做：真 5 分钟视频对照、竖屏预设人工看片、说话人跟踪、封面图。
