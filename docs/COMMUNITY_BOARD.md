# AutoClip 社区看板

公开想法进 GitHub Discussions，已经决定要跟的事进 GitHub Issues，公开路线图用 GitHub Projects。
这三样都在公开仓库的免费额度里。第二阶段再考虑自建 Quackback，现在不建。

当前产品状态见 [HANDOFF.md](../HANDOFF.md)，商业化阶段见 [ROADMAP.md](../ROADMAP.md)。
`docs/PROJECT_MANAGEMENT.md` 是 2024 年的重构计划，不作为排期依据。

## 为什么现在就定这套

AutoClip 的用户已经在 GitHub 上。v1.2.1 的下载以 Windows 安装包为主，仓库里同时有桌面、Docker 和 CLI 用户。
再引入一套账号、投票和看板，等于让同一个人维护两个产品。

现在的反馈是散的：应用内一句、GitHub Issue 一堆，Discussions 开着但还是默认分类，没有公开路线图。飞书表格不再收反馈：界面有八种语言，一张中文表跟着走不了。
Issue 区曾经被「用不了」和「我觉得应该」混在一起。入口分开之后，Agent 才有稳定的地方可读。

| 方案 | 现在 | 原因 |
| --- | --- | --- |
| GitHub Discussions + Projects | 用这套 | 公开仓库免费，Agent 用 `gh` 就能读能写 |
| Quackback 自建 | 先记下，不立项 | 等非开发者反馈多到 Discussions 撑不住 |
| Featurebase / Productlane | 不用 | 免费档没有 Agent 能用的 API，付费从月费开始 |
| Linear | 不用 | 不适合作为公众提需求的地方 |

不打开 GitHub 的人用应用内反馈。它跟着界面语言走。点发送不看匿名统计开关：句子先进入 PostHog，每小时由 `.github/workflows/ingest-feedback.yml` 写进 GitHub。故障开 Issue，想法开 Ideas，其他开 Q&A。这些帖子带 `from-app` 或反馈编号，只是收件箱，不直接变成路线图卡片。邮箱不写进公开帖。没有配置或网络失败时，应用会打开预填好的 GitHub 页面。

## 三条通道

```text
用户
  │
  ├─ 想法、用法、模型、提问 → Discussions
  ├─ 能复现的故障 → Issue（bug 模板）
  └─ 不想用 GitHub → 应用内反馈（自动写入 Issue 或 Discussions）
          │
          ▼
     Product Agent 聚类、去重、排序
          │
          ├─ 先不处理
          └─ 人确认值得研究
                 │
                 ▼
            GitHub Issue
                 │
                 ▼
         AutoClip Roadmap
     Exploring → Researching → Planned → Building → Testing → Shipped
                 │
                 ▼
           Pull Request → Release
```

Discussions 里的帖子不是承诺。Issue 才是进入 backlog 的需求。Project 上的一张卡对应一个 Issue。

## Discussions 分类

对外只引导这五类。仓库里原有的 General、Polls、Show and tell 留着，说明改成把人指回下面的分类。

| 分类 | 谁来写 | 写什么 |
| --- | --- | --- |
| Ideas | 任何人 | 希望 AutoClip 支持什么。先写场景 |
| Use Cases | 任何人 | 拿它做游戏切片、播客、课程、短剧 |
| AI Models | 任何人 | 希望支持哪个模型，现在缺在名单里还是效果不行 |
| Q&A | 任何人 | 怎么用。能复现的故障仍开 Issue |
| Announcements | 维护者 | 版本、已知问题、方向变化 |

表单在 `.github/DISCUSSION_TEMPLATE/`。GitHub 不会按文件名自动绑到分类，装好分类后要在仓库设置里各选一次。

Polls 留给维护者发起投票，不作为日常入口。

## 路线图六列

Project 名称是 **AutoClip Roadmap**，设为公开。Status 只有这六列：

| 列 | 含义 | 谁能放进去 |
| --- | --- | --- |
| Exploring | 社区出现过，还没决定做不做 | Agent 可以建议，人点头后放入 |
| Researching | 值得弄清楚做法和范围 | 必须人确认 |
| Planned | 已经承诺，还没写 | 必须人确认 |
| Building | 正在做，或代码已在 main、还没发版 | 必须人确认 |
| Testing | 有包或可运行版本，等人看 | 必须人确认 |
| Shipped | 已经在某次 Release 里 | 发版说明写了才算 |

标签 `status:exploring` 到 `status:shipped` 是这六列的镜像，方便只读 Issue 的脚本。公开页面以 Project 的 Status 为准。

Agent 不可以自己把卡推进到 Planned、Building、Testing 或 Shipped。
合并 Pull Request 不等于 Shipped，发版才算。

## 人怎么说，Agent 怎么做

每天或每次你问「这周社区在说什么」：

```bash
python3 scripts/feature_signals.py --days 30
```

脚本按赞成、评论和反应排序，并用用词重叠提示可能重复。它不做语义结论。
Agent 读完后写出本周信号：哪几条是同一件事、哪几条已经有 Issue、哪几条还只是呼声。

