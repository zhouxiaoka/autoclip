# T3: 本地模型明确型号门槛 — UI 截图

Fixture：`frontend/t3-shots/index.html`（chrome headless）。

| 文件 | 场景 |
|------|------|
| `01-red-warn-under-gate.png` | 参数 <7B 或上下文 <8k → 红字「大概率解析失败，不建议做分析」（仍可选） |
| `02-recommend-pull.png` | 顶部推荐 qwen2.5:7b/14b / llama3.1:8b + 一键拉取 SSE 进度 |
| `03-lm-studio-unknown.png` | LM Studio 无参数量时显示「未知」 |

门槛字段：`params_b` / `context_tokens`（Ollama `/api/show`；LM Studio 名推断 `\b(\d+)[bB]\b`），供后续 D1 `chunk_size` 使用。
