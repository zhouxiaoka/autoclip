# F2: 测试连接改为快速/试跑两档 — UI 截图

Fixture HTML：`frontend/f2-shots/index.html`（chrome headless 截图）。

| 文件 | 场景 |
|------|------|
| `01-quick-vs-trial-buttons.png` | 「快速测试」+「试跑一段」两档按钮；保存后自动试跑提示 |
| `02-trial-pass.png` | 试跑通过：上下文/速率/输出格式三行 ✓ + 预计请求/耗时 |
| `03-trial-fail-yellow-badge.png` | 未通过试跑黄标；速率 ⚠ 限流 + 输出格式 ✗；仍可保存 |

试跑：内置 sample SRT → 真实 step1 大纲 prompt + JSON schema，连发 3 次（间隔 1s）；任一 ✗ 仍允许保存，连接卡显示「未通过试跑」（`trial_status` 供 F5 读取）。