你说「把游戏高光识别放进 Researching」时，Agent 做完这五步再停：

1. 按 [issue-body.md](community/issue-body.md) 建 Issue，标题 `[Feature] …`
2. 打上 `feature` 和对应的 `status:*`
3. 正文链到相关 Discussions
4. 把 Issue 加进 AutoClip Roadmap，Status 设成你说的那一列
5. 回讨论帖，链到 Issue

你说「最近 30 天呼声最高、还没进路线图的需求」时，Agent 只分析，不开 Issue。

## 初始看板

下面是按 2026-09-21 的仓库状态排的第一版，不是社区投票结果。
Testing 是空的：还没有一个「有包、正在给人验」的条目。已发版的历史写在 Project 简介里，不再补开 Issue。

完整字段在 [roadmap-seed.json](community/roadmap-seed.json)。

v1.3.0 和 v1.3.1 已经发布。八语界面、崩溃上报、应用内更新、失败文案、通义国际站、Docker 设置页、竖屏导出和 CLI / MCP 算 Shipped，写在 Project 简介里，不再开卡。
Building 和 Testing 现在是空的：更新日志里没有「已写完、还没发版」或「有包正在给人验」的条目。

**Researching**

- ASR 后端可插拔（#67，协议先于具体模型）
- 切片质量对照（5 分钟和 60 分钟真视频）
- Step 3 评分后端可插拔

**Planned**

- Windows 安装包真机验证
- Apple 公证与 Windows 代码签名（应用内更新已在 v1.3.1，签名还没有）
- 首页与项目卡按设计系统重做
- CLI / MCP 真视频端到端
- Intel mac 安装包
- 分块大小和合集条数接到流水线
- 竖屏三条预设人工看片

**Exploring**（提过，但没有承诺）

- 1080p60 导出
- 说话人居中裁切与封面图

## 排期

这条工作是运营规则，不改切片流水线，也不占 v1.3 的工程顺序。

1. **先把看板装上。** 跑一次安装脚本，把五个表单挂到分类上。种子 Issue 单独决定要不要开，避免一次出现十几张旧账。
2. **v1.3.1 之后按这个顺序做产品，社区新想法默认停在 Exploring：**
   - Windows 真机验证。安装包已经是下载主力，交接记录里仍没有干净机器跑通的结论。
   - Apple 公证和 Windows 代码签名。应用内更新和崩溃上报已经在 v1.3.1，未签名仍会拦住安装。
   - 首页和项目卡按设计系统重做。八语界面已经上线，这两处还是 Ant Design 默认件。
   - CLI 真视频，以及竖屏三条预设的人工看片。
3. **识别和评分的可替换接口留在 Researching。** #67 在协议写下来之前不接具体厂商。账号仍等公证和代码签名完成，不因为界面语言已经上线就提前开。
4. **新的社区需求不插到上面这几件前面**，除非它就是其中一件的复现，例如切片结果为空。

Quackback 同时满足下面三条再立项，缺一条就继续用 GitHub：

- 连续四周，Ideas 和 Use Cases 里来自非贡献者的新帖多到每周 triage 看不过来
- 应用内反馈里，不用 GitHub 的人成了多数，而 PostHog 已经不好把公开路线图做出来
- 需要一个给非开发者看的独立页面：`/feedback`、`/roadmap`、`/changelog`

到那时的路径是：Quackback 收集和投票，Agent 读它的 API，确认后的需求仍写回 GitHub Issue 和这个 Project，代码继续在仓库里走。

## 安装

预览：

```bash
python3 scripts/setup_community_board.py
```

GitHub 的接口不能创建 Discussion 分类。脚本会打印还缺哪几类、说明该怎么改；分类本身在仓库的 Discussions 设置里点一次。
标签和公开 Project 由脚本写入：

```bash
python3 scripts/setup_community_board.py --apply
```

Project 权限不够时：

```bash
gh auth refresh -s project,read:project
```

同意种子清单后再开 Issue：

```bash
python3 scripts/setup_community_board.py --apply --seed-issues
```

然后在 GitHub 仓库设置的 Discussions 里，把表单对应到分类：

| 分类 | 表单 |
| --- | --- |
| Ideas | `.github/DISCUSSION_TEMPLATE/ideas.yml` |
| Use Cases | `.github/DISCUSSION_TEMPLATE/use-cases.yml` |
| AI Models | `.github/DISCUSSION_TEMPLATE/ai-models.yml` |
| Q&A | `.github/DISCUSSION_TEMPLATE/q-a.yml` |
| Announcements | `.github/DISCUSSION_TEMPLATE/announcements.yml` |

## 明确不做

- 不让普通用户用 Issue 提「我希望」。故障仍用 bug 模板。
- 不在应用里做投票墙，也不把 Discussions 同步进数据库。
- 不用飞书表格收反馈。不用 GitHub 的人走应用内反馈。
- 不重开已经关闭的「用不了」Issue。
- 不上 Featurebase、Linear、Productlane。
