# AutoClip Desktop v1.3.2 发布页截图

这些是 v1.3.2（`af2012a0`，`chore: release v1.3.2`）真实界面的静帧，不是设计稿。

| 文件 | 内容 |
|---|---|
| `publish-page.png` | 切片「发布」页：平台勾选（TikTok / Instagram / YouTube / Facebook / B站）和可见范围「仅自己」 |
| `cover-preview.png` | 同一页的自动封面：本地排版封面、封面标题 / 副标题 / 角标、「重新生成封面」 |
| `publish-full.png` | 整页，只勾选 B 站，封面按 16:9 显示 |
| `cover-empty-vs-filled.png` | 还没有封面 / 已生成封面，左右对照 |

## 怎么截的

本机 `/Applications`、`~/Applications`、下载目录里没有 AutoClip Desktop 1.3.2。仓库里已有的 `.app` 是 1.1.0。当前进程没有屏幕录制权限，`screencapture` 返回 `could not create image from display`。

因此用 v1.3.2 标签构建桌面端同一份前端（`frontend/dist`，包内版本号 1.3.2），并用该版本后端以桌面模式提供页面，再用 Playwright 对页面截图（视口 1200×900，与桌面窗口一致）。页面文案是简体中文、浅色主题。

数据用的是本机已有项目「CLI 联调 3 分钟」里的一条真实切片和源视频。封面由产品自己的本地排版生成（截帧后叠标题，`method=local_overlay`），没有调用生图接口。这台机器没有已保存的 Upload-Post 密钥或 B 站 Cookie，平台列表是为了让发布页画出勾选控件而填的示例账号，图里没有密钥、Cookie 或头像。
