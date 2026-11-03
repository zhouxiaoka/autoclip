# X2: 失败主按钮按原因分流 — UI 截图

静态 fixture（`/tmp/x2-shots` → chrome headless）对照 `FailureActions` / `SwitchModelDialog` 主路径。

| 文件 | 场景 |
|------|------|
| `switch_model.png` | SWITCHABLE_UPSTREAM + ≥2 连接 → 主按钮「换模型重试」+ 选择器（F1 成功率标签，默认最高） |
| `install_asr.png` | `whisper_*` GATE → 主按钮「安装转写」 |
| `settings_single.png` | SWITCHABLE_UPSTREAM + 仅 1 连接 → 「去设置」+ 文案「建议再加一个服务商」 |

`recharge`（不足额度 + 已知赞助商）仅接线，完整跳转见 X3，本批未单独截图。
