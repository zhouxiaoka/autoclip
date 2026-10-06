# AutoClip 项目诊断与下一阶段重点（2026-10-06）

基线：main `b77c9301`，线上 latest v1.5.5（2026-10-06 17:15 发布）。数据来源：PostHog 生产事件（近 14 天）、Sentry（近 24 小时）、GitHub API、代码只读审计。上一轮诊断见 [PROJECT_DIAGNOSIS_AND_ITERATION_2026-09-30.md](PROJECT_DIAGNOSIS_AND_ITERATION_2026-09-30.md)。

## 一句话结论

**用户开始一键出片后，约 7 成设备拿不到成片。** 9-30 的诊断已经指出"第一次出片要稳"是唯一重点，但随后一周的精力主要花在了新功能（1.5.0）、连续热修（1.5.1–1.5.5）和发版流程本身上，核心成功率没有改善。1.5.4 还引入了一个新回归：自动模式下，可选的视觉预检一旦失败，整个出片都会失败。下一阶段只做一件事：**把设备级出片成功率从约 28% 拉到 60% 以上**，其余都让路。

## 1. 证据

### 1.1 线上漏斗（PostHog，设备去重，按天）

| 日期 | 日活 | 新装 | 发起导入 | 出片成功 | 出片失败 | 下载成片 |
|---|---|---|---|---|---|---|
| 09-25 | 318 | 261 | — | — | — | — |
| 09-29 | 242 | 162 | 168 | （1.4 无此事件） | | 16 |
| 10-02 | 179 | 121 | 103 | 19 | 63 | 13 |
| 10-04 | 162 | 101 | 103 | 25 | 60 | 23 |
| 10-05 | 156 | 95 | 90 | 23 | 57 | 20 |
| 10-06（不满一天） | 118 | 70 | 77 | 16 | 50 | 18 |

- **设备级出片成功率约 28%**：每天约 100 台设备发起导入，只有 20 多台拿到成片。
- **新装和日活都在下降**：新装从 261 降到约 95，日活从 318 降到约 160。GitHub 星标一周只涨了约 130（9,050 → 9,183）。获客红利在消退，首次体验失败的用户很少会再回来。
- **Windows 占已知安装包下载的 87%**（1.5.0：Windows 928 / Mac 140）。

### 1.2 各版本出片结果（`studio_generation_finished`，`material_origin=user`）

| 版本 | 成功设备 | 失败设备 | 主要失败码（设备数） |
|---|---|---|---|
| 1.5.0 | 79 | 250 | **全部没有错误码**（监控没覆盖到） |
| 1.5.3 | 3 | 17 | whisper_not_installed 13、subtitle_setup 4、rate_limited 4 |
| 1.5.5（上线 5 小时） | 3 | 22 | **provider_error 13**、whisper_not_installed 5、llm_not_configured 3、authentication 2 |

Sentry 显示 1.5.5 的 `provider_error` 主要出在 `intelligence.vision_call`，`phase=screening`，也就是自动出片前的"快速视觉判断"。

### 1.3 交付节奏

- 16 天里打了 12 个 tag（v1.3.1 → v1.5.5）。v1.5.1–v1.5.3 一直停在 Pre-release，v1.5.4 的 tag 没有生成 Release。
- 1.5.4 验收耗时 3 天，候选换了 8 次，正式记录只签了 Mac 2/10、Windows 0/10、回归 0/52，最后由负责人豁免发版。
- 9-29 之后的一周里，改动过的 Markdown 文档有 106 份；`artifacts/` 里的验收产物有 858 MB、151 个状态文件。

## 2. 诊断

### P0-1（线上回归，S1）：自动模式的视觉预检失败会拖垮整个出片

`backend/services/studio/planning.py` 在 1.5.4 加入了：

```python
except (...) as error:
    if options.auto_start:
        raise
```

原意是修 154-05b"游戏视频视觉失败后被静默改成按字幕制作"。但默认配置是 `analysis_mode='auto'` 加 `allow_visual_screening=True`，所以**每一次一键出片都会先走视觉预检**。只要视觉模型返回 400/5xx、超时或截断，访谈、播客这类按字幕完全能做的素材也会直接失败。1.5.2 / 1.5.3 在这种情况下会降级成按字幕制作。

