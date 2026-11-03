# X3: 赞助商余额不足直接跳充值 — UI 截图

Fixture HTML：`frontend/x3-shots/index.html`（chrome headless 截图）。

| 文件 | 场景 |
|------|------|
| `01-sponsor-recharge.png` | api88：主按钮「去 88API 充值」+ 固定文案「密钥没问题，是余额不足…」 |
| `02-non-sponsor-balance.png` | 非赞助商：主按钮「查看余额」 |
| `03-billable-n.png` | 「本次已消耗 N 次请求」（无金额） |

`insufficient_quota` 粗码保持 `provider_error`（A2），细码 `upstream_error_type=insufficient_quota`；赞助商打开 `topup_url`（否则 `register_url`）。
