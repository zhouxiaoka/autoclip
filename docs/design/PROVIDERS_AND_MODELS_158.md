# 1.5.8 服务商与模型架构

给 Kris 拍板。**只交文档，不写实现、不改 1.5.7、不合并。** Draft PR [#369](https://github.com/zhouxiaoka/autoclip/pull/369)。

本文取代 `docs/design/DYNAMIC_PROVIDER_PRESETS.md`。动态预设、默认模型、设置页 v6、线 B 校验不再拆成 1.5.9 独立项，统一进 **1.5.8「服务商与模型」**。对照：

| 材料 | 用处 |
|---|---|
| 模型设置 PRD v1.0 | 产品范围 IN-1–IN-9、§6.1 三十八家、§9 迁移、MS-38 deeplink、§12 待定 |
| 成功率路线图 v6 | §2.3 / §2.3.1 原 10.2–13.5 人天；§4 验收；§7 Pre-release 约 10/30–11/3 |
| `providers.md` | 三十八家清单与国内地址（上线前须核实） |
| OhMyGame `29bd5d4`（调研稿对照 `aa93b07`） | 可复用算法与数据，不是可粘贴的 UI |

已定、本文不再问：

1. **进 1.5.8**，不是单独 1.5.9。
2. **绝不自动换服务商**（倒推 #A）。PRD §7 / MS-23 写「失败时换其他服务商」——1.5.8 **改文案、不按这句话做**。
3. **「智能选择」= `source=preset`**：走该连接上的有序候选，并在**同一服务商内**降级。不是第二套开关。
4. 签名、CDN 镜像 **后移 1.5.9**。首版：内置预设 + `/models` 实时过滤 + 同商降级；远程若做，只走 https + schema。

---

## 0. 结论先行

默认地址和默认模型现在写在六处，发版才能改。百炼 `qwen-turbo` 429、同账号 `qwen-flash` 正常；e2e 与产品预设已经分叉。设置页仍是「一家下拉 + 隐式拉模型」，和 PRD 的「先连服务商、再按用途选默认模型」对不上。

1.5.8 做一件事：**一份预设表，前后端和门槛同读；地址和模型都标 `preset | user`；智能选择就是预设候选。** 线 B 用这张表锁官方地址并做保存前探测；线 C 管同模型 429；线 D 读同一份候选；#365 只管格式/空时间线。换商、签名分发、完整 deeplink 像素验收，都不挡 10/30–11/3。

OhMyGame 是 Electron + TypeScript，AutoClip 是 Python + React/antd。**能搬的是算法、报错分层、分组规则和清单数据；页面必须按 `DESIGN.md` 重写。** 原估 12 人天把签名和 CDN 算进去了，偏高。复用 + 砍非必须项之后，**本模块增量约 4.5–6.5 人天、日历 4–6 天**；与已开工的 B/C/D 并行，**不推翻 10/30–11/3**，但缓冲几乎为零。完整 v6 三十八家网格 + 双端 deeplink 若要像素级对齐原型，应砍或减到「数据齐、主路径能连」。

---

## 1. 范围：1.5.8 做 / 不做 / 后移

### 1.1 对照路线图 §2.3

路线图 v6 的 10.2–13.5 人天是 **#S S2–S7、#10、#2、#3、#9 余量**，并且 §3.1 曾把 v6 整页后移到 1.5.10 之后。Kris 后来改口：动态预设和默认模型并进 1.5.8，和 v6 / 线 B 同一模块。

| 条目 | 路线图原义 | 本文 |
|---|---|---|
| S2 预设锁定 | 先锁赞助商和 DeepSeek 等主流 | **三十八家预置都来自同一份 JSON**；官方地址对 `source=preset` 锁定；`compatible` / 自定义可改 |
| S3 保存前校验 | `GET /models` + 小请求；允许保存但标红，生成前再拦 | 仍是线 B；探测实现移植 OhMyGame 的 `/models` 算法 |
| S4 模型列表回填 | `/models` 填下拉 | 与候选求交，不再另写一份 `PREFERRED` |
| S5–S7 | 文案、埋点、门槛用例 | 沿用 copy-guide / #354；门槛改读同一份 JSON |
| #2 / #3 | 429 退避、付费前预检 | 线 C，本模块只**调用**，不重写 |
| #10 | `provider-e2e-gate` | 线 D；矩阵默认模型改读 JSON |
| 动态预设（原 1.5.9） | 未列入 §2.3 | **并入**：内置 JSON + 可选 https/schema 拉取 |
| 同商降级 | 未列入 §2.3 | **并入**：`source=preset` 时的外层候选 |
| 设置页 IA / 三十八家网格 / 首次引导 / deeplink | 路线图 §3.2 明确不提前 | **数据层 1.5.8 必做**；完整 UI 见 §1.3 |

### 1.2 1.5.8 必做（本模块 + 已开工线）

1. 单一数据源 `presets/provider_presets.json`（约三十八家 + 候选 + 分组 + 协议 + 能力）。
2. `source=preset | user` 同时用于地址和模型；映射 PRD 的「预置 / 自定义 / 智能选择 / 固定」。
3. 启动用内置表；`/models` 成功则只信账号列表；与候选求交后预选。
4. 同服务商降级：`model_not_found` / 下线 / 线 C 预算用尽仍 `rate_limited`。
5. 线 B：保存前探测、官方 host 锁定、key strip（#356 已开工）。
6. 线 C：429 / 5xx / 超时同模型再试（#358 已开工）。
7. 线 D：门槛读同一份 JSON（#355 已开工）。
8. 从 1.5.7 升级：尽量迁连接；迁不了就**留 key**，用途回到预设默认（NF-02 / NF-03）。
9. 新键八语同步。

### 1.3 1.5.8 做「薄切片」、不挡发版

| 项 | 1.5.8 | 说明 |
|---|---|---|
| 设置页 | 列表 + 详情 + 默认模型四格 + 智能选择/固定 | 跟 `DESIGN.md` / copy-guide；选中浅灰底。三十八家**数据先齐**，网格可以按组滚动，不追 OhMyGame 像素 |
| 自定义服务商 | 名称、OpenAI 兼容、地址、key、拉列表、勾选、手加 id | Anthropic / Google 原生协议后移 |
| 首次引导 | 现有 FirstRunSetup 接到同一份预置 | 不重做一整套向导 |
| 88API deeplink | 有余量再做；安全规则按 MS-38 | Infistar 对方未确认前只验手动填 key |
| 远程预设 | 可选：https + schema + 版本只增；失败用内置 | 无签名也能发 |

### 1.4 明确后移 1.5.9（或更后）

| 项 | 为什么可以后移 |
|---|---|
| Ed25519 签名、独立私钥、与 updater minisign 分离 | 内置表已能改候选；劫持面主要在「远程改官方 host」。1.5.8 远程只加 https + schema，或干脆不拉远程 |
| CDN / jsDelivr 镜像 | 没有远程拉取就不需要；有拉取先走 GitHub raw |
| 跨服务商智能选择（#A） | Kris 已定暂不做；PRD hover 要改文案 |
| 视觉能力精细标注 | 路线图已挂 1.5.9；1.5.8 沿用现有 vision marker |
| 自定义 Anthropic / Google 协议 | 预置家里已有协议字段；自定义弹窗首版只做 OpenAI 兼容 |
| Infistar Chat 预设 / 剪贴板粘贴按钮 | 取决于对方；按钮 PRD 已标 P2 |
| 配音 / 配乐、3D、OAuth、托管额度 | PRD OUT；OhMyGame 也不适用 |

---

## 2. 现状：六处写死

`main` `6868d562`（#364 已合）：

| 位置 | 写了什么 |
|---|---|
| `backend/core/cloud_presets.py` | 7 家云预设：地址 + **单个** `default_model`（网关为空） |
| `backend/core/local_presets.py` | Ollama / LM Studio 地址与默认名 |
| `frontend/src/features/settings/providers.ts` | 13 个 `ProviderKey`：分组、地址、单个默认模型、赞助文案 |
| `backend/core/model_catalog.py` | `DEFAULT_MODELS`（百炼=`qwen-plus`）；`/models` 缓存 5 分钟 |
| `frontend/src/features/settings/modelDefaults.ts` | `PREFERRED` / `IMAGE_PREFERRED` 有序，只填空槽 |
| #355 `scripts/provider_e2e/matrix.py` | 门槛自己的地址和模型（百炼 `qwen-flash`；88API host 与产品不一致） |

`Connection` **没有** `source`。空地址 = 隐式用内置。`Assignment` 只有 `connection_id` + `model`，没有「智能选择还是手选」。

现网已定、实现时必须接着用：

- [#364](https://github.com/zhouxiaoka/autoclip/pull/364)：只规范化地址，不拦保存。
- [#365](https://github.com/zhouxiaoka/autoclip/pull/365)（已合）：只对 `invalid_response` / `timeline_empty` 同模型再试 2 次。
- [#356](https://github.com/zhouxiaoka/autoclip/pull/356)（draft）：线 B，`provider_validation.py` + `provider_endpoint.py`。
- [#358](https://github.com/zhouxiaoka/autoclip/pull/358)（draft）：线 C，`llm_retry.py`，429 守 `Retry-After`≤120s。
- [#355](https://github.com/zhouxiaoka/autoclip/pull/355)（draft）：线 D，门槛。
- #354：`UpstreamErrorType` / `classify_upstream_error` / 埋点脱敏。

现有 `analysis_mode=auto` 仍是「画面识别走字幕还是视觉」，**不是**智能选择。不要改名去抢「智能选择」这个词。

---

## 3. PRD 术语 ↔ 本设计字段

PRD 只写「预置服务商」和「自定义服务商」，没有 `source=preset/user`。实现必须能对上，避免两套说法。

| PRD | 本设计 | 用户能改什么 | 远程/发版能不能改 |
|---|---|---|---|
| 预置服务商（推荐 / 热门 / 本机 / 更多） | 目录行 `kind=preset`；连接默认 `base_url_source=preset` | 填 key、开关启用；官方地址默认隐藏 | 只更新 `source=preset` 的地址和候选 |
| 自定义服务商 | 目录行 `kind=custom`；`base_url_source=user` | 名称、地址、协议、key、模型勾选 | **永不**被预设改地址或模型 |
| 智能选择（默认模型下拉） | 该用途 `model_source=preset` | 一键「改用推荐」回到 preset | 预设 bump + `/models` 求交后可改写 **preset** 槽 |
| 固定某一服务商 / 点选模型 id | `connection_id` 钉死，且/或 `model_source=user` | 选具体连接或具体 id | **不**自动改模型、不降级 |
| 与精彩片段分析相同 | `vision` 跟随 `analysis`（现有能力） | 快捷项 | 跟随对象变则跟着变 |
| 关闭 · 使用视频帧 | `cover_enabled=false`（已有字段） | 开关 | 不发起图像请求 |
| 已连接且启用 | 现有 `connections[]` + 启用开关 | 停用后退出下拉和智能选择 | — |

补充：

- **预置 ≠ 不能改地址。** 用户改过、规范化后仍与当时预设不同 → 记 `user`，之后当自定义线路。
- **自定义 ≠ 不能拉 `/models`。** 自定义照样探测；只是没有官方候选，下拉用账号列表。
- **「N 个服务商提供」**（MS-21）1.5.8 仍可展示，但智能选择**不会**在运行期换到另一家。要换家，用户自己点固定线路。PRD MS-23 hover 改为：「自动从当前服务商的推荐列表里选可用模型；这家限流或下线时换下一个推荐型号，不会改换服务商。」

`DefaultBinding` 建议落盘（旧文件兼容见 §10）：

```json
{
  "analysis": {
    "connection_id": "c1",
    "model": "qwen-flash",
    "model_source": "preset",
    "capability": "auto"
  }
}
```

`mode=smart|fixed` 不必再单开字段：`model_source=preset` 即 smart，`user` 即 fixed。

---

## 4. 单一数据源

### 4.1 唯一文件

仓库：`presets/provider_presets.json`。

生成/派生（实现阶段用脚本，禁止再手写第二份产品语义）：

| 消费者 | 怎么读 |
|---|---|
| 后端 `cloud_presets` / `local_presets` / `model_catalog.DEFAULT_MODELS` | 启动加载 JSON；旧模块变成薄封装或删除产品语义 |
| 前端 `providers.ts` / `modelDefaults.ts` | 同文件（构建拷入或运行时接口） |
| 线 B 官方 host / 锁地址 | `kind=preset` 的 `base_url` + `locked_hosts` |
| 线 D `matrix.py` | CI 读当前分支这份 JSON，再与 `GET /models` 求交；`*_MODEL` 仍可压过 |
| 内置 fallback | 打包进安装包的同一份字节 |

三十八家分组以 PRD §6.1 / `providers.md` 为准。OhMyGame / pi-ai 没有的国内行（百炼、硅基、火山语言、智谱标准址、千帆、混元、88API、Infistar、Whisper、SenseVoice）**写在这份 JSON 里**，不要另开表。

### 4.2 行字段（逻辑）

```json
{
  "schema_version": 1,
  "version": 1,
  "issued_at": "2026-10-14T00:00:00Z",
  "providers": {
    "dashscope": {
      "kind": "preset",
      "display_name": "阿里云百炼",
      "group": "popular",
      "protocol": "openai-completions",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "auth": "api_key",
      "capabilities": ["language", "asr", "image"],
      "docs_url": "https://bailian.console.aliyun.com/",
      "locked": true,
      "candidates": {
        "analysis": ["qwen-flash", "qwen-plus"],
        "vision": ["qwen-vl-plus", "qwen-flash"],
        "asr": [],
        "image": ["qwen-image-2.0", "wanx2.1-t2i-turbo"]
      }
    }
  }
}
```

约定：

- `schema_version` 管结构；`version` 管内容世代，只增不减。
- 未知 provider / 未知用途键：**忽略该行，不整包作废**。未知 `schema_version`：整包拒绝，退回已采用版本。
- 云端 `base_url` 必须 https + 主机，无 userinfo / query / fragment，保存前走 #364 `normalize_provider_base_url`。本机允许 `http://localhost` / 私网。
- 网关（88API / Infistar）`candidates` 可写推荐，**仍以账号 `/models` 为准**；列表失败才用候选。
- Ollama 可写推荐名；LM Studio / 自定义候选为空，必须手选。
- 首版候选 = 今天 `PREFERRED` ∩ 已核实 id。国内地址上线前按 `providers.md` §2 核实。

### 4.3 内置与可选远程（1.5.8 简化）

```
启动
 └─ 内置 JSON 立刻进内存（UI / health 不阻塞）
     └─ 若打开远程：https GET（超时 5s，ETag）
         ├─ schema 通过且 version ≥ 已采用 → 采用，写入数据目录缓存
         └─ 失败 / 降级 → 磁盘缓存 → 内置
```

1.5.8 **不做**：Ed25519、CDN 多源、私钥进 Secrets。设置页可留「检查更新」，失败只记日志和埋点。

谁的地址能被远程改：仅 `base_url_source=preset`。`user` 永不改。改地址仍作废已存 key（现有行为）。预设页对 `preset` 地址继续默认隐藏；「恢复默认」打回 `preset`。

---

## 5. 智能选择 = 候选路由

### 5.1 预选

沿用现网 `POST /settings/ai-models/discover`：

1. 账号 `/models` 成功 → **只信账号**。
2. 失败 → 保留上次 live；第一次失败才用内置目录。
3. 缓存 5 分钟；手动刷新打穿。
4. 预选：`candidates[purpose]` 里第一个同时在本次列表、且用途适配（ASR 要 `asr_supported`，封面要生图，画面要视觉或 `follow_analysis`）。
5. 没 key 的预览目录 **不写入** 推荐。
6. `applyModelDefaults` / 预设 bump **只动 `model_source=preset` 或空槽**。

### 5.2 运行期同商降级

只对 `model_source=preset`。手选不降级、不改文件；设置页用现有错误条：「当前模型在该账号不可用或已下线」，主按钮「改用推荐」。

触发（须先走 #354 分类）：

| 降 | 不降 |
|---|---|
| `model_not_found` / 目录 RETIRED / 404·503 的模型语义 | 401 / 402 / 403 |
| 线 C 预算用尽仍 `rate_limited`（频率，如百炼 `limit_requests`） | 余额 / 配额 / 权限 / 地址错 |
| | 手选（`source=user`） |

### 5.3 与 #358 / #365 的顺序和上限

```
一次分块
└─ 候选 1..N（N≤3，仅当前连接）
   ├─ 内层 #358：同模型最多 3 次（含首次）。429 守 Retry-After≤120s，否则抖动退避；并减半分块并发
   ├─ 调用成功但结果不可用 #365：invalid_response / timeline_empty → 同模型再试最多 2 次
   └─ 外层降级：not_found / 下线 / 358 用尽仍频率 429 → 下一候选（degrade_count++）
全部失败 → 最后一次错误给用户（现有 HINT_KEYS）
```

#358 / #365 上限按候选**重置**。建议每分块再加 **6 次计费帽**，防 3×3×3。SDK 仍只留 1 次 429/5xx。`degrade_count` 与 `retry_count` 同时上报，含义不同。

线 B 的保存前探测 **不算** 这 6 次帽（设置态，不是出片分块）。生成前再拦走线 C 的预检，401/402/403 付费前失败。

---

## 6. 与 B / C / D / #365 的边界

各线已开工，本模块**复用，不平行再写一套**。

| 线 | PR | 本模块用它做什么 | 本模块不改什么 |
|---|---|---|---|
| B | #356 | 锁 `kind=preset` 的官方 host；保存时 `GET /models` + 16 token 探针；`ValidationResult`；控制台 host / 缺 `/v1` 清理；`provider_validation_finished` | 不改「允许保存但标红、生成前再拦」 |
| C | #358 | 每个候选内部的 429/5xx/超时；`Retry-After`；并发减半；ASR 预检 | 不在 C 里换模型、不换商 |
| D | #355 | `matrix.py` 改读 JSON；cases 记实际 `model` 与 `degrade_count`；故障注入仍不换商 | 不把门槛改成测跨商 |
| #365 | 已合 | 语义重试只认两种结果码 | 不把 429 / not_found 塞进 #365 |
| #364 | 已合 | 所有写入地址先规范化 | 不在规范化里拦截保存 |
| #354 | 已合 | 分类、脱敏、事件字段 | 不新开错误枚举 |

文件边界（并行时遵守，减少冲突）：

| 线 | 主文件 |
|---|---|
| P 本模块数据 | `presets/provider_presets.json`、新 loader、删/薄封装 `cloud_presets` / `local_presets` / `modelDefaults` / `DEFAULT_MODELS` |
| B | `provider_validation.py`、`provider_endpoint.py`、设置保存 API |
| C | `llm_retry.py`、`llm_manager.py`、pipeline 并发 |
| D | `scripts/provider_e2e/*`、workflow |
| R 降级 | `llm_manager` 外一层候选循环（C 合入后再接），不要在 #358 里夹带 |
| U 设置页 | `frontend/src/features/settings/*`、八语；视觉跟 `DESIGN.md` |

合入顺序建议：#354（已合）→ #364（已合）→ **P 数据契约** → B / C 可继续并行 → R 接 C → D 改读 JSON → U 接 P+B。

---

## 7. OhMyGame 复用（已 clone 核对）

本地核对：`https://github.com/WhiteTowerAI/ohmygame` @ `29bd5d4`（调研稿 `aa93b07` 结构仍适用）。许可证 **Apache-2.0**，仓库**没有** `NOTICE` 文件。作者字段：`WhiteTowerAI`。栈：Electron + TS daemon/renderer，模型清单来自 `@earendil-works/pi-ai@0.99.2`（**MIT**），图标 `@lobehub/icons-static-svg@1.94.0`（**MIT**）。

### 7.1 建议复用（按价值）

| 路径 | 内容 | 怎么用 | 工作量 |
|---|---|---|---|
| `src/daemon/provider-model-discovery.ts` | `{baseUrl}/models`：OpenAI / Anthropic / Gemini 头、分页、15s、最多 20 页 / 2000 条、可操作报错 | **移植成 Python**，供线 B S3 与自定义「获取模型列表」。测例 `test/provider-model-discovery.test.ts` 一起搬断言 | 高 |
| `src/renderer/custom-provider-models.ts` | 发现结果与已选合并、id 校验、用途约束 | 逻辑移植；UI 用 antd 重写 | 中 |
| `src/renderer/local-model-providers.ts` | Ollama `11434/v1`、LM Studio `1234/v1`、`authentication=none` | 并入 JSON；现有 `local_presets.py` 已接近 | 低 |
| `src/renderer/models-settings.tsx` 约 L46–186 | 搜索、能力筛选、Popular 写死、More 折叠、已连接提前 | **只借分组规则**，不拷 JSX | 中 |
| `src/renderer/provider-models.tsx` | 显示/隐藏、手加 id、shown/total | 聚合网关需要；存 `hidden_model_ids` | 中 |
| `src/renderer/custom-provider-dialog.tsx` | 名称 / 协议 / 地址 / key / 拉列表 | 交互骨架；视觉按 DESIGN.md | 中 |
| `src/renderer/media-model-defaults.tsx` | 按用途选默认 | 用途换成 analysis / vision / asr / cover | 中 |
| `src/renderer/provider-icons.ts` | id → lobehub 文件 | 映射表可抄；**只用单色 SVG** | 低 |
| `src/shared/custom-models.ts` `normalizeEndpoint` | 去尾 `/`、禁 userinfo/query | 已有 #364，对照即可，不必再搬 | 已有 |
| `src/daemon/app.ts` `providerSummaries` | 已连接 / 能力汇总 | 对照接口形状，后端用现有 `connections[]` | 低 |
| pi-ai `models` 入口（MIT） | id、名称、baseUrl、协议、视觉标记 | **导出 JSON 快照**进 `provider_presets.json`，不把 TS runtime 引进 Python | 高 |
| `test/custom-provider-dialog.test.ts` 等 | 发现失败文案、合并行为 | 改写成 pytest / 前端单测 | 中 |

### 7.2 不要搬

| 路径 | 原因 |
|---|---|
| `src/daemon/model-auth.ts`、`src/desktop/oauth.ts` | 绑 pi runtime OAuth；PRD OUT-6 |
| `src/daemon/cloud-models.ts`、`docs/free-cloud-models.md` | 托管额度，Kris 不做托管 |
| `provider-models3d.ts`、`meshy` / `tripo` / `hyper3d` | PRD OUT-5 |
| `seedance-*` / BytePlus 视频主路径 | 1.5.8 视频只做能力标签 |
| 编程套餐端点（Xiaomi Token Plan、Z.AI coding、Qwen token-plan） | `providers.md` 已排除 |
| Electron 设置壳、chip 选中态 | 违反 `DESIGN.md`（选中用 `--sel` 浅灰，不用强调蓝填充） |

### 7.3 许可证

| 来源 | 许可 | 和 AutoClip（MIT） |
|---|---|---|
| OhMyGame | Apache-2.0 | **可以复用**。MIT 工程收录 Apache-2.0 文件是常见且兼容的做法：项目根仍可写 MIT，但**被复用的文件继续按 Apache-2.0 义务发布**，不能改成「只保留 MIT、丢掉 Apache 条件」。 |
| pi-ai 0.99.2 | MIT | 导出快照时保留版权与 MIT 声明即可。 |
| lobehub icons | MIT | 同样保留声明。商标只能指代服务商，不能暗示合作。88API / Infistar 用首字母。 |

Apache-2.0 **必须做**（实现 PR 落地，本 PR 只登记）：

1. 在仓库放 `third_party/ohmygame/LICENSE`（全文）和 `third_party/ohmygame/NOTICE`。上游没有 NOTICE，NOTICE 里写：来源 `WhiteTowerAI/ohmygame`、commit、哪些文件是衍生。
2. 每个从 OhMyGame **复制或明显改写**的文件保留原版权行，并加：`Modifications © AutoClip Team` + 改了什么。
3. 发行物（桌面安装包）带上这些 LICENSE / NOTICE。
4. 专利授权随 Apache-2.0 走；不要删授权段。
5. 纯思路重写、没有实质性代码对应的 antd 页面，用 AutoClip MIT 即可，但分组常量和报错句若直接翻译自 OhMyGame，仍建议在文件头注明来源。

**结论：许可证不挡 1.5.8。** 不能「拷了代码却只留一个 MIT 文件」。

---

## 8. 迁移（PRD §9 / NF-02 / NF-03）

旧 `ai-model-settings.json`：

| 旧状态 | 新字段 |
|---|---|
| 空 `base_url` 或规范化后等于当时预设 | `base_url_source=preset` |
| 用户填过且与预设不同 | `base_url_source=user` |
| 已填模型 | **建议** `model_source=user`（保守，避免静默改老用户） |
| 空模型槽 | `model_source=preset`，下次 discover 填候选 |
| `compatible` | 永远 `user` |
| `cover_enabled` / `analysis_mode` / Whisper / SenseVoice | 保持现有字段，不做无损映射时不删 key |

迁不了的用途绑定：保留连接与 key，用途回到该预置的推荐默认，设置页给一条确认。**禁止**因迁移失败清空 key。

封面：现有 `cover` + `cover_enabled` + `cover_choice_version` 已覆盖 PRD「关闭 · 使用视频帧」。1.5.8 不新开 `purpose=cover` 平行配置。

---

## 9. 埋点

先登记再发。沿用 [TRACKING_PLAN](../analytics/TRACKING_PLAN.md) / `sanitize_model` / `hostname_of_base_url`。不报 key、完整 URL、提示词、字幕、用户内容。

| 事件 | 何时 | 允许字段 |
|---|---|---|
| `provider_preset_fetched` | 一次启动（或手动检查）结束 | `preset_version`，`source`∈`remote\|cache\|builtin`，`outcome`∈`success\|error`，`schema_version` |
| `provider_validation_finished` | 线 B 已定 | 现有字段 |
| `llm_request_finished` | 线 A 已定 | 现有 + `preset_version`，`degrade_count`（0=未降级），`model`=实际打出的 id |

八语无关；改契约与 `event_inventory.json`。

---

## 10. 工期：复用 + 多助手并行

### 10.1 人天（相对原 12 人天和路线图 §2.3）

原 #369 把签名、CDN、降级、门槛全算进 12 人天，按从零写。下面按「移植算法 + 已开工 B/C/D + 砍签名」重估。

| 块 | 原估 | 现估人天 | 依据 |
|---|---|---|---|
| P 单一 JSON + loader + 内置 | 3（含签名） | **1.0–1.5** | pi-ai 快照 + `providers.md`；无 Ed25519 |
| 可选 https + schema 拉取 | 含在上项 | **0.5** | 无 CDN、无验签 |
| `source` + 迁移 | 2 | **1.0–1.2** | 规则已定；测例要覆盖旧文件 |
| `/models` 求交 + 回填 | 2 | **0.8–1.0** | 移植 discovery；与 S3/S4 重叠，不重复算满 |
| 同商降级 + 埋点 | 3 | **1.2–1.8** | 接 #358/#365，不重写退避 |
| 门槛改读 JSON | 2 | **0.3–0.5** | #355 已有矩阵，只换数据源 |
| **本模块增量小计** | **12** | **4.8–6.5** | |
| 线 B 余量（S2–S7 − 与 P 重叠） | 3.2–4.5 | **2.0–3.0** | S3 借用 discovery |
| 线 C | 3.0–3.5 | **1.5–2.0** | 已开工 |
| 线 D | 3–4 | **2.5–3.5** | 已开工；改读 JSON 已计入上表 0.3–0.5 |
| 设置页薄切片（列表/详情/四格/智能选择） | PRD 待估 | **2.0–3.0** | 结构看 OhMyGame，控件 antd + DESIGN.md |
| 自定义 + 首次引导接预置 | 待估 | **0.8–1.2** | |
| 88API deeplink | 2–3 + 1 验 | **2.0–3.0**（可选并行） | 无 OhMyGame 可抄 |
| **1.5.8 服务商与模型合计（含 B/C/D，不含完整三十八家像素和 Infistar deeplink）** | 10.2–13.5 且不含本模块 | **约 13.5–19.0 人天** | 人天升、日历可以不升 |

人天比路线图 §2.3 多，是因为并进了数据源、`source`、降级和一层设置 IA。Kris 要快的是**日历**，不是把人天装成没加范围。

### 10.2 并行切分（日历）

假设继续用多名云端助手，文件边界见 §6。

```
        10/14          10/21          10/27          10/30–11/3
1.5.7   开发/验收/观察  Promote
线 B    ████████░░░░   ░░收尾
线 C    ████████░░░░   ░░收尾
线 D    ████████████   ██ 门槛夜间
线 P    ░░████         JSON+loader+source   （不碰 1.5.7 路径）
线 R         ░░████    降级（等 C 的 retry API）
线 U         ░░██████  设置薄切片（等 P 的 JSON 形状）
线 L            ░░████ deeplink（可选，与 U 并行）
联调              ██   10/27–29
验收                    ████
```

| 线 | 依赖 | 日历（并行后） |
|---|---|---|
| P 数据 | 无。1.5.7 期间即可写 JSON 与 loader | 2–3 天 |
| B 校验 | P 的锁定 host 表；#364 已合 | 已开工，再 4–6 天收尾 |
| C 退避 | #354 已合 | 已开工，再 3–5 天 |
| R 降级 | C 的「预算用尽」信号 + P 的候选 | 3–4 天，接在 C 后 |
| D 门槛 | P 的 JSON；专用 key（§6.1） | 已开工，到 10/27 夜间累计 |
| U 设置 | P 的字段；B 的 ValidationResult | 4–6 天 |
| L deeplink | U 的连接写入；Win/Mac 各验 | 4–5 天（可与 U 后半重叠） |

**日历合计（P+R+U 与 B/C/D 并行）：约 12–16 个日历日**，从 10/14 起算，落在 10/26–10/30 可提测。这比「12 人天串行 ≈ 两周一个人」短，也比「从零写签名分发」短。

### 10.3 对 10/30–11/3 的影响

| 问题 | 判断 |
|---|---|
| 只做 §1.2 必做 + 设置薄切片，签名/CDN/跨商/#A 后移 | **不推翻**路线图 §7 的 Pre-release 窗 |
| 再加 88API deeplink 双端 | 能并行则仍可能赶上；Infistar 不作为门槛 |
| 再加签名 + CDN + 三十八家像素级 + 双赞助商 deeplink | **会挤窗**，建议明确砍到 1.5.9 |
| 1.5.7 验收/观察与 1.5.8 重叠（路线图 R14） | 本模块用独立分支/助手；10/16 前不占 1.5.7 合入名单 |
| 路线图 §3.1「v6 整页后移」 | 被 Kris 新决定覆盖：**数据与智能选择进 1.5.8**；整页像素级仍可薄 |

缓冲为零（R9）。任一已开工线（B/C/D）晚合，先保门槛和校验，降级与设置 IA 可以同一 Pre-release 里少做一档，但不能把「一份 JSON + `source`」再拆出去。

验收仍走 `docs/TESTING_ACCEPTANCE.md`：源码门禁、双平台安装包、手选不被改、mock 429 在同商第二候选出片、换商用例必须失败。真实百炼 `qwen-turbo`→`qwen-flash` 作观察样本，不挡本文合入。

---

## 11. 风险

| 风险 | 缓解 |
|---|---|
| 把 OhMyGame JSX 贴进 antd | 只移植算法；视觉审查对照 `DESIGN.md` |
| Apache-2.0 文件当 MIT 发出 | §7.3；实现 PR 同时加 LICENSE/NOTICE |
| 远程预设被劫持改 host | 1.5.8 默认可只内置；若拉远程则 https+schema+只改 preset；签名 1.5.9 |
| 降级更贵或放大 429 | 人工审候选顺序；≤3 候选 + 建议 6 次帽；额度不降 |
| 手选被静默改 | `user` 只提示；旧已填模型当 `user` |
| 与 #358 叠乘 | 每候选 3 次 + 全局 6 次 |
| e2e 与产品分叉 | 同读一份 JSON |
| PRD「换商」文案与 #A 冲突 | 改 hover，写入实现说明 |
| 国内地址未核实 | 开放问题；不核实不上正式 tag |
| 多助手改同一设置文件 | §6 文件边界；合入顺序 P → B/U，C → R |

---

## 12. 待确认问题（PRD §12 与原文 8 条合并去重）

已在本文拍板、不再列为问题：进 1.5.8；智能选择 = `source=preset` 且不换商；签名/CDN 后移；1.5.8 远程最多 https+schema；不做 key 识别与剪贴板自动读。

仍需 Kris / 产品点头：

1. **智能选择排序**（PRD §12.1）：1.5.8 是否接受「固定顺序：赞助商 → 热门 → 其他 + 失败换下一候选」，不做延迟探测？
2. **画面理解跟随分析**（§12.2）：跟随的模型无视觉时，禁止选择、保存警告，还是运行时报错？
3. **「N 个服务商提供」里未连接项**（§12.3）：点击引导去配置，还是直接禁用？
4. **自定义协议**（§12.4）：确认首版只做 OpenAI 兼容？
5. **封面字段**（§12.5）：确认沿用现有 `cover` + `cover_enabled`，不新开用途键？
6. **八语**（§12.6）：新键是否必须八语齐（建议必须，与仓库门禁一致）？
7. **Infistar**（§12.7）：Chat 预设能否配？确认前 deeplink 验收是否只绑 88API？
8. **国内 baseUrl**（§12.8）：百炼 / 硅基 / 火山 / 智谱 / 千帆 / 混元由谁核实并签字？
9. **「从剪贴板粘贴」按钮**（§12.9）：确认 1.5.8 不做（非自动读取）？
10. **旧版迁移体验**（§12.10）：不能自动映射时，是否接受「留 key、用途重置为推荐默认」一次性体验？
11. **SenseVoice**（§12.11）：首次启用是否复用 Whisper 下载流？
12. **火山视频标签**（§12.12）：确认只做筛选/能力，不绑默认模型？
13. **全局计费帽**（原文 3）：每分块 6 次，还是只靠「≤3 候选 × 每层最多 3 次」？
14. **已保存的 preset 模型**（原文 4）：预设 bump 后下次 discover **改写**文件，还是只影响新连接、旧 preset 冻结？
15. **429 降级范围**（原文 5）：只降频率（`limit_requests` / `rate_limit_exceeded`），额度失败不降？
16. **旧文件缺省**（原文 8）：已填模型当 `user`（建议，更保守），还是当 `preset`（老用户才能吃到降级）？

原 8 条里的「进哪个版本 / 是否三层智能 / 签哪种名 / 用哪家 CDN」已收进 §0 与 §1.4，不重复问。

---

## 13. 参考

- PRD：附件 `autoclip-model-settings-prd.md`（仓库外）；原型 `mockups-v6/`
- 路线图 v6：`autoclip-success-rate-roadmap.md` §2.3、§2.3.1、§4、§7
- 清单：`providers.md`
- OhMyGame 调研：`ohmygame-settings-review.md`；源码 https://github.com/WhiteTowerAI/ohmygame
- 设计：[`DESIGN.md`](../../DESIGN.md)
- 验收：[`docs/TESTING_ACCEPTANCE.md`](../TESTING_ACCEPTANCE.md)、[`RELEASE_CHECKLIST.md`](../../RELEASE_CHECKLIST.md)
- 埋点：[`docs/analytics/TRACKING_PLAN.md`](../analytics/TRACKING_PLAN.md)

---

## 修订

| 日期 | 说明 |
|---|---|
| 2026-10-14 | 初稿曾建议实现进 1.5.9，并拆成独立动态预设 |
| 2026-10-14 | 统一进 1.5.8；PRD 对照；OhMyGame 复用与许可证；人天/日历重估；签名后移；待定问题合并 |
