# 动态服务商预设与默认模型

给 Kris 拍板。**只交文档，不写实现、不改 1.5.7。** 建议实现进 **1.5.9**。

默认地址/模型写死在六处，发版才能改。最近百炼 `qwen-turbo` 429 `limit_requests`，同账号 `qwen-flash` 正常。e2e 也在漂：产品 `https://88api.ai/v1`，门槛 `https://api.88api.ai/v1` + `deepseek-v4-flash`；Gemini 旧默认已下线。Kris 已定：**暂不自动换商**。

`main` `6868d562` 写死点：`cloud_presets.py` / `local_presets.py` / 前端 `providers.ts`（地址 + 单个默认模型）；`model_catalog.DEFAULT_MODELS`（百炼=`qwen-plus`，`/models` 缓存 5 分钟）；`modelDefaults.PREFERRED`（有序，只填空槽）；e2e `matrix.py`（分支 `provider-e2e-gate`，百炼=`qwen-flash`）。`Connection` **没有** `source=preset/user`，空地址 = 隐式内置。

已定：[#364](https://github.com/zhouxiaoka/autoclip/pull/364) 只规范化地址、不拦保存；[#365](https://github.com/zhouxiaoka/autoclip/pull/365) 只对 `invalid_response` / `timeline_empty` 同模型再试 2 次；[#358](https://github.com/zhouxiaoka/autoclip/pull/358)（draft）对 429/5xx/超时/断连同模型再试 2 次，`Retry-After`≤120s。v6「智能选择」= `analysis_mode=auto` + 空槽预选，**不是**调用期换模型。

---

## A. 服务商预设动态更新

仓库放签名的 `presets/provider_presets.json` + `.sig`，发到 GitHub raw，CDN 镜像（建议 jsDelivr `gh/zhouxiaoka/autoclip@main/...`）。私钥进 Secrets，**与 updater minisign 分开**；公钥打进客户端。CI 在文件变更时验签 + schema。

**启动：** 内置先入内存，UI / health **不阻塞**。后台 CDN → raw；失败依次退回磁盘缓存 → 内置。超时 5s，ETag。6 小时最多成功拉一次，设置页可手动检查。

**校验（全过才用）：** 拉取 URL 必须 `https`；schema；Ed25519 签**已提交原字节**；`version` 整数且 **≥** 已采用版本（只增不减）；云端 `base_url` 必须 `https` + 主机、无 userinfo/query/fragment，走 #364 的 `normalize_provider_base_url`。本机允许 `http://localhost` / 私网。缺字段或未知 key：**忽略该家，不整包作废**。

**谁的地址能改：** `Connection.base_url_source: preset | user`。空地址或规范化后等于当时预设 → `preset`，只改这类。用户改过（#364 改写后仍与预设不同）→ `user`，**永不被远程改**；改地址仍作废已存 key。`preset` 地址在设置页继续默认隐藏；「恢复默认」打回 `preset`。`compatible` 无远程地址。赞助/文档链接可随预设更新（只展示）。

落盘：数据目录已校验正文 + `provider-presets.meta.json`（`version` / `fetched_at` / `source=cdn|raw|cache|builtin`）。密钥不上盘。

---

## B. 默认模型也要动态

### 1) 远程写「有序候选」，不写死单个模型

每家按用途给有序列表：`analysis`（切片/对话）、`vision`、`asr`、`image`。排序 = 推荐优先级（稳、够用、少踩限流的在前）。网关（Infistar / 88API）也可以写候选，仍以账号 `/models` 为准。本地 Ollama 可写推荐名；LM Studio / `compatible` 候选为空，必须手选。

### 2) 和 `/models` 求交，取第一个可用

沿用现网：`POST /settings/ai-models/discover`，账号列表成功则**只信账号**；失败保留上次 live；第一次失败才用内置目录。缓存 5 分钟，手动刷新可打穿。

预选：`candidates[role]` 里第一个同时满足「在本次列表里 + 该用途适配」（ASR 还要 `asr_supported`，封面要生图协议，画面分析要多模态或 `auto` 可走字幕）。预览目录（没 key）**不写入**推荐，与现在一致。

运行时不再每调用打 `/models`；用本次进程里最后一次 discover。若候选全不在列表，**每个 run 最多再刷一次**；仍没有就用当前已保存模型，不换商。

### 3) 同商降级；与 #365 / #358 的顺序和上限

**绝不自动换服务商。** 只对 `model_source=auto` 降级。触发：`model_not_found` / 已下线（目录 `RETIRED` 或 404/503 模型语义）/ `#358` 预算用尽后仍 `rate_limited`（如百炼 `limit_requests`）。401/402/403、余额、权限、地址错：**立即失败，不降级**。频率 vs 额度 429 见文末。

```
一次分块
└─ 候选 1..N（N≤3，仅当前连接的服务商）
   ├─ 内层 #358：同模型最多 3 次（含首次）。429 守 Retry-After≤120s，否则 2/4/8… 抖动；并减半分块并发
   ├─ 调用成功但 #365：invalid_response / timeline_empty → 同模型再试最多 2 次
   └─ 外层降级：not_found / 下线 / 358 用尽仍 429 → 下一候选（degrade_count++）
全部失败 → 最后一次错误给用户（现有 HINT_KEYS）
```

#365 / #358 上限按 Kris 已定（每种再试 2 次），**按候选重置**。建议每分块再加 **6 次计费帽**，防 3×3×3。SDK 仍只留 1 次 429/5xx（`LLM_SDK_MAX_RETRIES=1`）。

### 4) 手选不被覆盖；下线怎么提示

`Assignment` 增加 `model_source: auto | user`。`applyModelDefaults` / 预设 bump **只动 `auto` 或空槽**。下拉里点选、自定义 ID、「使用自定义型号」→ `user`。点「改用推荐」→ `auto` 并重算。

手选模型不在 live 列表或运行期 `model_not_found`：**不改模型、不降级**。设置页在模型行下用现有 `ac-note--error`：「当前模型在该账号不可用或已下线」，主按钮「改用推荐」。出片失败走已有 `HINT_KEYS.model_not_found`，可带同一动作。不弹阻塞框、不自动改文件。

### 5) 与 v6「智能选择」：分层，不替代

| 层 | 是什么 | 本设计 |
| --- | --- | --- |
| L1 设置页（已有） | `analysis_mode=auto` 画面识别；空槽预选；刷新不覆盖已填 | **保留**。远程名单成为 L1 的数据源，替换 `PREFERRED` / `DEFAULT_MODELS` / `CloudPreset.default_model` |
| L2 远程候选（新） | 每家每用途有序列表 | 单一数据源，前后端与 e2e 同读 |
| L3 调用期降级（新） | 同商换下一个候选 | v6 没有；不把 L3 做成设置里第二个「智能」开关 |

三层都**不换商**。L1 的 `auto` 是字幕/画面路由，L3 的 `model_source=auto` 是「可换候选」，两个字段，不要合成一个开关。

### 6) provider-e2e / 探针读同一份名单

`matrix.py` 与 verify / `api88` 探针缺省改为读仓库这份 JSON（CI 用当前分支，不靠客户端拉取），再与 `GET /models` 求交，取该用途第一个。`*_MODEL` 仍可压过。`cases.jsonl` 记实际 `model` 与 `degrade_count`。故障注入按分支 `provider-e2e-gate` 的 `docs/PROVIDER_E2E_GATE.md` 与成功率契约，**不换商**。孤儿分支 `provider-e2e-cases` 只追加脱敏记录。

---

## 数据格式（示例）

`presets/provider_presets.json`（签名对象是**整个文件字节**）：

```json
{
  "schema_version": 1, "version": 1, "issued_at": "2026-10-14T00:00:00Z",
  "providers": {
    "dashscope": {
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "candidates": {
        "analysis": ["qwen-flash", "qwen-plus", "qwen3.8-flash"],
        "vision": ["qwen3.8-flash", "qwen-vl-plus"],
        "asr": ["qwen-audio-3.1-asr-flash", "qwen-audio-3.0-asr-flash"],
        "image": ["qwen-image-2.0", "wanx2.1-t2i-turbo"]
      }
    }
  }
}
```

同级 `.sig`：Ed25519 签**文件原字节**。`schema_version` 是结构，`version` 是内容世代；未知 schema 整包拒绝，未知 provider/role 忽略。首版候选 = 今天 `PREFERRED` ∩ 已核实 ID。

`ai-model-settings.json` 增量（旧文件：空地址=`preset`，已填模型=`user`）：

```json
{
  "connections": [{ "id": "c1", "provider": "dashscope", "base_url": "", "base_url_source": "preset" }],
  "analysis": { "connection_id": "c1", "model": "qwen-flash", "model_source": "auto", "capability": "auto" }
}
```

---

## 埋点

先登记再发，沿用 [TRACKING_PLAN](../analytics/TRACKING_PLAN.md) / `sanitize_model` / `hostname_of_base_url`。只报：**preset `version`、host（本机=`local`）、模型 id、降级次数**。不报 key、完整 URL、提示词、字幕、用户内容。

| 事件 | 何时 | 允许字段 |
| --- | --- | --- |
| `provider_preset_fetched` | 一次启动拉取结束 | `preset_version`, `source`∈`cdn\|raw\|cache\|builtin`, `outcome`∈`success\|error`, `schema_version` |
| `llm_request_finished`（已有） | 每次模型调用 | 现有字段 + `preset_version`, `degrade_count`（0=未降级）, `model`=**实际打出去的 id** |

`degrade_count` 是本次分块已换候选次数，不是 #358/#365 的 `retry_count`。两者同时存在：先同模型重试，再换候选。实现时改契约与 `event_inventory.json`，八语无关。

---

## 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| 伪造预设 / 劫持 host | 独立 Ed25519；https-only；#364 规范化；`user` 地址不改 |
| CDN/raw 被劫持或回滚 | 验签 + version 只增；失败用缓存/内置；启动不依赖网 |
| 降级更贵或放大 429 | 人工审顺序；≤3 候选 + 建议 6 次帽；额度/权限不降 |
| 手选被静默改 | `user` 只提示；旧文件已填模型当 `user` |
| 与 #358 叠乘 | 每候选 3 次 + 全局 6 次；`Retry-After`≤120s |
| e2e 与产品分叉 | 同读一份 JSON；`*_MODEL` 可压过。L2 落地后删掉 `PREFERRED` / `DEFAULT_MODELS` 的产品语义 |

---

## 分期与版本（人天）

**1.5.7 不动。** 1.5.8 已排成功率收口、#358、e2e 门槛。**文档现在可合；实现进 1.5.9。** 若要把「只拉预设、不降级」提前，A + B1–B2 可薄切片进 1.5.8，L3 仍留 1.5.9。

| 阶段 | 交付 | 人天 |
| --- | --- | --- |
| P0 契约 | schema、签名、内置文件、异步拉取/缓存、单测 | 3 |
| P1 地址 | `base_url_source`、迁移、只更新 preset、衔接 #364、设置页「恢复默认」 | 2 |
| P2 预选 | 候选替换 `PREFERRED`/`DEFAULT_MODELS`、discover 求交、八语文案 | 2 |
| P3 降级 | 同商 L3、与 #365/#358 顺序、埋点、手选下线提示 | 3 |
| P4 门槛 | e2e/探针同名单、429 降级注入、回归 | 2 |
| **合计** | | **12** |

验收：源码门禁 + 双平台安装包；预设拉失败仍能出片（内置）；手选不改；mock 429 在同商第二候选出片；换商用例必须失败。真实百炼 `qwen-turbo`→`qwen-flash` 作 1.5.9 观察样本，不挡文档合入。

---

## 请 Kris 拍板

1. **版本：** 实现 1.5.9，还是 A+B1–B2 进 1.5.8、L3 留 1.5.9？
2. **智能选择：** 同意 §B5 三层，还是把 L3 并进设置页一个「智能」开关？
3. **全局计费帽：** 建议每分块 6 次。还是只靠「≤3 候选 × 每层最多 3 次」、不再加帽？
4. **已保存的 `auto` 模型：** 预设 bump 后，下次 discover **改写**设置文件，还是只影响新连接、旧 auto 当冻结？
5. **429 降级范围：** 只降频率（`limit_requests` / `rate_limit_exceeded`），额度/配额失败不降？
6. **签名：** 独立 Ed25519（建议），还是复用 updater minisign？
7. **CDN：** jsDelivr 镜像 GitHub raw（建议），还是只走 raw、或自建？
8. **旧文件缺省：** 已填模型当 `user`（建议，更保守），还是当 `auto`（才能给老用户降级）？