**修法**：只有用户明确选了 `analysis_mode='visual'` 时才抛出；`auto` 模式下失败要记录原因，然后降级成按字幕制作；没有字幕也没有可用转写时，才算失败。需要补一条回归测试：auto 模式 + 预检 HTTP 400 → 字幕路线出片成功。**建议立即作为 1.5.6 热修。**

### P0-2：大部分失败在开始之前就能知道，却要等任务跑起来才告诉用户

1.5.5 失败码的前几名里，`whisper_not_installed`、`llm_not_configured`、`authentication`，加上预检相关的 `provider_error`，在用户点"开始"那一刻就能判断出来。但首页导入（`CreativeImport` 写死了 `auto_start=true`）**没有任何就绪检查**，任务排队、下载、分析之后才失败。用户看到的是"制作失败"，而不是"还差一步"。

**修法**：导入前做一次预检。检查分析模型是否已配置且测试通过、素材无字幕时转写是否已就绪、视觉能力是否已验证。缺什么就直接给出一键修复的入口（准备 SenseVoice、改用云 ASR、导入 SRT、去设置测试连接），而不是先跑任务再报失败。

### P0-3：监控口径还不足以指导修复

- 1.5.0 的失败事件**完全没有错误码**，两百多台失败设备只能从 Sentry 侧面推断原因。
- `backend/pipeline/failures.py:115` 把所有无法识别的异常都归成 `provider_error`；视觉请求只要不是 401/403/429，也都是 `provider_error`。它其实是个兜底桶。
- `studio_generation_finished` 上没有 `phase`、`http_status`、`route`（字幕或视觉）。只看 PostHog 无法区分是预检失败、转写失败还是分析失败。

**修法**：在出片终态事件上加 `failure_phase`（screening / subtitle / analyze / render / save）、`http_status`、`route`；把 `provider_error` 拆出 `http_4xx`、`http_5xx`、`unknown`。改完以后，§3 的周度看板才算真的可用。

### P1-1：CI 绿不等于用户能出片

代码审计发现，安装包冒烟（`scripts/verify_windows_install.py:174`、`installed_video_acceptance.py:112`）走的是旧的 `POST /api/v1/projects/upload` 加旧 step1–4 流水线。**用户实际使用的 `/studio/import` 一键出片、竖版包装、发布包都没有被自动测到。** 这正是验收被迫变成大量人工操作的根本原因。

**修法（S）**：把冒烟改成用本机 loopback LLM 调用 `POST /studio/import?auto_start=true`，等 `generation` 到终态，再用 ffprobe 检查一条成片。这一条做完以后，§4.2 的黄金路径里大部分步骤都能交给 CI。

### P1-2：状态有两个来源，Windows 上的文件写失败还在发生

- Studio 状态写在 `studio.json`（`store.py`），项目列表读 SQLite（`jobs.mark_project`），两边会不一致，列表显示"制作中"而结果页已经失败。`project_completion.py` 是事后补丁。
- Sentry 最近 24 小时里，`store.write` 的 `PermissionError` 仍是 Windows 上最常见的 issue 之一（PYTHON-FASTAPI-2E 等）。1.5.2–1.5.3 的热修处理的是症状，没有消除根因。
- 桌面版每次启动都会拉起 Celery worker（`desktop_main.py:180`），旧的"开始处理"入口也还能点到，多出来的进程会锁文件。

**修法（M）**：终态以 SQLite（或单一 WAL）为准，JSON 只作缓存；桌面版关掉 Celery；Studio 项目隐藏旧的重试入口。

### P1-3：发版流程的负担超过了它带来的保护

`release_acceptance.py` / `internal_acceptance.py` 的包身份绑定是真有用的（防止换包）；但影响承接合同、80 条命名断言、52 条逐条回归、每条依赖字节比对，属于簿记，没有增加任何产品覆盖。这次 tag 构建还暴露出：门禁自己有一个从没在真实 tag 上跑过的 bug，任何版本都会被它拦住。

