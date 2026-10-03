# 测试与发布验收工作流

负责人：实现者负责复现、修复和源码检查；验收者负责最终安装包与场景记录；发布负责人核对证据后转正。个人开发时可以由同一人承担，但三个阶段分别留证据，不能用前一阶段代替后一阶段。

## 1. 本次复盘和验收原则

1.5.0 暴露出四个缺口：旧配置的可选封面会挡住整个模型设置；重试拦截器重置预算，单次故障可变成持续请求；出片失败码没有走完持久化与统计链路；自动出片已上线，旧看板查询仍只覆盖手动流程。现有单测和构建没有充分覆盖这些边界。后端通用 lint 还设置了失败继续，未定义变量可以长期留在代码中。

本流程以用户能完成的任务作为验收单位。绿色 CI 是源码检查证据；成功启动是安装证据；完整链路的可播放文件才是交付证据。模拟供应商验证协议与恢复，真实供应商验证服务兼容性与内容结果，分别记录。

先完成未打标签的内部安装包产品验收，再创建公开候选；内部发现缺陷继续修复同一个未公开编号。Internal Acceptance 的不可变回执绑定源码 SHA 和包哈希，tag 构建缺少回执或源码不符就阻断。标签后的最终包验收与观察仍保留。远端 main 已要求源码合同、后端、前端、两种 Docker 链路、Windows IOCP 与 Windows 媒体回归七项检查，管理员同样受约束；禁止强推和删除 main。手工点击 GitHub 的转正按钮仍可绕过发布工作流，因此发布负责人和仓库代理必须遵循最终安装包验收要求。

## 2. 从问题到修改

| 阶段 | 必做工作 | 完成证据 |
|---|---|---|
| 定级、定位 | 最新版本/平台/构建、反馈、Sentry 栈、PostHog 分母和终态；把未知与根因分开 | 问题与复现条件；仅本地保存原始生产资料 |
| 复现 | 在临时数据目录构造触发条件；避免使用真实密钥/用户素材 | 修复前回归失败，或真实安装包明确复现 |
| 修复 | 最小修改；检查相邻失败路径；用户可恢复；保存旧数据 | 修复后同一用例通过，相关回归通过 |
| 源码验收 | 完整统一检查；review diff；更新八语文案/事件契约/CHANGELOG | 命令、提交、未提交改动、检查结果 |
| 内部安装包 | 未打标签分支的 Desktop Build；双平台构建、签名、安装/升级和内置运行时检查 | 成功 build run；双平台 Actions artifacts + internal provenance |
| 标签前产品验收 | 下表所有必测场景；每条发布变更有对应结果；失败就继续内部修复 | 匹配提交/包哈希的记录；Internal Acceptance 成功 run |
| 公开候选及最终包验收 | 被验收源码才可打标签；exact tag CI；最终包核对和受影响场景复验 | tag 中的内部验收 run；完整 Release assets 与最终证据 |
| 观察、转正 | 有样本的 Pre-release 观察；确认无阻断；实名复核 | Release Acceptance 成功 run；转正后线上核对 |

高风险修改包括配置迁移、API 重试、模型路由、任务状态、数据库、运行时安装、文件保存和监控。review 必须追踪到真实调用方，覆盖成功、失败、恢复与数据保留。普通文案/样式改动按影响范围检查；不要求为每个可逆小改动堆砌单测。

## 3. 源码检查：一个入口

在隔离 checkout 安装 `requirements.txt` 与 `requirements-test.txt`（固定 Ruff / NumPy 测试依赖）、前端 `npm ci`；媒体测试需要 ffmpeg/ffprobe 和中文字体。然后运行：

```bash
python scripts/quality_gate.py --report /absolute/local/evidence/quality.json
```

开发中可以加 `--group contracts`、`--group backend` 或 `--group frontend` 做局部验证。发布必须运行全部组，且让目标 tag 的 CI 再跑一次；本地 Python 版本与发布 portable Python 有差异时，分别记录。

| 组 | 自动阻断项 |
|---|---|
| contracts | 版本一致、八语 README/链接、发布验收校验器的负例回归 |
| backend | 媒体测试依赖就绪、Python 正确性 lint（E9/F63/F7/F82）、全部后端 pytest、离线剪辑质量约束 |
| frontend | ESLint、TypeScript、全部前端测试、生产构建（禁止测试时上传 sourcemap） |
| CI 额外项 | Windows IOCP/进程树/桌面编译、真实 YuNet 并发检测与 SenseVoice 状态文件、安装 wheel 的取景/字体、源码启动与停止、Docker 生产/开发链路 |

