# 发版前服务商端到端门槛

> **验收冻结：** fail-closed 已在 verify live（Actions `38514864277`）核对。Gemini 默认 `gemini-3.5-flash-lite` 已通过。88API 单探针（Actions `38516691310`，`https://api.88api.ai/v1` + `deepseek-v4-flash`）已通过。完整发版仍要走分层 live，**不要只靠这一条探针放行**。mock 套件本身仍可用来挡回归。

1.5.7 起，Desktop Build 在 `candidate-gate` 之后、Release Acceptance 之前必须通过 [`.github/workflows/provider-e2e-gate.yml`](../.github/workflows/provider-e2e-gate.yml)。它在 Linux 上起无界面桌面后端（`backend.desktop_main`），用 Studio HTTP 跑「导入 → 自动出片」，不打开 UI。

同一份 workflow 也可单独触发（PR / 分支 push / 候选 tag / 夜间定时 / `workflow_dispatch`）。**fork 的 PR 整门都不跑**，避免把 environment 密钥暴露给外部仓库。

## 分层：谁跑真实服务商

| 触发 | 跑什么 | 真实服务商 |
| --- | --- | --- |
| PR、功能分支 push、未打 tag 的 Desktop Build | 仅 mock | 不调用 |
| 夜间 `17 18 * * *` | `nightly`：DeepSeek + Gemini 免费/低价档，2–3 条短素材（按 ISO 周轮转分配） | 只这两家 |
| 候选 tag / `workflow_dispatch` 且 `full=true` | `prerelease`：10 条素材拆给 5 家，每家 2 条；配对按 ISO 周轮转 | 五家都在 key 齐时跑 |
| `workflow_dispatch` 且 `include_live=true`（默认） | `nightly` 规模 | DeepSeek + Gemini |
| `workflow_dispatch` 且 `live_mode=verify` | 夜间子集 + 88API / DashScope / Infistar 各 1 条最小成功用例 | 五家各至少探一次 |
| `workflow_dispatch` 且 `live_mode=api88` | 只跑 88API 一条 `talk_zh` 探针 | 只这一家 |

**PR / push 永远不会打真实服务商。** 缺 `*_MODEL` 时用 [`matrix.py`](../scripts/provider_e2e/matrix.py) 的 live 默认模型，不受产品目录默认型号影响，不跳过。一家都没配 key 时 live job 记 `skipped` 并写进汇总，workflow 不失败。

## 矩阵数据源

Live 聊天地址和回退型号以 [`matrix.py`](../scripts/provider_e2e/matrix.py) 的 `LIVE_PROVIDERS` 为准，**不要把门槛 live 默认写进产品 JSON**。产品目录里 Gemini 默认是 `gemini-3.8-flash`、地址是 `https://generativelanguage.googleapis.com/v1beta`（给原生 `/models` 用）；live 出片走 OpenAI 兼容根 `…/v1beta/openai`。DashScope live 默认是 `qwen-plus`。有 `backend/presets/provider_presets.json` 时只读显示名和聊天地址输入，保留 live 默认型号；聊天地址仍经 `locked_chat_url` 补齐。可用 `AUTOCLIP_PROVIDER_PRESETS` 指向另一份 JSON。`*_MODEL` 仍可覆盖型号。日志、报告和用例库继续脱敏，不打印密钥。

## 判定

| 组合 | 门槛 |
| --- | --- |
| Mock 应成功（口播、访谈、英文播客、带字幕、竖屏、游戏、体育、纯音乐） | **当次**成功率 ≥ 95%。8 条素材时必须全部通过。 |
| 应拦下（太短、无音轨） | 100% 在开始前拦下，契约字段 `billable_calls_before_failure = 0`（由 `llm_usage.jsonl` 计数） |
| 故障注入（本地 mock：429 + `Retry-After`、503、断线、中途杀后端） | 期望类型用 [`UpstreamErrorType`](SUCCESS_RATE_CONTRACT.md)：`rate_limited` / `upstream_unavailable` / `connection`（均可重试，退避后出片）。杀后端不是上游错误，重启后应落成 `service_restarted`。不做自动换服务商。 |
| Live 应成功 | **fail-closed。** 任一服务商失败、缺报告 / 空报告 / 无法解析、或实际条数少于计划矩阵，具名 `provider-e2e` job 必须红。滚动窗口（用例库最近 5 次、满 20 条应成功样本后 ≥ 95%）是额外门槛，样本不足不能把当次失败判绿。单次硬失败（不可重试的 `UpstreamErrorType` 或产品失败）会中止该服务商剩余用例。 |

产物是 `provider-e2e-report` 与 `provider-e2e-cases` artifact（`report.json` / `report.md` / `cases.jsonl`），不含密钥、用户正文、字幕全文或完整 URL（只留 host）。

