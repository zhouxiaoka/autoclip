# 发布到海外平台（Upload-Post）

「发布导出」把切片渲成 9:16 成片之后，原来只能下载再手动上传；B 站有一键投稿，TikTok / Instagram /
YouTube Shorts / X / LinkedIn 等没有。这条链路通过 [Upload-Post](https://www.upload-post.com) 的 API
把成片一次发到多个海外平台，与 B 站投稿并列，互不影响。

- **视频处理仍然全部在本地**：字幕、分析、剪辑、渲成片都不变，只有最终的 mp4 会上传到 Upload-Post。
- Upload-Post 是第三方托管服务（免费档每月有额度，更多用量按套餐付费），需要自己注册、连接社交账号、生成 API Key。
- 一次请求发多个平台；每个平台的结果（链接 / 错误）异步返回，AutoClip 负责轮询汇总。

入口：API（`/api/v1/publish/upload-post/...`）、CLI（`autoclip publish`）、MCP（`publish_clip`）。
桌面 / Docker / 脚本模式都可用。设置页 UI 暂未接入（见文末）。

---

## 1. 准备

1. 注册 [app.upload-post.com](https://app.upload-post.com)，在 **Manage Users** 里创建一个 profile（例如 `main`），
   把要发的社交账号连接到这个 profile 上。
2. 在 **API Keys** 生成一个 key。
3. 告诉 AutoClip（三选一，环境变量优先级最高）：

| 方式 | 做法 |
|---|---|
| 环境变量（Docker / 脚本） | `.env` 里填 `UPLOAD_POST_API_KEY=…`、`UPLOAD_POST_USER=main`（`docker-compose.yml` 已透传） |
| CLI | `autoclip publish --api-key <key> --user main --save`（会先校验 key，再写到 `<数据目录>/upload_post.json`，权限 0600） |
| API | `PUT /api/v1/publish/upload-post/config` `{"api_key": "…", "user": "main"}`（同样先校验） |

检查是否就绪、profile 连了哪些平台：

```bash
autoclip publish --list-profiles
# ● main          tiktok, youtube, instagram
#   brand         linkedin
```

---

## 2. CLI

```bash
# 把 2 号切片发到 TikTok + YouTube Shorts（自动渲 9:16 shorts 预设，≤ 60 s），并等结果
autoclip publish <project_id> --clip 2 --platform tiktok --platform youtube --wait

# 多个切片、指定预设与 profile、自定义标题
autoclip publish <project_id> --clip 2 --clip 5 --platform instagram --preset douyin --user brand --title "本周最精彩的一段"

# 横屏平台不裁切
autoclip publish <project_id> --clip 3 --platform linkedin,x --preset original --description "完整访谈见主页"

# 先私密试发：平台专属字段用 --extra key=value 透传（字段名见 Upload-Post 文档）
autoclip publish <project_id> --clip 2 --platform tiktok --extra privacy_level=SELF_ONLY
autoclip publish <project_id> --clip 2 --platform youtube --extra privacyStatus=unlisted

# 定时发布
autoclip publish <project_id> --clip 2 --platform tiktok --schedule 2026-10-01T09:00:00 --timezone Asia/Shanghai

# 查结果（提交时打印的 request_id）
autoclip publish --status <request_id>
autoclip publish --status <request_id> --wait

# 给脚本 / agent
autoclip publish <project_id> --clip 2 --platform tiktok --wait --json
```

约定：
- 不指定 `--clip` 会发项目里**全部**切片，需要加 `--yes` 确认。
- 不指定 `--preset` 时：平台里只要有 tiktok / instagram / youtube / facebook / threads / pinterest 之一就用 `shorts`（9:16 crop，60 秒截断），否则 `original`（原画重编码）。
  同参数的成片会复用「发布导出」的缓存，不会重复渲。
- 标题默认取切片标题；YouTube 必须有标题。`--description` 只有 YouTube / LinkedIn / Facebook / Pinterest 会用。
- 退出码：`0` 提交成功（`--wait` 时全部平台成功）· `1` 有平台失败 · `2` 参数 / 配置错误。
- `--wait` 每 10 秒查一次，默认最多等 600 秒（`--timeout`）。
- 每次提交在 `<项目目录>/output/publish/<request_id>.json` 留一份记录，查状态时会更新进去。

`--json` 输出（节选）：

```json
{
  "ok": true,
  "published": [
    {
      "ok": true,
      "request_id": "7b2c2f5e-…",
      "clip_id": "2",
      "platforms": ["tiktok", "youtube"],
      "user": "main",
      "title": "为什么要做本地优先",
      "preset": "shorts",
      "path": "…/output/exports/2_shorts.mp4",
      "status": "completed",
      "results": [
        {"platform": "tiktok", "success": true, "url": "https://www.tiktok.com/@…/video/…"},
        {"platform": "youtube", "success": true, "url": "https://youtube.com/shorts/…"}
      ]
    }
  ]
}
```

---

## 3. API

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/publish/upload-post/config` | 是否已配置、key 打码、默认 profile、支持的平台列表 |
| `PUT` | `/api/v1/publish/upload-post/config` | `{api_key?, user?}`；传 key 时先向 Upload-Post 校验，无效返回 401 且不覆盖旧 key |
| `DELETE` | `/api/v1/publish/upload-post/config` | 删除本地保存的配置（环境变量不受影响） |
| `GET` | `/api/v1/publish/upload-post/profiles` | profile 列表及各自已连接的平台 |
| `POST` | `/api/v1/publish/upload-post/{project_id}/clips/{clip_id}` | 提交发布，返回 `job_id`（后台先导出再上传） |
| `GET` | `/api/v1/publish/upload-post/jobs/{job_id}` | 本地任务状态：`queued / running / submitted / failed`；`submitted` 后附带 `request_id` 与 `remote`（各平台结果） |
| `GET` | `/api/v1/publish/upload-post/requests/{request_id}` | 直接按 request_id 查 Upload-Post |
| `GET` | `/api/v1/publish/upload-post/{project_id}/records` | 这个项目提交过的发布记录 |

发布请求体：

```json
{
  "platforms": ["tiktok", "youtube"],
  "user": "main",
  "preset": "shorts",
  "title": "可选，默认切片标题",
  "description": "可选",
  "subtitles": true,
  "title_card": true,
  "scheduled_date": "2026-10-01T09:00:00",
  "timezone": "Asia/Shanghai",
  "extra": {"privacy_level": "SELF_ONLY", "privacyStatus": "unlisted"}
}
```

前端只需要轮询 `jobs/{job_id}`：`status=submitted` 且 `remote.final=true` 时结束，`remote.results[]` 里每个平台有
`success / url / error / skipped`。`skipped=true` 表示该 profile 没连这个平台，不算失败。

---

## 4. MCP

| 工具 | 说明 |
|---|---|
| `list_publish_profiles()` | 配置是否就绪 + profile 列表；agent 不知道该填哪个 `user` 时先调 |
| `publish_clip(project_id, clip_id, platforms, user?, preset?, title?, description?, subtitles?, title_card?, scheduled_date?, timezone?, extra?)` | 导出 + 提交，返回 `request_id` |
| `get_publish_status(request_id, project_id?)` | 各平台结果；`final=true` 为终态 |

`skills/autoclip/SKILL.md` 里有给 agent 的使用约定（先私密试发、不要一次发全部切片等）。

---

## 5. 常见问题

- **401 / Invalid or expired token**：key 复制错或已在 Upload-Post 后台删除。`autoclip publish --api-key <新 key> --save` 重新保存。
- **没有指定 profile**：`--user` 或 `UPLOAD_POST_USER`；`--list-profiles` 看有哪些。
- **某个平台 `skipped`**：profile 没连这个平台，到 Manage Users 里连接。
- **TikTok 结果带 `fallback_to_inbox`**：发布成功，但因 TikTok 当日活跃用户上限进了收件箱草稿，需要在 TikTok App 里手动发布；
  详见 Upload-Post 文档 *reached_active_user_cap*。
- **`tiktok_privacy_unavailable`**：这个账号没有请求的 `privacy_level`（私密账号没有 `PUBLIC_TO_EVERYONE`），换一个或不传。
- **成片超过 60 秒被截断**：`shorts` 预设有 60 秒上限，横屏或长内容用 `--preset douyin`（不截断）或 `original`。
- **导出失败 / 没有中文字体**：与「发布导出」相同，见 `docs/QUALITY_AND_PUBLISH_PLAN.md`；`--no-title` 可跳过标题卡。

## 6. 后续

- 设置页「发布」区（填 key / 选默认 profile）与切片卡片「发布导出」对话框里的「发到海外平台」按钮尚未做，
  后端 / CLI / MCP 先落，UI 按 `DESIGN.md` 另开 PR。
- 参考：[Upload-Post API 文档](https://docs.upload-post.com/api/upload-video) · [状态查询](https://docs.upload-post.com/api/upload-status) · [profile 管理](https://docs.upload-post.com/api/user-profiles)。