runner 创建临时数据库、配置、日志和隐私关闭文件，清空继承的供应商凭据与监控 DSN/公开采集 key，并隔离 Redis 地址。测试须使用 mock 或本机协议 fixture，禁止调用付费模型；真实模型调用移到产品验收，先明确素材、供应商、模型和费用预算。runner 会保留失败状态，不会被后续成功覆盖。缺依赖也算失败；退出码非零就不能宣称通过。

外部 Upload-Post HTTP 探测默认跳过（仅验证无效 key 的只读响应，不投稿）；需要时单独用 `AUTOCLIP_LIVE_NETWORK_TESTS=1` 运行并记录网络结果。源码门槛固定关闭该探测，使用 loopback 测试；Windows IOCP 在其他平台的 skip 由 Windows job 补验，不能当成通过。runner 读取本次 pytest 的 JUnit 结果，只允许这两类跳过；缺 NumPy、OpenCV、ffmpeg、字体等导致其他用例跳过时，整个检查失败。OpenCV 仅加入测试依赖，真实 YuNet 回归交替检测示例人物和空画面；共享检测器曾在并发时把不同素材的结果混在一起，不能用 mock 替代该回归。

当前通用 Ruff 的格式/未使用导入等存量问题仍以 advisory 报告；会造成运行错误的正确性规则已独立阻断。处理存量风格问题应分批提交，不在紧急补丁里混入大范围整理。

Desktop Build 除统一源码 CI 外，还必须通过 Windows Whisper 恢复/真实离线转写，以及三平台 SenseVoice 实际安装、模型下载与离线转写。原有这两套工作流只有 PR 路径触发，不能当成 tag 已验证；现在复用为构建的依赖，校验器核对目标构建中的实际 job。开发 Python 上的真实转写仍须由最终安装包产品矩阵补验。

终端用户不应为可选 ASR 安装编译工具。Python 3.13 下 editdistance 缺少上游 wheel，开发 CI 曾因自带编译器而掩盖安装包失败。桌面构建现用同一 portable Python 预编译、离线安装并加载原生 wheel，随 backend 提供；两平台的安装包阶段还运行真实 SenseVoice 准备、模型下载和离线转写，防止仅源码环境可用。模型网络下载失败仍是红灯，不以 wheel 检查代替完整准备。

## 4. 最终安装包的必测矩阵

以下 **Windows x64、macOS arm64 均必测**。Windows ARM 虚拟机运行 x64 包时明确记录仿真；不能把它写成原生 x64 真机。CI 的 Windows 安装脚本补充内置运行时与协议证据，仍需真实桌面 UI 和真实模型验收。没有可用 Windows 环境时保留 NO-GO，先补环境或取得经授权的测试者证据。

| case ID | 场景与通过标准 |
|---|---|
| clean_install | 干净安装；打开真实 UI；首次引导、模型设置、退出/重启正常；使用包内 Python/ffmpeg |
| upgrade_legacy | 从上个正式版与本次受影响版覆盖升级；旧项目/密钥保持；无效封面、未配置可选组件不挡模型设置；SQLite 占用可恢复；退出旧后端 |
| model_settings | 分析/视觉/ASR/封面独立配置与保存；重启仍正确；无效 key/地址可解释并修正；无无限 Loading/请求 |
| local_with_subtitles | 自有/授权口播视频和 SRT → 一键出片 → 目标平台成片；通过真实分析服务；确认字幕、声音、标题、完整内容边界 |
| local_without_subtitles | 无字幕语音素材；所选 Whisper/SenseVoice/云 ASR 就绪后真实转写并出片；组件未就绪时及时说明；安装/下载中断后可恢复；本版涉及的 ASR 路线逐一补测 |
| link_import | YouTube 或 B 站真实链接 → 下载进度 → 字幕/转写 → 出片；目标平台/下载器修改时两站都测；失败保留可重试入口 |
| visual_generation | 游戏/无口播素材 → 真实视觉服务 → 出片；验证帧发送同意、时长/内容结果；未配置或取消授权有明确结果 |
| failure_recovery | 注入持续 500/429/超时/离线；请求预算有限、写请求不自动重放、任务离开 running；修正后重试成功；已有成片/项目保留；断开后重开 UI |
| output_delivery | 预览和原生保存；文件非空，ffprobe 有正确时长/画幅/音视频轨；全文件解码无错；亲眼播放首/中/尾；封面、字幕、片尾、ZIP 发布包和中文/空格路径正确；保存失败无残缺成品 |
| privacy_telemetry | 关闭统计/崩溃报告无新请求；验证构建的自动出片成功/失败终态、受控错误码、flow 关联与重复观察去重实际入库；对应查询必须包含 studio_generation_finished |

