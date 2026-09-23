# 常见问题与排错

[English](FAQ.en.md) · [安装指南](USER_INSTALLATION_GUIDE.md) · [返回首页](../README.md)

## 费用、模型与数据

### AutoClip 收费吗？必须有 API Key 吗？

AutoClip 本身仍然免费、开源（MIT）。云端模型调用由你选择的服务商计费，价格、额度和可用模型以服务商为准。Ollama / LM Studio 本地预设无需云端 API Key，但需要下载模型并具备相应硬件；本地 Whisper 也需要单独安装组件和语音模型。

自 **v1.3.2** 起，海外发布需要你自己的 [Upload-Post](https://www.upload-post.com) 账号。免费档、付费档，以及 TikTok、YouTube、Instagram 等平台的每日额度，以 Upload-Post 自己的页面为准，不是 AutoClip 的承诺。

### 视频会上传吗？可以离线使用吗？

剪辑留在你的设备上，视频也保存在本机。选择云端语言模型时，字幕文本会发送到该服务商。成片只有在你点「发布」之后才会离开这台机器，发到你已经连接的平台。也可以只下载、不发布。匿名使用统计和错误报告取决于版本、构建配置和设置，详见 [隐私说明](PRIVACY.md)。发布页自 **v1.3.2** 起可用。

准备好本地视频、语言模型及语音模型后，核心本地处理无需云端模型服务。视频下载、组件安装、模型下载和更新仍需要网络。不要把“本地处理”理解为所有功能都不联网。

### 哪些视频比较适合？

分析主要基于字幕，因此对白清楚的访谈、播客、课程、口播和直播回放比较合适。音乐、体育动作和其他主要依赖画面的内容，单靠字幕可能无法识别精彩点。没有固定出片数量或效果保证。

第一次出片请自备 3–5 分钟、对白清楚的短样片，最好带时间轴准确的 `.srt`。来源可以是本地文件、B 站或 YouTube，请确认你有权使用。AutoClip 不托管官方样片，Release 里也没有样片压缩包或成片下载。

第一次出片先试这条：[Jackie Dowling | Stanford Energy Fellow](https://www.youtube.com/watch?v=dtmjLzOtx8I)（Stanford ENERGY）。示例·非托管·自担使用权。

其他示例不必都试。多为英语对白，可开官方字幕或自备 SRT/Whisper。

- [The State of Startups in 2026](https://www.youtube.com/watch?v=yslXlV2BP_Y)（Y Combinator）。示例·非托管·自担使用权。
- [Sam Altman on Astra, AGI, and the future of OpenAI](https://www.youtube.com/watch?v=VeizK1M7V7E)。第三方访谈（Sources Podcast，非 OpenAI 官方频道）。示例·非托管·自担使用权。

准备步骤见 [安装指南 · 自备短样片](USER_INSTALLATION_GUIDE.md#自备短样片)，卡点见 [讨论 #128](https://github.com/zhouxiaoka/autoclip/discussions/128)。

## 安装与启动

### 应该下载哪个文件？

[Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) 中，Apple Silicon Mac 选 `aarch64.dmg`，Windows x64 选 `x64-setup.exe`。Intel Mac / Linux 使用 Docker 或 CLI。以每次 Release 的实际资产为准，`Source code` 不是桌面安装包。Release 不提供官方样片或成片下载。

首次启动的系统提示请参考 [安装指南](USER_INSTALLATION_GUIDE.md) 和对应 Release。Windows 日常运行不需要管理员权限。

### 空白页、后端未启动或连接失败怎么办？

1. 完全退出后重新启动一次，保留数据目录。
2. 检查磁盘空间，记录界面上的具体错误和发生阶段。
3. 桌面后端端口由启动器管理，查看实际启动日志，不要假设一直是 8000。Docker 默认 Web 端口为 3000、API 端口为 8000。
4. Web 模式下若开启了浏览器网页翻译，先关闭翻译再刷新。
5. Docker 用户执行 `docker compose ps` 和 `docker compose logs --tail=100 autoclip celery-worker`，参见 [Docker 指南](../DOCKER.md)。

### 模型连接测试失败怎么办？

确认提供商、模型名、API Key、Base URL 与区域设置一致，账号拥有该模型权限。Ollama / LM Studio 要先启动服务并加载模型。本地服务默认地址分别是 `http://localhost:11434/v1` 和 `http://localhost:1234/v1`。

Docker 中的 `localhost` 是容器自己。宿主机模型服务的访问方式见 [Docker 指南](../DOCKER.md)。若出现代理、TLS 或超时错误，检查具体连接目标和网络配置；不要在反馈中粘贴完整 API Key。

## 字幕、分析与导出

### 没有字幕怎么办？支持什么字幕格式？

首页的本地上传入口支持可选 `.srt`。没有可用字幕时需要本地语音转写；先在设置中安装 Whisper 组件与模型。CLI 环境可安装 `faster-whisper`。其他字幕格式建议先转换为带正确时间轴的 SRT，不假设上传入口支持所有格式。

### 在 Windows 上安装 Whisper 仍提示 mlx-whisper 仅支持 Apple Silicon？

「设置 → 转写」里安装 Whisper 时，若 Windows 或其他非 Mac 仍出现红色错误「mlx-whisper 仅支持 Apple Silicon (macOS)」，请更新到包含 [#145](https://github.com/zhouxiaoka/autoclip/pull/145) 的下一版安装包（晚于已发布的 v1.3.2）。桌面版用「设置 → 应用 → 检查更新」，或到 [Releases](https://github.com/zhouxiaoka/autoclip/releases) 下载。旧版会误报并拦住安装；更新后点原来的「安装」即可。见 [#141](https://github.com/zhouxiaoka/autoclip/issues/141)。

### 为什么没有生成片段？

先看项目错误提示，再按失败阶段排查：

| 阶段 | 优先检查 |
| --- | --- |
| 字幕 / SUBTITLE | 字幕是否为空、时间轴是否与视频对应、Whisper 是否就绪 |
| 分析 / ANALYZE | 模型连接是否成功、返回是否可解析、字幕是否有足够内容 |
| 评分 | 是否有候选片段、阈值是否过高；可尝试从 0.7 降到 0.5 后重新处理 |
| 导出 / EXPORT | FFmpeg 是否可用、磁盘是否充足、输出目录是否可写 |

CLI 可先检查环境，再用较低阈值验证：

```bash
autoclip doctor --provider ollama
autoclip run talk.mp4 --provider ollama --srt talk.srt --min-score 0.5 --json
```

把示例文件名和模型选项换成实际配置；没有 SRT 时去掉 `--srt talk.srt` 并确保转写已就绪。降低阈值只影响筛选，不保证一定有片段。第一次验证用自备短片，或先试上文的 [Jackie Dowling | Stanford Energy Fellow](https://www.youtube.com/watch?v=dtmjLzOtx8I)。不必把示例都跑一遍。用法上仍不清楚时，到 [第一次出片问答](https://github.com/zhouxiaoka/autoclip/discussions/128) 讨论。能复现的故障仍开 Issue。

### 处理慢、内存不足怎么办？

先区分视频下载、转写、模型分析和 FFmpeg 导出哪个阶段慢。用短视频验证；关闭不必要的并发任务，尝试更小的本地模型，并检查可用内存与磁盘。转写模型首次下载可能耗时较长；重试前确认旧任务是否仍在运行。处理时间随硬件、时长、模型和导出设置变化，没有统一的“每小时视频几分钟”承诺。

### 下载 YouTube / B 站视频失败怎么办？

先确认链接可在浏览器打开、当前账号有权访问，必要时配置该平台的登录凭据。CLI / 源码环境可检查 yt-dlp 版本，桌面用户先检查新版本。也可以使用有权获取的本地文件继续处理。不要在 Issue 或邮件中发送 Cookies。

### 原始切片和发布导出有什么区别？

切片是根据时间范围从原视频生成的片段；发布导出会按预设进一步渲染，例如竖屏布局、烧录字幕和标题卡。生成切片后仍需执行导出，并播放检查结果。

```bash
autoclip export PROJECT_ID --preset shorts
```

`PROJECT_ID` 替换为真实项目 ID。其他预设包括 `douyin`、`xiaohongshu`、`bilibili` 和 `original`，详见 [CLI / MCP 指南](CLI_AND_MCP.md)。

### v1.3.2 的发布页怎么用？

自 **v1.3.2** 起可用。

切片就绪后，在切片上打开发布。海外和 B 站在同一页：

- 海外平台走你自己的 Upload-Post 账号，以及你在那里连接的平台。范围是 TikTok、Instagram、YouTube、Facebook、LinkedIn、X、Threads、Pinterest、Bluesky、Discord、Telegram、Google Business，以该账号实际连接的为准。
- B 站在设置里粘贴一次 Cookie。Cookie 须包含 `SESSDATA`、`bili_jct`、`DedeUserID`。一个 B 站账号。

可以现在发，也可以定时。B 站的定时须晚于现在两小时。标题和描述可以不填，默认用切片标题。字幕烧录默认打开。片头约 4 秒的标题卡默认打开。可见范围在平台支持时默认「仅自己」。AutoClip 对外只对 TikTok、YouTube、B 站承诺仅自己 / private。也可以只下载成片、不发布。

项目页可以查看发布记录和月历，并取消尚未发出的排期。「排这一周」只排海外平台，把还没发的切片填进周一、周三、周五的 09:00，不包含 B 站。

画幅跟着要发的账号：有竖屏账号时渲成 9:16，不按 60 秒截断。只发 B 站时用横屏。只有 LinkedIn、X 这类横屏账号时用原画。竖屏和 B 站放在同一次时，各自单独渲染。

发布时可自动生成封面，避免 B 站空封面被拒。默认封面和标题卡的细节随本版安装包说明。自 **v1.3.2** 起可用。

## 更新、备份与反馈

### 数据存在哪里？如何备份？

桌面默认目录见 [安装指南](USER_INSTALLATION_GUIDE.md)。Docker 使用仓库下的 `data/`、`logs/`、`uploads/` 绑定目录。退出应用或停止服务后，备份数据库、项目文件与配置，避免运行中只复制 SQLite 主文件。不要依赖未经确认的自动备份，也不要为了排错删除原始数据。

### 升级后项目列表打不开

桌面端和 Docker 的项目状态、类型存在 SQLite 的文本列里。服务按枚举**名字**读取（`PENDING`、`KNOWLEDGE`）。库里若还有当前版本对不上的值，整页列表会加载失败。已知的一类旧值是已经从代码移除的 `cancelled` / `CANCELLED`；写成小写 value（`pending`）时也会对不上。

自 **v1.3.3** 起，服务启动时自动改写这两个字段。项目记录保留：

- 能对上的 value 改成枚举名，例如 `pending` → `PENDING`
- 无法识别的状态（含 `cancelled`）改为 `FAILED`
- 无法识别的项目类型改为 `DEFAULT`

升级后重新打开应用，项目列表应能打开。被改写的项目会显示为失败或默认类型。升级前若要自己看一眼：

```sql
SELECT status, COUNT(*) FROM projects GROUP BY status;
SELECT project_type, COUNT(*) FROM projects GROUP BY project_type;
```

### 哪里看已知问题？怎样联系？

先查 [已知问题](https://github.com/zhouxiaoka/autoclip/issues/96) 和 [版本记录](https://github.com/zhouxiaoka/autoclip/releases)。希望增加的能力、用法和模型发到 [Discussions](https://github.com/zhouxiaoka/autoclip/discussions)：[欢迎与分类](https://github.com/zhouxiaoka/autoclip/discussions/127)、[第一次出片问答](https://github.com/zhouxiaoka/autoclip/discussions/128)、[想法](https://github.com/zhouxiaoka/autoclip/discussions/129)。能复现的故障开 Issue。规则见 [社区看板](COMMUNITY_BOARD.md)。仍需联系时，将以下信息一次性发到 [christine_zhouye@163.com](mailto:christine_zhouye@163.com)：

- 系统和 CPU 架构、AutoClip 版本、桌面 / Docker / CLI 使用方式。
- 模型提供商、模型名、视频来源与大致时长、是否提供字幕。
- 复现步骤、失败阶段、错误截图或最近的相关日志。
- 日志中移除 API Key、Cookies、私人路径和不希望公开的字幕内容。

个人业余维护，回复时间不固定，不提供即时客服或一对一部署服务。
