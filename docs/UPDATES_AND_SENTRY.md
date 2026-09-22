# 应用内更新与崩溃上报

桌面端已接 **Tauri updater**（检查更新 → 用户确认后下载安装）和 **Sentry**（前端 + Python 后端）。
未配置 DSN 时监控为 no-op；配置了前端 DSN 的桌面 CI 构建还必须提供 `SENTRY_AUTH_TOKEN`，否则提前失败，避免发布无法还原堆栈的安装包。

Rust 原生崩溃先不接（体积 / reqwest 版本），壳进程挂了目前看不到；Python 后端和 React 渲染错误会进 Sentry。

## 你需要配的 Secrets

GitHub → Settings → Secrets and variables → Actions：

| Secret / Variable | 用途 |
|-------------------|------|
| `TAURI_SIGNING_PRIVATE_KEY` | updater minisign **私钥**全文（见下方生成）。没有则打得出安装包，但没有 `latest.json`，应用内检查更新会安静失败。 |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | 私钥密码。当前仓库生成的密钥是空密码，可留空。 |
| `VITE_PUBLIC_SENTRY_DSN` | 前端 Sentry DSN（客户端公开值，打进 JS）。不配则前端不报。 |
| `SENTRY_DSN` | 后端 DSN。构建时由 Rust 启动器注入 Python 子进程。可与前端用同一个 Sentry 项目。 |
| `SENTRY_AUTH_TOKEN` | Sentry 组织上传令牌，仅供构建时上传 source maps / 创建 release，不能使用 DSN 代替，也不能以 `VITE_` 开头。 |
| `VITE_PUBLIC_POSTHOG_KEY` | 已有，埋点用。 |

公钥已写在 `src-tauri/tauri.conf.json` 的 `plugins.updater.pubkey`，**不要改**，除非同时轮换私钥。

私钥在本机：`src-tauri/.updater-private-key`（已 gitignore）。把它的内容贴进 `TAURI_SIGNING_PRIVATE_KEY`。不要提交、不要发到聊天里。

重新生成（会让旧版本无法校验新包，只在密钥泄漏时做）：

```bash
cargo tauri signer generate --ci --password "" -w src-tauri/.updater-private-key -f
# 把打印出的公钥写回 tauri.conf.json
```

## Sentry 项目