包的 SHA-256 必须来自 Release 下载文件；每个平台记录系统、机器/虚拟化、portable Python、供应商/模型（不含 key）、输入素材类型和费用。离线 loopback 完整流水线不能填写“真实模型通过”。已有 case 可复用方法与合法素材，换包、重打构建或改变代码要重跑受影响场景；转正器会拒绝旧哈希与构建前的记录。

Privacy/telemetry 使用独立 validation 构建和隔离数据目录（前端 `VITE_TELEMETRY_VALIDATION=true`；受控后端进程使用 `AUTOCLIP_BUILD_ENVIRONMENT=validation` 并明确标记测试 scope，见 [监控说明](analytics/STUDIO_MONITORING.md)）；它是同一提交的补充证据，**不替代最终生产安装包**。桌面启动器会注入 production/development，验收时需核查实际事件标签。生产包检查版本标记与关闭采集，validation 检查最终收数。不要把验收事件塞入生产成功率。

自动制作在生成版本前失败的恢复验收，还需从真实结果页确认重试入口，修正前置条件后沿用原素材和所选平台完成出片；validation 收数应保留同一 flow、不同 attempt 的失败与成功，各尝试重复观察只入库一次。

每条修复和新功能还需列入 `regressions`，写明 issue/变更 ID、触发条件、实际平台、预期与结果；一个 happy path 不代表整个发布说明通过。首次出片时间、费用、画幅、语种、字幕同步、切点与包装质量须按素材记录，性能声明需要与上一版同条件对照。

自动出片的 validation 查询模板见 [release_validation.sql](analytics/release_validation.sql)，逐条运行并替换版本；缺 flow 或失败码需要调查。上线新流程时同步更新实际看板，不能只在仓库增加 SQL 就宣布线上监控已覆盖。

生产看板 02/03/04 已补入自动出片终态：交付、失败构成与示例后真实渲染都覆盖 `studio_generation_finished`。事件、设备、非空 flow 和非空 artifact 分开计数；自动生成没有逐文件 artifact ID 时不能把 variant 属性累计值当成去重文件数。历史失败码留空，partial 单列；看板修正不能回填旧事件，也不能证明新安装包的收数已通过。

## 5. 可校验的验收记录

### 标签前的内部验收

先在未打标签的候选分支准备拟发布的版本号，再运行双平台 Desktop Build。现有公开编号不能用于新内部构建，防止把另一份代码混入已公开版本的监控/包身份。Actions 下载目录应含两个平台的包和签名，以及 `internal-desktop-provenance` artifact 内的 `internal-build-provenance.json`。此时不创建 Release。

```bash
python scripts/internal_acceptance.py init \
  --version X.Y.Z --commit FULL_40_CHAR_SHA --build-run-id BUILD_RUN_ID \
  --assets /absolute/local/internal-assets \
  --manifest /absolute/local/internal-acceptance/internal-acceptance.json
```

记录初始全部 pending。两个平台完成全部必测矩阵与每条修复后，填写场景、回归的实际完成时间、证据、环境、blockers 和实名复核；回归还需记录具体平台。时间须晚于该内部构建完成。未知主流程失败、缺失场景、CI 代替产品验收或包/源码不符，都不能通过。

人工审阅脱敏后，把内部 manifest 与摘要提交到独立证据分支，例如 `docs/internal-builds/COMMIT/`。不要为了提交报告改变被验收源码 SHA。运行 **Internal Acceptance**，输入源码 SHA、内部 build run ID 和 manifest 路径；它重新下载 Actions 包并校验全部哈希、provenance、构建 checks、双平台场景、回归与复核，生成不可变的 `internal-acceptance` artifact。它不打标签、不发布。

获授权的版本只有在上述 workflow 成功后才可创建 annotated tag。标签必须指向被验收的源码提交，注解有独立一行 `Internal-Acceptance-Run: RUN_ID`。tag 的 Desktop Build 会检查回执来自成功的 Internal Acceptance，版本和完整源码 SHA 完全一致；缺失/失败/不符就阻断构建发布。代码、依赖声明或版本变化后要重新内部构建和验收，不能复用旧回执。

