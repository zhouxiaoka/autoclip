# 发版前服务商端到端门槛

1.5.8 起，Desktop Build 在 `candidate-gate` 之后、Release Acceptance 之前必须通过 [`.github/workflows/provider-e2e-gate.yml`](../.github/workflows/provider-e2e-gate.yml)。它在 Linux 上起无界面桌面后端（`backend.desktop_main`），用 Studio HTTP 跑「导入 → 自动出片」，不打开 UI。

同一份 workflow 也可单独触发（PR / main / 候选 tag / 夜间定时 / `workflow_dispatch`）。**fork 的 PR 整门都不跑**，避免把 environment 密钥暴露给外部仓库。

## 判定

| 组合 | 门槛 |
| --- | --- |
| 应成功（口播、访谈、英文播客、带字幕、竖屏、游戏、体育、纯音乐） | 当次成功率 ≥ 95%。8 条素材时必须全部通过。 |
| 应拦下（太短、无音轨） | 100% 在开始前拦下，契约字段 `billable_calls_before_failure = 0`（由 `llm_usage.jsonl` 计数，埋点线落地后读同一字段） |
| 故障注入（本地 mock：429 + `Retry-After`、503、断线、中途杀后端） | 期望类型用 [`UpstreamErrorType`](SUCCESS_RATE_CONTRACT.md)：`rate_limited` / `upstream_unavailable` / `connection`（均可重试，退避后出片）。杀后端不是上游错误，重启后应落成 `service_restarted`。不做自动换服务商。 |

近 7 次夜间累计成功率会写进报告，当前没有跨 run 历史时只作说明，不单独卡发版。产物是 `provider-e2e-report` artifact（`report.json` / `report.md`），不含密钥。

## 两套套件

**Mock（必跑，不花钱）**  
本地 OpenAI 兼容服务回答大纲 / 时间线 / 评分 / 标题。素材由 `ffmpeg` lavfi 现场生成（约 25 秒、带 SRT），体积小、可再分发。应拦下的两条不带 SRT。

**真实服务商（有 key 才跑）**  
88API、DeepSeek、Gemini、DashScope（百炼）、Infistar。密钥只从 GitHub Environment `provider-e2e` 读取。**只缺 `*_MODEL` 时用矩阵里的默认模型，不跳过。** 一家都没配 key 时 job 记 `skipped` 并写进汇总，workflow 不失败。额度用尽或产品失败会失败，并在报告里用错误码区分。

B 站 / YouTube 链接单独验收，不计入本门槛。

## 配置 Environment 与密钥

1. 仓库 Settings → Environments → 新建 `provider-e2e`。
2. Deployment branches：只允许 `main` 和 `v*` tag。不要对尚未配 key 的仓库加 required reviewers，否则 Desktop Build 会停在审批。
3. Environment secrets（不要写进仓库 Secrets，除非你清楚 fork 风险）：

| Secret | 用途 |
| --- | --- |
| `API88_API_KEY` | 88API 专用 CI token，设额度上限并限制模型。地址 `https://api.88api.ai/v1` |
| `API88_MODEL` | 可选，缺省 `gpt-4o-mini` |
| `DEEPSEEK_API_KEY` | DeepSeek 官方独立项目 key |
| `DEEPSEEK_MODEL` | 可选，缺省 `deepseek-flash` |
| `GEMINI_API_KEY` | Gemini 独立项目 key |
| `GEMINI_MODEL` | 可选，缺省 `gemini-2.0-flash` |
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

真实服务商：把上面的变量 export 到当前 shell 后再跑 `--suite live`。不要把 key 写进命令行历史能看到的脚本。

## 费用量级

数字来自倒推方案的公开价估算，以各家账单为准。

| 范围 | 量级 |
| --- | --- |
| DeepSeek 单条短素材 | 约 ¥0.05–0.5 |
| Gemini flash 单条 | 约 $0.01–0.1 |
| 88API（中档模型）单条 | 约 ¥0.2–2 |
| 一次完整真实门槛（约 5 家 × 10 条） | 约 ¥30–100 |
| 夜间子集 | 约 ¥10–20 |
| 每月 | 约 ¥500–1000 |

Mock 套件为 0。本门槛只走字幕 + 自带 SRT，不跑 Whisper，也不默认打视觉。CI token 请设月度上限；额度耗尽时报告会带服务商错误，而不是被当成「没配 key」跳过。

## 接入发版链路

- [`desktop-build.yml`](../.github/workflows/desktop-build.yml) 的 `provider-e2e` job `needs: candidate-gate`，与双平台打包并行。
- `release` 与 `internal-provenance` 都要求它成功。
- [`scripts/release_acceptance.py`](../scripts/release_acceptance.py) 的 `BUILD_JOBS` 含 `provider-e2e`，Release Acceptance 会核对 Desktop Build 里这个 job。

矩阵与故障定义见 [`scripts/provider_e2e/matrix.py`](../scripts/provider_e2e/matrix.py)。判定与故障注入引用 [成功率共享契约](SUCCESS_RATE_CONTRACT.md) 的 `UpstreamErrorType` 与 `billable_calls_before_failure`，不另造一套码。
