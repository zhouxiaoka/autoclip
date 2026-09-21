# AutoClip 埋点体系

> **2026-09-21 更新：** 本页下方保留历史埋点说明。新实现、事件准确口径、看板和验收请以 [ANALYTICS_V2.md](ANALYTICS_V2.md) 为准。旧 `clips_exported` 并非完整出片指标；`app_installed` 是匿名存储身份首次启动；网页与桌面不能直接串联归因。V2 本地代码尚待发布与正式包收数验收。

> 工具：**PostHog**（US 区，`https://us.i.posthog.com`）
> 原则（见 `ROADMAP.md` Phase 0）：**匿名 · 可关 · 本地缓冲**。不采集 PII、视频内容、字幕文本、API key 明文。

## 1. 指标框架

| 层级 | 指标 | 数据来源 |
|------|------|---------|
| 🌟 北极星 | 周成功出片用户数 | `clips_exported` |
| 获取 | 下载数 / 安装数 | 下载页 / `app_installed` |
| 激活 | 导入→出片转化率、首次出片耗时 | 漏斗事件 |
| 留存 | D1/D7/D30、周活 | `app_opened`（PostHog 自动算） |
| 参与 | 人均出片数、功能渗透率 | 各功能事件 |
| 变现就绪 | 模型分布、配 key 率、失败率 | `api_key_configured` / `processing_failed` |

## 2. 核心漏斗

```
下载 .dmg → app_installed → video_imported → clips_exported(★激活) → 回访(留存)
```

## 3. 事件字典

命名规范：`对象_动作`，snake_case。代码统一走 `src/analytics/events.ts`，未配置 key 或用户关闭时自动 no-op。

### 生命周期（`src/analytics/lifecycle.ts`）
| 事件 | 触发 | 属性 |
|------|------|------|
| `app_installed` | 设备首次启动 | `version, os, arch` |
| `app_opened` | 每次启动 | `version, session_number` |
| `app_updated` | 版本号变化 | `from_version, to_version` |

### 激活漏斗
| 事件 | 触发位置 | 属性 |
|------|---------|------|
| `video_imported` | `api.ts` `uploadFiles` / `createDownloadTask` / `createYouTubeDownloadTask` | `source(upload/url), fileType, sizeBytes` |
| `clips_exported` ★ | `api.ts` `downloadVideo` | `clipCount, exportType(clip/collection/project)` |

### 配置
| 事件 | 触发位置 | 属性 |
|------|---------|------|
| `api_key_configured` | `SettingsPage` 保存成功后 | `provider, hasKey`（**不传明文**） |

### 错误
| 事件 | 触发位置 | 属性 |
|------|---------|------|
| `processing_failed` | `api.ts` 导入/导出 catch | `stage(import/export/...), code, message` |

> 崩溃/异常栈交给 **Sentry**（`frontend/src/desktop/sentry.ts`、`backend/core/sentry_setup.py`），PostHog 只记业务失败。接入说明见 `docs/UPDATES_AND_SENTRY.md`。

## 4. 全局属性（Super Properties）

每条事件自动携带，在 `lifecycle.ts` 的 `trackLaunch()` 里注册：
`app_version`（Tauri `getVersion()`）· `os` · `arch` · `app_locale`。

## 5. 身份模型

- 现在：匿名设备 ID（PostHog 自动，`localStorage` 持久化）。
- Phase 1 账号上线后：登录 `identifyUser(userId)`、登出 `resetUser()`（`src/analytics/posthog.ts` 已备好）。

## 6. 下载量（App 外）

App 内用 `app_installed` 当装机量。若有官网，加 PostHog 网页 snippet 埋 `download_clicked`，串成"落地页→下载→安装"全漏斗。

## 7. 隐私 / 合规

- 设置页 → 应用设置 → **隐私与数据** 开关（`setAnalyticsEnabled`），状态持久化，重启生效。
- 默认关录屏、不采 PII、key 只记 `hasKey`。
- 上线前需配套**隐私政策**（《个人信息保护法》要求）。

## 8. 配置

环境变量（`frontend/.env.local`，已 gitignore）：
```
VITE_PUBLIC_POSTHOG_KEY=phc_xxx
VITE_PUBLIC_POSTHOG_HOST=https://us.i.posthog.com
```
缺省时埋点全程 no-op。模板见 `frontend/.env.example`。

Sentry DSN（同样可打进前端的公开值）：
```
VITE_PUBLIC_SENTRY_DSN=https://...@....ingest.sentry.io/...
```

## 9. 加新事件的步骤

1. 在 `events.ts` 的 `AnalyticsEvent` 加常量 + 类型化封装函数。
2. 在调用点 import 调用（优先放 `services/api.ts` 这类集中层）。
3. 更新本文件的事件字典。
