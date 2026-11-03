# T1: 首次出片默认单平台 — UI 截图

Fixture-driven renders（`frontend/t1-shots`）使用真实 `platformsForLocale` + studio CSS / Btn。

| 文件 | 场景 |
|------|------|
| `01-default-single-platform.png` | 无 `first_success_at` 时 zh 默认仅抖音（可手动多选） |
| `02-more-platform-banner.png` | 成片顶提示「也可以再做一个小红书版本」+ 同素材再做一个 / 知道了 |

动作路径：成片 CTA → `stashReuseImport`（platforms + source_meta + 已下载源）→ `navigate('/')` → `CreativeImport` `takeReuseImport` 预选；**不**恢复 `append_platform_variants`。
