---
name: autoclip
description: >-
  用 AutoClip 把一条 YouTube / B 站链接，或本地长视频（讲座、访谈、播客、课程），做成各平台成片、封面、发布文案和 ZIP 发布包。
  当用户要「出片」「做封面」「写发布文案」「打包发布」「从这个链接做短视频」时使用。
  只要原始高光切片、合集，或把旧切片发到 Upload-Post 时不要用这份说明，改读 references/legacy.md。
---

# AutoClip：从链接或长视频到发布包

AutoClip 在本机把一条素材做成可发布的成片。产物和桌面应用共用数据目录，桌面首页能看到同一个项目。

先调用 `get_version`（或 `autoclip --version`）读取当前安装的版本。版本号来自安装包，不要和文档里的数字核对。

## 什么时候用

用户给出下面任一输入，并且要的是成片而不是素材列表：

- HTTPS 的 YouTube 或 B 站链接
- 本地长视频的绝对路径（讲座、访谈、播客录像、课程）

交付物是四样，缺一要说明哪一样没有：

1. 按平台剪好的成片
2. 封面
3. 发布文案
4. ZIP 发布包

## 什么时候不用

- 只要带评分的原始切片和合集：读 [references/legacy.md](references/legacy.md)。
- 把已经切好的旧片段发到 TikTok / YouTube 等（Upload-Post）：同样读那份参考，不要走下面的出片流程。
- 用户只是在问 AutoClip 怎么安装、或还没有视频：先说明装法，不要空跑任务。

## 先选调用方式

1. **有 AutoClip MCP 工具** → 用工具，不要自己拼命令。
2. **没有 MCP，但能跑 shell** → `autoclip produce <source> --json`。
3. **两者都没有** → 让用户安装。Skill 用 `npx skills add zhouxiaoka/autoclip`。MCP 进程优先 `uvx autoclip-mcp`；还没有包时按 `docs/CLI_AND_MCP.md`。

模型密钥放在桌面应用的设置里，或环境变量 `AUTOCLIP_API_KEY`。不要把 key 写进工具参数或对话。

## 示例 1：链接出发布包

1. `get_version`（或 `autoclip --version`），记下返回的版本。不要对照文档里写死的版本号。
2. `start_quick_output`，`source` 用用户给的 HTTPS 链接（YouTube 或 B 站）。本地文件则先解析成绝对路径。`platforms` 用用户点名的平台；没点名时用 `douyin`。已有字幕就传 `srt_path`。
3. 立刻拿到 `project_id`。按返回里的 `poll_after_sec` 调用 `get_quick_output_status`；没有这个字段时每 10 秒查一次。
4. 每次把 `progress`、`stage`、`eta` 用一句话告诉用户。终态是 `completed`、`partial`、`failed`、`interrupted`、`cancelled`。`unknown` 表示没有这条任务，不要把它说成已完成。
5. 终态后再查一次，并带 `export_kits=true`。把每条成片的视频、封面、文案和 ZIP 路径交给用户。
6. `partial`：交付已经完成的版本，说明失败的平台，不要把整单再提交一遍。`interrupted`：进程已经不在，已完成的成片仍可取，未完成的要用户决定是否重做。

没有 MCP 时：

```bash
autoclip produce "https://www.youtube.com/watch?v=VIDEO" --platform douyin --platform youtube_shorts --json
autoclip outputs PROJECT_ID --export-kits
```

`youtube_long` 只生成至少 180 秒的完整片段。短素材改用 Shorts 或 B 站。

## 示例 2：选剪辑风格

风格 id 只有三个：`editorial`（杂志风）、`street`（街头快剪）、`classic`（经典）。竖版版式 `portrait_style`（`auto` / `interview` / `podcast`）只改竖版布局，不代替剪辑风格。`template` / `--template` 只在 `mcp_v2_tools` 打开时接受。不支持的值返回 `invalid_input`。

1. 如果工具列表里有 `list_styles`，先调用它，把 id 和名称给用户选。没有这个工具时，直接使用上面三个 id。
2. 用户选定后，MCP 在 `start_quick_output` 上传 `template`。命令行用 `--template`。开关关闭时不要传；不传则按经典制作。
3. 以返回结果里的风格为准。`template` 是实际用的风格，`requested_template` 是请求值。`pkg_templates_v1` 关闭时，即使请求了杂志风或街头快剪，实际风格也是 `classic`。
4. 其余步骤与示例 1 相同：轮询到终态，再 `export_kits=true`。

```bash
autoclip produce talk.mp4 --template street --platform douyin --json
```

```json
{"source":"/absolute/path/talk.mp4","platforms":["douyin"],"template":"editorial"}
```

不要发明 `magazine` 或其他 id，也不要额外加风格参数。那些留到后续版本。

## 示例 3：批量

多个链接或多个本地文件时，一次只提交一条。不要并行开多条任务。

1. 和用户确认平台和风格（风格可省略，省略则不传 `template`）。
2. 对第一条调用 `start_quick_output`，记下 `project_id`。
3. 按 `poll_after_sec`（没有则 10 秒）轮询到终态，导出发布包。
4. 再提交下一条。全部结束后做一张表：来源、`project_id`、状态、发布包路径。失败的单独列出，不要为了补齐而重跑已经成功的条目。

没有「一次传入多条 source」的参数。不要自造 `sources` 数组。

## 平台

`douyin`、`xiaohongshu`、`bilibili`、`tiktok`、`instagram_reels`、`youtube_shorts`、`youtube_long`。`reels` 和 `shorts` 是别名。

中文平台用中文，英文平台用英文。横版保持 16:9。

## 出了问题先看这里

| 问题 | 去哪 |
|---|---|
| 链接或本地视频 → 成片、封面、文案、发布包 | 本文示例 1 |
| 选杂志风 / 街头快剪 / 经典 | 本文示例 2 |
| 多个链接排队 | 本文示例 3 |
| 原始切片、合集、评分、Upload-Post | [references/legacy.md](references/legacy.md) |
| 安装、命令、数据目录 | `docs/CLI_AND_MCP.md` |

给用户结果时列出：平台、状态、视频路径、封面路径、文案标题、ZIP 路径。路径给全，但不要把密钥或环境变量值打出来。
