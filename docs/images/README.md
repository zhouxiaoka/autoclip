# README 界面素材

## 当前 README 视频展示（2026-10-01）

八语 README 共用 16 条官网已有成片：主区精选 6 条（访谈竖版、满屏播客、横版各 2 条），其余 10 条放在折叠区。点击实际画面截图或播放链接即可打开对应 MP4；完整视频继续由官网的 R2 媒体库托管，应用仓库只保存缩略图。

[视频清单](demos/manifest.json) 记录固定的成片链接、原片来源、字幕语言、版式、实际视频时长与尺寸，以及视频和缩略图的 SHA-256。缩略图逐字节复制自官网案例库的实际帧截图，没有改绘画面或添加虚构字幕；播放时长以本地对应视频的 FFprobe 结果取整，而非生成任务的预估时长。

主区精选如下，完整清单含另外 10 条：

| 案例 | 版式 / 平台 | 字幕 | 成片 |
| --- | --- | --- | --- |
| Bill Gates | 访谈式 / 抖音 | 中文 | [截图](demos/gates-ezra-01.jpg) |
| AI Experts Debate | 访谈式 / Shorts | 英文 | [截图](demos/ai-labs-debate-01.jpg) |
| Tony Robbins | 满屏播客 / 抖音 | 中文 | [截图](demos/robbins-36months-01.jpg) |
| Andrew Garfield × Amy Poehler | 满屏播客 / Shorts | 英文 | [截图](demos/garfield-poehler-01.jpg) |
| 佟丽娅 × 鲁豫 | 原画幅 / B 站 | 中文 | [截图](demos/luyu-tongliya-01.jpg) |
| Sam Altman | 原画幅 / B 站 | 中文 | [截图](demos/altman-uses-ai-01.jpg) |

这些是官网 `2026-10-01g` 批次的公开展示素材，包含开发、验收期间的输出；官网各案例元数据并未统一记录生成时的源码提交，因此不将整个展示清单视为同一个正式安装包的全量验收证明。网站媒体经过展示用转码，清单尺寸为实际托管版本；正式安装包的验收范围见 [1.5.0 验收记录](../RELEASE_1_5.md)。原片版权归原作者，仅作效果展示，README 每张卡片均附原片链接。

更新时先核对公开媒体能访问及实际画面、版式、字幕和时长，再同步清单、缩略图及八语卡片。新增完整视频继续放在媒体库，避免将 MP4 加入应用仓库。赞助区属于独立内容，更新演示区时保持原样。

### 历史成片墙

[PR #248](https://github.com/zhouxiaoka/autoclip/pull/248) 引入的 [成片墙](v2/demo-wall.webp) 保留供历史引用，图中展示以下素材的访谈式与播客式效果：

- [Dwarkesh Patel — Dario Amodei](https://www.youtube.com/watch?v=n1E9IZfvGMA)
- [Y Combinator — Sam Altman](https://www.youtube.com/watch?v=ZIaOBAjvc38)
- [WIRED — Hideo Kojima](https://www.youtube.com/watch?v=02Ah5VQrzvA)

下方保留 1.4 界面截图的来源及制作记录，供历史引用。

## 1.4 界面预览（2026-09-29）

| 图片 | 内容 |
| --- | --- |
| [home-v1.4.0.png](home-v1.4.0.png) | 新版导入入口与项目管理 |
| [clips-v1.4.0.png](clips-v1.4.0.png) | 已完成项目的真实切片列表、评分、起止时间与操作入口 |
| [studio-v1.4.0.png](studio-v1.4.0.png) | 从真实切片打开 Studio，预览原片并调整成片设置 |

- **源码版本**：本地 `origin/main` 提交 [`ad996131`](https://github.com/zhouxiaoka/autoclip/commit/ad996131)，版本字段为 `1.4.0`，包含 v1.4.0 发布后的 Studio 处理、监控和 Windows 导入预览修复。截图不是原始 v1.4.0 标签的界面，也不代表另一个已发布版本。
- **运行环境**：独立工作树、独立端口与演示数据库副本；不使用个人项目或已保存的 API Key。原有运行环境与案例数据没有被修改。
- **案例来源**：[Sources Podcast — Sam Altman on Astra, AGI, and the future of OpenAI](https://www.youtube.com/watch?v=VeizK1M7V7E)。原片约 68 分 39 秒，使用此前 v1.4.0 正式流水线运行得到的 13 条切片、0 个合集；本次仅在新版界面中展示已有结果，没有重新调用模型。
- **结果边界**：标题、推荐理由、分数与时间范围保留原始模型输出，分数不是传播效果或内容真实性指标；截图不构成对生成标题或观点的背书。案例字幕和生成标题为英文，UI 为中文。
- **Studio 状态**：在演示副本中从已有切片创建编辑草稿。画面明确标注“原片预览”，字幕、翻译和标题模板以实际渲染为准；本次没有生成或发布新成片。
- **截图方式**：上述三张图片直接截取浏览器内实际应用界面，PNG 原始保存；没有拼接、改绘 UI 或添加虚构项目、分数及结果。
- **多语言**：2026-09-29 的八语 README 共用这三张截图，并提供对应语言的图片说明。两张细节图可以点击放大。

## 功能特性配图（2026-09-29）

2026-09-29 的八语 README 曾以带边框的双列卡片展示九个功能项的缩略图，点击图片查看大图；说明随 README 语言翻译，应用画面共用。AI 内容分析复用上方真实切片列表，其余新增图片如下。

| 图片 | 展示状态 |
| --- | --- |
| [feature-import.png](feature-import.png) | 文件导入入口与已有案例 |
| [feature-collections.png](feature-collections.png) | 创建合集对话框；示例标题人工输入，未选择切片、未保存合集 |
| [feature-export.png](feature-export.png) | 导出预设与字幕、标题选项；未执行导出 |
| [feature-publish.png](feature-publish.png) | 发布入口，明确显示尚未连接发布账号 |
| [feature-cover.png](feature-cover.png) | 自动封面设置；服务未配置、自动封面关闭，未生成封面 |
| [feature-calendar.png](feature-calendar.png) | 实际空发布月历，未安排发布任务 |
| [feature-models.png](feature-models.png) | OpenAI 兼容接口设置，未填写密钥、未测试或保存 |
| [feature-languages.png](feature-languages.png) | 英文界面与语言菜单，案例内容保持原语言 |
| [feature-cli.png](feature-cli.png) | 实际 CLI / MCP 帮助输出的只读 HTML 展示页截图，非应用 GUI 或终端截图 |

功能截图沿用上述源码、独立环境和真实案例；除 CLI 展示页外，均直接截取实际应用界面。没有调用模型、创建合集、生成封面、导出或发布新成片。

CLI 素材来自在该工作树执行 `python -m backend.cli --help` 和 `python -m backend.cli mcp --help` 的成功输出：展示页选取前者的子命令列表及后者的完整帮助文本，不包含模拟任务结果。

## 历史素材

`import-local.jpg` 为 v1.3.0（`2a393f88`）的真实 Web 界面截图，摄于 2026-09-21，场景为空数据库下的文件导入页。保留用于历史引用，2026-09-29 的 README 曾替换为上方三张界面图片；当前展示素材见本文开头。

后续更新须标明实际源码提交及其与发布标签的关系，同步八语说明，并使用真实结果。不要将未渲染的预览、人工设计图或虚构数据写成实际成片。
