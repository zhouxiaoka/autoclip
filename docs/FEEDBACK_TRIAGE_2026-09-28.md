# 最新反馈排查（2026-09-28，待发布）

目标为新出现的 [#224](https://github.com/zhouxiaoka/autoclip/issues/224) 与 [#225](https://github.com/zhouxiaoka/autoclip/issues/225)。修复追加到 `codex/recent-feedback-fixes` / PR #221；不修改 #185，不自动回复或关闭反馈。

## #224：Windows 1.4.0 升级、导入和预览

### 已复现并修复

- **缩略图不是有效图片**：用真实 H.264 MP4 调旧 `_extract_video_cover`，返回成功但 PIL 无法识别。原先 `-vcodec copy` 将压缩视频包写到 `.jpg`。现在只将 attached_pic 当嵌入封面并解码为 JPEG，普通视频走按时长选帧；修复短于 1 秒素材的越界选帧，统一 UTF-8 解码及内置 ffmpeg 路径。
- **本地导入漏缩略图**：Studio URL 下载会写 Project.thumbnail，但本地上传不做。现在后台筛查时补齐，失败不阻断方案确认。真实导入 API 测试验证数据库内是可解码 JPEG。
- **探测可能无限等待**：Studio 复用的 `_probe` 没有 timeout。模拟 ffprobe 停滞已覆盖，现在最多 20 秒后返回无效媒体，进入已有失败状态，而非一直等待。这只证明修复了一个可挂起路径，不证明用户卡住的所有原因相同。
- **原片格式未保证浏览器兼容**：Studio 编辑器直接播放原片，AVI/MKV/HEVC 等素材不能保证被 WebView 解码。新增明确点击后才运行的兼容预览：独立本地 H.264/yuv420p + AAC MP4，不改原片、不调用模型。单任务、2 编码线程、最长 15 分钟、最高 1280×720，失败可重试，按源文件 stat 缓存，原子落盘；真实 AVI 测试验证输出编码、Range 206、缓存复用/失效与原片字节保持。
- **Windows 后台进程残留**：旧 Rust stop 只终止 Python 父进程；托盘退出未统一清理。新增 Windows Job Object，非继承句柄随桌面进程关闭，管理后端及后续子进程；Tauri Exit 统一 stop，停止已退出后端也清理残留。CI 回归包含“杀父进程后孙进程仍在”的旧行为与 Job 关闭后完整清理。原理见 [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)。

### 尚未证明的范围

没有报告者的素材、编解码信息和安装日志，不能把以上复现等同于用户整条故障链。Windows 安装包在真实机器上的原位升级、WebView2 播放及长素材转码仍需冒烟。兼容预览入口始终可手动展开，播放器报告错误时自动展开，便于处理“有声音但黑屏”而浏览器未报告错误的情况。

旧安装包已残留的进程不会被新代码追溯接管。遇到 `_asyncio.pyd` 正被占用，应完整退出旧应用，必要时重启 Windows 后再安装；不要跳过文件覆盖或批量结束其他软件的 Python 进程。

## #225：Windows 1.3.3 Whisper 未安装

反馈正文明确为运行时未安装，尚无证据是新的程序缺陷。现有测试已验证未安装时抛出可读的配置错误，提示「设置 → 转写」或导入 SRT，并将安装失败与未安装分开。本轮未自动下载运行时或模型，不将配置缺失伪装成成功；#221 已有结构化 warning 分类。需要用户安装运行时及模型，或提供字幕后重试。

## 验证

- 媒体/导入/Whisper 定向：72 passed；兼容预览：4 passed。
- 前端 136 项测试、typecheck、lint、build 通过。
- macOS `cargo check` 通过（指定现有 MacOSX15.4 SDK；默认 SDK 27 与本机 linker 不兼容）。
- 后端全量 639 passed、1 skipped（macOS 跳过 Windows IOCP）；末次缓存删除恢复边界单独 4 项回归通过。
- [Windows CI](https://github.com/zhouxiaoka/autoclip/actions/runs/36368556991) 在 `29342b56` 上通过：13 项 IOCP 测试、2 项真实进程树测试、完整桌面 `cargo check`。编译使用资源占位目录，不是安装包验收；后续改动仅为兼容预览缓存恢复、UI 手动入口与文档。
- [PR CI](https://github.com/zhouxiaoka/autoclip/actions/runs/36368559552) 的后端、前端、Docker 冒烟均通过。
- 本轮没有发布安装包或关闭 issue；线上旧版不会因 PR 更新而自动修复。