### 标签后的最终包与观察

完成候选构建后，从 Release 下载全部 assets 到本地目录。生成空模板：

```bash
python scripts/release_acceptance.py init \
  --tag vX.Y.Z --commit FULL_40_CHAR_SHA --build-run-id BUILD_RUN_ID \
  --release-type hotfix --assets /absolute/local/release-assets \
  --manifest /absolute/local/acceptance/acceptance.json
```

模板全部是 pending。按真实结果填写 `platforms`、`regressions`、`blockers`、`observation`、`approval`。每个场景的 `evidence` 是同目录内非空的脱敏 Markdown/JSON 等记录；可以共享一个详实的记录文件，但必须逐场景写结果，不得把“已执行测试”当成通过。时间使用含时区的 ISO 格式。

原始截图、用户素材、模型响应和生产监控导出只保留本地；证据摘要剔除密钥、机器个人路径和身份。人工审阅脱敏后，仅把 `acceptance.json` 与必要摘要放到 `docs/releases/vX.Y.Z/` 并提交。机器校验能验证完整性与一致性，不能代替验收者对内容真实性的负责。

Pre-release 常规观察至少 **24 小时**，hotfix 至少 **4 小时**。两个平台都需要至少一个实际测试/试用设备及一个完成流程；零事件不能证明没有问题。观察记录包含：采样范围、设备与 flow 去重口径、自动生成成功/失败/保存情况、主要 Sentry code/phase、最新反馈、与旧版对比及样本不足的限制。未知原因的主流程失败要作为 blocker，不能填写 passed。部分可接受的降级要有明确范围、可恢复路径与验收结果。

Desktop Build 发布前自动生成 `build-provenance.json`，记录源提交、run ID 和最终文件哈希；人工重新填写哈希不能让另一份包冒充该构建。

运行 **Release Acceptance**：输入 tag、该 tag 成功的 Desktop Build run ID、已提交的 manifest 路径。它检查源码/构建 job、版本、构建 provenance 和所有 asset 哈希、更新地址/签名、双平台场景、修复、观察样本、时间顺序、无 blocker 和实名复核，再保存不可变的 `release-acceptance` Actions artifact。

运行 **Promote / Halt Release** 的 promote 时必须传成功的 Acceptance run ID。它重新取当前 tag、Release assets 与 build 状态再校验，确保验收之后没有换包。缺证据时流程失败。halt 不受验收门槛阻碍，仍需明确的好版本作为回退目标。

## 6. 转正后与故障闭环

发布负责人核对 Release latest、双平台下载/签名、latest.json 版本/地址与官网；在新版本有真实生产样本后核查自动生成终态与保存、错误码/最新反馈。发现主流程集中失败、升级损坏或数据风险时停止扩大升级，按 [发布清单](../RELEASE_CHECKLIST.md) halt 并前向修复；已升级用户不能靠 updater 自动降级。

这里只规定检查点，没有偷偷创建新的定时任务或更改告警接收人。确需持续监控时在得到任务授权后配置现有平台告警/桌面 heartbeat。关闭 issue 必须对应已发版本及该反馈条件的确认；旧 Whisper “已安装但不可用”报告不能用新的缺组件事件代替验收。

每次生产缺陷补齐三个记录：为什么原有门槛漏掉、哪个自动/安装用例现在能抓住、在哪个实际包验证。源码检查失败先修；安装验收失败保持候选；发布后的事故不要靠增加版本频率掩盖。

## 7. 入口

- 仓库执行约束：[AGENTS.md](../AGENTS.md)
- 统一源码检查：[quality_gate.py](../scripts/quality_gate.py)，[CI](../.github/workflows/ci.yml)
- 内部构建与标签前验收：[Desktop Build](../.github/workflows/desktop-build.yml)、[internal_acceptance.py](../scripts/internal_acceptance.py)、[Internal Acceptance](../.github/workflows/internal-acceptance.yml)
- 验收校验器：[release_acceptance.py](../scripts/release_acceptance.py)，[Release Acceptance](../.github/workflows/release-acceptance.yml)
- 转正/撤回：[Promote / Halt Release](../.github/workflows/promote-release.yml)
- 本轮候选与缺口：[1.5.3 验收记录](RELEASE_1_5_3.md)；历史候选：[1.5.2](RELEASE_1_5_2.md)、[1.5.1](RELEASE_1_5_1.md)