## 两套套件

**Mock（必跑，不花钱）**  
本地 OpenAI 兼容服务回答大纲 / 时间线 / 评分 / 标题。素材由 `ffmpeg` lavfi 现场生成（约 70 秒、带 SRT），体积小、可再分发。应拦下的两条不带 SRT。

**真实服务商（有 key 才跑，且只在上表允许的触发里跑）**  
88API、DeepSeek、Gemini、DashScope（阿里云百炼）、Infistar。密钥只从 GitHub Environment `provider-e2e` 读取。额度用尽或产品失败会失败，并在报告里用错误码 / `error_class` 区分。

B 站 / YouTube 链接单独验收，不计入本门槛。

## 配置 Environment 与密钥

1. 仓库 Settings → Environments → 新建 `provider-e2e`。
2. Deployment branches：只允许 `main` 和 `v*` tag。夜间 cron 与 `workflow_dispatch` 也要能部署到该 environment；不要对尚未配 key 的仓库加 required reviewers，否则 Desktop Build 会停在审批。
3. Environment secrets（不要写进仓库 Secrets，除非你清楚 fork 风险）：

| Secret | 用途 |
| --- | --- |
| `API88_API_KEY` | 88API 专用 CI token，设额度上限并限制模型。地址读预设 JSON（已核实门槛为 `https://api.88api.ai/v1`）；无 JSON 时用 `matrix.py` 默认 |
| `API88_MODEL` | 可选。未设时用预设 JSON 默认模型；该行若为空则回退 `deepseek-v4-flash` |
| `DEEPSEEK_API_KEY` | DeepSeek 官方独立项目 key |
| `DEEPSEEK_MODEL` | 可选，缺省 `deepseek-flash` |
| `GEMINI_API_KEY` | Gemini 独立项目 key（夜间走免费档） |
| `GEMINI_MODEL` | 可选。未设时用预设 JSON 默认型号（产品目录为 `gemini-3.8-flash`）；无 JSON 时门槛回退已核实的 `gemini-3.5-flash-lite`。聊天地址固定 `…/v1beta/openai`，不要用缺 `/openai` 的产品目录地址。不要再用已下线的 `gemini-2.0-flash` / `gemini-2.0-flash-lite` |
| `DASHSCOPE_API_KEY` | 阿里云百炼 / DashScope。地址 `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `DASHSCOPE_MODEL` | 可选，缺省 `qwen-plus` |
| `INFISTAR_API_KEY` | Infistar。地址 `https://infistar.ai/v1` |
| `INFISTAR_MODEL` | 可选，缺省 `gpt-4o-mini` |

Harness 只读环境变量。日志和 artifact 会掩码 `sk-` / `Bearer` / `api_key`。每季度轮换。GitHub 也会自动掩码 secrets。

本地试跑 mock（不需要 key）：

```bash
sudo apt-get install -y ffmpeg fonts-noto-cjk
pip install -r requirements.txt
PYTHONPATH=scripts python -m provider_e2e --suite mock --out /tmp/provider-e2e-mock
```

真实服务商：把上面的变量 export 到当前 shell 后再跑 `--suite live --mode nightly`。不要把 key 写进命令行历史能看到的脚本。

## 用例库

每次 live 跑完写一条脱敏记录（provider、clip id、model、pass/fail、`error_class`、duration_ms、估费、run id / commit）。不写密钥、用户内容、转写、完整 URL。

- Artifact：`provider-e2e-cases`（`cases.jsonl` + `cases.json`），保留 90 天，供滚动窗口和月度预算回放。
- 追加分支：`provider-e2e-cases`（孤儿分支，**不要合进 main**）。live job 在有 `contents: write` 时尽量追加；失败只记日志，不挡 mock。

## 预算与熔断

| 上限 | 值 | 行为 |
| --- | --- | --- |
| 月度硬顶 | **¥300** | 开跑前：本月用例库估费 + 本轮估费。超了则 **不发起任何真实调用**，live 记 `budget_blocked`，job 失败，写 step summary；有权限时开一条 GitHub issue。 |
| 单轮 | nightly ¥15 / verify ¥25 / prerelease ¥40 | 超过则中止剩余用例 |
| 单服务商 | nightly ¥8 / verify ¥10 / prerelease ¥12 | 超过则中止该服务商剩余用例 |
| 首个硬失败 | 不可重试的上游错误或产品失败 | 中止该服务商剩余用例 |
| live job | 60 分钟 | Actions timeout |

**请 Kris 在各服务商控制台再加一道账单上限**（本仓库的 ¥300 是 CI 自己的保险丝，控制台限额才能挡住泄漏或重放）：