1. 在 [sentry.io](https://sentry.io) 建一个项目（平台选 React 或 Python 均可，或建两个）。
2. 复制 DSN，分别填 `VITE_PUBLIC_SENTRY_DSN` / `SENTRY_DSN`。
3. 未配置时：前端 `initSentry()` 和后端 `init_sentry()` 直接 return，不发网络请求。

上报内容：崩溃栈、应用版本、OS。`send_default_pii = False`。不含视频、字幕、API key。
用户可在 **设置 → 应用 → 崩溃报告** 关闭；关闭后写入本机 `privacy.json`，每次发送错误前重新检查；无需重启即可拦截后续错误。

### 后端本地接入

在项目根目录的 `.env`（已被 Git 忽略）配置 `SENTRY_DSN`，从项目根目录启动：

```bash
venv/bin/python -m uvicorn backend.main:app --env-file .env --host 127.0.0.1 --port 8000
```

`init_sentry()` 读取进程环境变量；仅把 DSN 放入 `.env` 不会自动启用，启动时需传入 `--env-file .env` 或提前导出 `SENTRY_DSN`。
桌面构建仍需在构建环境 / GitHub Actions 配置 `SENTRY_DSN`，本地 `.env` 不会自动写入已发布的安装包。

后端 SDK 固定为 `sentry-sdk==2.69.2`，兼容当前 FastAPI / Starlette；原 2.35.2 在未安装 Jinja2 的当前环境中初始化失败。
保留 `send_default_pii=False` 和 `traces_sample_rate=0.0`，当前只启用错误监控。验证时应使用临时测试路由，收到事件后移除，不在发布版本保留 `/sentry-debug`。

### 前端接入与验证

前端对应 Sentry 组织 `autoclip-ts` 的 `autoclip-frontend` 项目；后端对应 `python-fastapi`。
本地在 `frontend/.env.local` 配置 `VITE_PUBLIC_SENTRY_DSN`，修改后重启 Vite。
GitHub Actions 使用同名仓库 Secret，macOS / Windows 构建步骤均已引用。
已于 2026-09-21 从真实开发页面触发并确认收到测试错误：
[AUTOCLIP-FRONTEND-1](https://autoclip-ts.sentry.io/issues/AUTOCLIP-FRONTEND-1)。临时测试按钮及代码已移除。

当前前后端完成的是本地错误上报验证；正式桌面安装包需使用这些配置重新构建后再验收。

### 生产 source maps

`@sentry/vite-plugin` 在带上传凭据的生产构建中注入 Debug ID、生成 hidden source maps、上传对应 JS 与映射，随后删除 `dist/**/*.map`，安装包不携带映射文件。
SDK 事件与上传 release 使用同一个版本：`autoclip-frontend@<VITE_APP_VERSION>`；未传版本时从 `src-tauri/tauri.conf.json` 读取。
插件上传失败会中止构建，不会降级为成功。

CI 的 macOS / Windows 构建均读取仓库 Secret `SENTRY_AUTH_TOKEN`，组织为 `autoclip-ts`，项目为 `autoclip-frontend`。
已配置前端 DSN 的构建会设置 `SENTRY_UPLOAD_SOURCEMAPS=true`，并在下载运行时之前检查 token 是否存在。

本地验证时，在 `frontend/.env.sentry-build-plugin` 写入 `SENTRY_AUTH_TOKEN=<组织上传令牌>`（已被 Git 忽略），然后从 `frontend` 运行 `npm run build`。
无令牌的普通本地构建仍可运行，但不生成或上传映射；可显式设置 `SENTRY_UPLOAD_SOURCEMAPS=false` 做离线构建检查。
上传令牌只用于构建，不能复制到前端环境变量或打入安装包。

验收必须使用上传完成的同一次构建触发**新错误**，在 Sentry 中检查原始文件、函数、行号和源码上下文；历史开发测试事件不能证明生产 source maps 有效。

2026-09-21：构建配置测试 7 项、前端 typecheck 和无上传构建已通过。后续已完成真实上传与生产构建错误还原，见文末验收记录。
发布准备另发现当前工作区基线早于已发布的 `v1.3.0`（本地版本配置为 `1.2.1`）；发布前需整合到最新基线并统一版本，不能直接把旧基线构建作为新版发布。

## 发版检查清单

打 `v*` tag 会跑 `desktop-build.yml`：

1. Secrets 已配（签名私钥；启用前端 Sentry 时还需 DSN 与上传令牌）。
2. `src-tauri/tauri.conf.json` 的 `version` 已 bump（updater 用这个和 `latest.json` 比）。
3. Tag 形如 `v1.2.2`，与 conf 版本一致。
4. Release 里应有：
   - 用户手装：`AutoClip Desktop_<ver>_aarch64.dmg`、`*-setup.exe`
   - 应用内更新：`AutoClip.Desktop_<ver>_aarch64.app.tar.gz`、对应 `.sig`、Windows 安装包的 `.sig`、`latest.json`
5. 打开已装的旧版本。有新版本时先在后台下载，右下角提示重启后生效；设置 → 应用里也可以重启更新。点「稍后」只隐藏这一次提示。

macOS 更新包必须是**注入 python/backend/ffmpeg 之后**的 `.app.tar.gz`，不能用改过内容的预签名 DMG。

## 本地不签名

不设 `TAURI_SIGNING_PRIVATE_KEY` 时构建照常成功，只是没有 `.sig` / `latest.json`。自动检查失败不弹窗，下次打开会再查。下载失败会在右下角提示重试。手动检查失败会明确提示，不显示「已是最新版本」。

## 相关文件

- 前端：`frontend/src/desktop/sentry.ts`、`updater.ts`、`UpdatePrompt.tsx`
- 后端：`backend/core/sentry_setup.py`，`GET/PUT /settings/privacy`
- 壳：`src-tauri` updater / process 插件；`backend_manager.rs` 注入 `SENTRY_DSN`
- 清单：`scripts/write_updater_manifest.py`
- 隐私：`docs/PRIVACY.md` §2.4

## v1.3.1 发布验证

- 保留 v1.3.0 的 DOM 翻译防护、设置页、流水线与官网发布同步。
- SDK 发送前仅保留错误类型、代码位置、版本和构建映射标识；删除错误正文、请求、变量和 breadcrumbs，避免业务文本进入上报。
- 后端逐事件读取隐私开关，设置页保存失败时明确提示。已关闭时不发送新错误；已发出的请求无法撤回。
- 自动检查更新失败时静默；手动检查失败时明确提示，不显示“已是最新版本”。
- 本地测试不代替 Windows / macOS 安装、实际视频出片和线上 PostHog 接收验证。

### 生产构建验收记录（2026-09-21）

v1.3.1 的公开源码生产构建已上传 source maps。使用隔离的模拟 API 返回无效项目数据，触发真实 HomePage 异常，未修改发布代码，也未使用用户素材。

- [AUTOCLIP-FRONTEND-2](https://autoclip-ts.sentry.io/issues/AUTOCLIP-FRONTEND-2)，新事件 `49ee6b626ba64b3f8fe224d97234189a`。
- release：`autoclip-frontend@1.3.1`；界面语言：`zh-CN`。
- 发送的异常正文为 `[message omitted for privacy]`，映射仍准确还原到 `frontend/src/pages/HomePage.tsx:300:40`。
- 模拟触发条件已撤掉，页面恢复正常。此记录不替代实际安装包、Windows 真机和真实视频业务流程验收。