**修法**：按 [TESTING_SOP.md](TESTING_SOP.md) 执行，包括冻结规则、黄金路径 G1–G7、按改动挑选追加项、时间盒、一次性预算、只有 S1 阻断、上线后看数据。验收工具保留身份绑定和豁免记录，不再扩展字段。

### P2：代码与文档债务

- `jobs.py` 1,530 行，下载、预检、字幕、视觉、包装、取景、封面、重试全在一个模块里，9-29 以来改了 41 次。
- 约 15–25% 的后端代码是并行的旧栈；完全无引用、可以先删的约 2–3k 行（`FileUpload.tsx`、`BilibiliDownload.tsx`、`celery_app_fixed.py`、`celery_minimal.py`、`execute_real_pipeline.py` 等）。
- Ruff 存量问题仍然很多（约 2,600 处可自动修复）；Studio 服务里有 47 处 `except Exception`。
- 文档膨胀：一周 106 份 Markdown 改动，HANDOFF、ROADMAP、COMMUNITY_BOARD、各个 RELEASE 文档之间互相引用、口径不一。

这些都不影响用户的第一次出片，**放到 P0/P1 之后，每周最多拿 20% 的时间处理**。

## 3. 下一阶段（约 3 周）计划

北极星指标：**设备级出片成功率**，即 `material_origin=user` 的设备中，`studio_generation_finished=completed` 的设备数 / 发起出片的设备数，按版本和平台拆分。目标：第 1 周 ≥ 45%，第 3 周 ≥ 60%。

| 顺序 | 工作包 | 规模 | 完成标准 |
|---|---|---|---|
| 0 | **1.5.6 热修：auto 模式预检失败降级到字幕路线** | S | 回归测试修复前失败、修复后通过；按 SOP 走热修流程；上线 24 小时后 1.5.6 的 `provider_error` 设备占比明显下降 |
| 1 | **导入前预检与一键修复** | M | 未配置模型、无字幕且转写没就绪、key 无效，这几种情况在开始前就被拦住，并给出修复入口；`whisper_not_installed` 和 `llm_not_configured` 作为出片失败码的设备数下降 80% |
| 2 | **失败口径**：终态加 `failure_phase` / `http_status` / `route`，拆分 `provider_error` | S | PostHog 看板能直接看到"按阶段的失败设备数"；未知错误占比 < 10% |
| 3 | **CI 冒烟改走 `/studio/import`** | S | Windows 安装冒烟用 loopback LLM 完成一次 Studio 自动出片，并用 ffprobe 检查成片 |
| 4 | **状态单一来源 + 桌面关掉 Celery** | M | 列表状态与结果页一致；Sentry 里 `store.write PermissionError` 的周设备数下降 |
| 5 | 删除无引用的旧代码（约 2–3k 行），把 `jobs.py` 按预检 / 制作 / 渲染拆开 | M | 测试全绿；不改用户可见行为 |

### 明确暂停

- 新的模型供应商、发布平台、包装样式、游戏买量相关能力。
- 账号、credits、商业化（继续按 ROADMAP 推后）。
- 验收工具的新字段、新合同，以及全仓 Ruff 清理和 UI 翻新。

### 负责人每周只看这四个数

1. 设备级出片成功率（按版本和平台）。
2. 失败阶段分布：预检 / 转写 / 分析 / 渲染 / 保存，加上未知。
3. 新装后 7 天内回来再出片的设备比例。
4. 每次发版的实际耗时、重建次数和费用（来自 SOP §10 的复盘）。

## 4. 局限

- PostHog 数据只包含同意匿名统计的设备，而且 1.5.0 之前没有 `studio_generation_finished`，所以不能和 1.4 直接比较成功率。
- 1.5.5 只上线了约 5 小时，样本小（25 台设备），趋势判断要等 24 小时数据。
- Sentry 的事件正文按隐私设置被省略了，具体的 HTTP 状态码要从后续补上的事件属性里拿。