- 88API：token / 额度上限，限制可用模型
- DeepSeek：用量或余额告警
- Gemini：AI Studio / Cloud 预算与日配额
- DashScope（百炼）：费用预警与额度
- Infistar：credit / 模型白名单

## 费用量级（月估 ¥80–180，硬顶 ¥300）

数字来自公开价的偏高估算，以各家账单为准。假设：字幕路线、约 70 秒 lavfi、每条成功用例约 1.5 万 + 4 千 token、默认最便宜模型。

| 范围 | 量级 | 假设 |
| --- | --- | --- |
| DeepSeek flash 一条短素材 | 约 ¥0.05–0.2 | 夜间主力 |
| Gemini flash-lite 一条 | 约 ¥0–0.1 | 常走免费档，仍按有价计入预算 |
| 88API `deepseek-v4-flash` 一条 | 约 ¥0.05–0.3 | 只在预发布或 verify / `api88` 探针 |
| Infistar `gpt-4o-mini` 一条 | 约 ¥0.3–1.5 | 只在预发布或 verify 探针 |
| DashScope `qwen-plus` 一条 | 约 ¥0.1–0.5 | 同上 |
| 一夜 late nightly（2–3 条） | 约 ¥0.2–0.8 | 30 夜 ≈ ¥6–24 |
| 一次预发布（10 条拆 5 家） | 约 ¥4–20 | 每月约 4 次 ≈ ¥16–80 |
| 一次 verify（夜间子集 + 三家各 1 条） | 约 ¥1–8 | 少用 |
| **每月合计** | **约 ¥80–180** | 含 1.5× 重试缓冲；硬顶 ¥300 |

Mock 套件为 0。本门槛只走字幕 + 自带 SRT，不跑 Whisper，也不默认打视觉。以前「5 家 × 10 条」的完整矩阵已取消，避免单月冲破 ¥300。

## 接入发版链路

- [`desktop-build.yml`](../.github/workflows/desktop-build.yml) 的 `provider-e2e` job `needs: candidate-gate`，与双平台打包并行。未打 tag 时只跑 mock；`v*` tag 才跑 `prerelease` live。
- `release` 与 `internal-provenance` 都要求具名 `provider-e2e` job 成功。fail-closed 已在 `38514864277` 核对；88API 单探针已在 `38516691310` 通过。live 滚动窗口在样本未满 20 条时不额外卡；当次服务商失败仍红。
- [`scripts/release_acceptance.py`](../scripts/release_acceptance.py) 的 `BUILD_JOBS` 含 `provider-e2e`，Release Acceptance 会核对 Desktop Build 里这个 job。

矩阵、轮转与故障定义见 [`scripts/provider_e2e/matrix.py`](../scripts/provider_e2e/matrix.py)。判定与故障注入引用 [成功率共享契约](SUCCESS_RATE_CONTRACT.md) 的 `UpstreamErrorType` 与 `billable_calls_before_failure`，不另造一套码。

## 2026-10 live 失败根因（配置，不是管线）

Actions `38508586808`（全矩阵）与 `38511841070`（verify）里，DeepSeek / DashScope / Infistar 同一条分析管线能过；88API 与 Gemini 在分析阶段 0 次计费、`error_code=provider_error`。产品把除 401/403/429 以外带 HTTP 状态的失败都落成 `provider_error`，所以报告里的 `error_class` 当时是 `unknown`。二者都按 **配置** 修，不改调用链：

| 服务商 | 归类 | 契约 `error_type` | 典型 HTTP | 脱敏线索 | 修复 |
| --- | --- | --- | --- | --- | --- |
| 88API | 配置 | 旧默认 `gpt-4o-mini` 不在该 token 的 `/v1/models` 里，落成 `upstream_unavailable` | 503（`38514864277`） | `大纲提取失败：1/1 个文本块调用模型都失败了`；0 次计费 | CI 默认 base `https://api.88api.ai/v1`（`GET /v1/models` 200）；默认模型 `deepseek-v4-flash`。`API88_MODEL` 已在 Environment 设为同一值 |
| Gemini | 配置（已修好） | 旧默认是 `model_not_found`；现默认已通过 | 旧 404 | 旧：`Gemini调用失败` / `gemini-2.0-flash*`；新：`gemini-3.5-flash-lite` 3 次计费出片 | 默认改为目录内最便宜的 `gemini-3.5-flash-lite`；可被 `GEMINI_MODEL` 覆盖 |

复现夹具：[`scripts/provider_e2e/testdata/live_24_of_40.json`](../scripts/provider_e2e/testdata/live_24_of_40.json)。旧判定（只看滚动窗口、样本不足即绿）会放行；fail-closed 必须红。
