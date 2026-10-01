# 1.5.0 发版验收与同事测试

更新：2026-10-01。桌面配置、Cargo、Python 包、CLI、MCP 均为 **1.5.0**。

## 正式 tag 与交付入口

[PR #250](https://github.com/zhouxiaoka/autoclip/pull/250) 已合并，tag `v1.5.0` 固定在 main `e940f5aef485409b13950c405fab6a9344376c88`。PR 和 [main 全量 CI](https://github.com/zhouxiaoka/autoclip/actions/runs/36872311072) 全绿，Windows 异步连接清理专项也通过。

最终包由 [tag 双平台构建](https://github.com/zhouxiaoka/autoclip/actions/runs/36873288668) 生成；[1.5.0 Release](https://github.com/zhouxiaoka/autoclip/releases/tag/v1.5.0) 已正式发布为 latest。9 项公开资产的 SHA256 已核对，macOS / Windows 更新包签名均验证通过，公开 `releases/latest/download/latest.json` 已确认返回 1.5.0。下方候选包名称是历史验收记录，`ee73e594` 包尚未包含最后的 YouTube 长视频修复。同版本候选更新必须强制重装，不能只检查 `--version`。

正式 Windows 安装包的 [CI 冒烟](https://github.com/zhouxiaoka/autoclip/actions/runs/36876463485) 通过：1.4→1.5 覆盖升级、桌面窗口与内置后端、provider 配置、本地视频 + SRT 处理及正式 wheel 人物检测/字体。模型端为本机协议 fixture，无新增付费调用。macOS 正式包的内置后端、六种文字模板，以及中文播客 / 英文播客 / 英文访谈的实际取景、字体和片尾均通过；公开 wheel 已在 checkout 外冷安装验收。

本次按负责人尽快正式发布的要求推进。Windows 没有人工真机界面验收，完整观察期尚未完成；这两项限制已在正式 Release 中明确，官网由负责人另行更新。分支 `worktree-project-diagnosis`，接手基线 `723eefbd`；该基线与下方候选包状态均为历史记录。

### 社区 issue 收口

按负责人要求，25 条相关发布 / 验收 / 复现说明已回复，补齐此前“已合入但未发布”的正式下载入口。[置顶 #96](https://github.com/zhouxiaoka/autoclip/issues/96) 已更新为 1.5.0；[说话人裁切与封面 #115](https://github.com/zhouxiaoka/autoclip/issues/115) 已按 completed 关闭并标记 shipped，其他已结案修复保留原关闭状态。新的 Whisper 反馈 [#247](https://github.com/zhouxiaoka/autoclip/issues/247) / [#249](https://github.com/zhouxiaoka/autoclip/issues/249) 已说明升级与补日志步骤，保持开放并标记 needs-info；#116 质量对照、#124 人工看片、#119 系统签名和 #122 Intel Mac 包仍保持开放，不将本次发版冒充这些事项完成。

## 这轮完成的验收修复

- 成片卡片只保留「复制发布文案」，实际复制不附 AutoClip 署名。原来的增长文案是「用 AutoClip 剪的 · GitHub 地址」；视频片尾仍是独立的品牌功能。
- 设置 → 应用增加自动品牌片尾开关，默认开启。影响后续自动制作、备选片段和自动草稿的编辑导出；已生成的视频不改写。记录实际追加结果，片尾失败时保留正文视频。
- 导入页提供竖版版式：按平台默认 / 访谈式（人物窗口）/ 播客式（满屏）。平台继续决定语言、画幅和时长限制；追加平台及备选片段继承本项目选择。
- 中文播客版按两行分页；英文访谈版会过滤中文标题、字幕、点评和名牌。模板缓存同时区分场景、版式和受众语言。
- 横版长字幕分页；按画幅与字号预算单行宽度，单条字幕每屏最多两行。先在原始时间轴分页，再裁切成片；包装和编辑后的模板字幕也遵守源时间轴。
- AI 重新设计封面进入 Studio 平台流程，保留小红书等平台的比例；重复请求合并，状态如实反馈，失败保留原封面，封面写入原子化。
- 略超出源视频结尾的内容片段截断到有效时长；无效片段不再拖垮全部生成。
- 发布包在磁盘生成，桌面下载逐段写入；同名下载不会覆盖已有文件，失败时清理残缺下载。
- CLI / MCP 新入口使用桌面 Studio 的完整一键出片链路，交付视频、封面、文案和发布包；旧切片命令继续兼容。
- CLI / MCP 启动也安装 Windows Python 3.13 的断连清理修复，保持网络连接释放行为与桌面一致；其他平台与 Python 版本不改动。

## 本机验证

环境：macOS 26.6.2、Python 3.13.2；真实视频渲染使用桌面打包资源的 FFmpeg 7.1.1。
这不是安装包的覆盖升级验收，也不能代替 Windows 测试。

| 检查 | 结果 |
|---|---|
| 后端全量回归 | 最终 PR 1106 passed、2 skipped；新增字幕 / 两种版式 / 语言隔离 / headless 状态与启动 / 实际中文字体 / 长视频平台排序均覆盖 |
| 前端 | 最终 198 passed；typecheck、lint、生产构建通过 |
| Rust 下载回归 | 5 passed，包含真实分块 HTTP 响应、截断下载清理和不覆盖已有文件 |
| `python -m backend.eval` | 两个黄金案例通过 |
| `python scripts/bump_version.py --check` | 五处版本均为 1.5.0 |
| 文档 / 轻量运行时检查 | 八份 README 一致；Windows asyncio 测试隔离应用依赖后本机 13 passed、1 skipped（真实 Windows 项由 CI 执行）；相关业务回归 38 passed、CLI / MCP 23 passed |
| 浏览器 | 片尾默认开启、关闭后刷新保留；复制按钮只有一个且无署名；竖版选项可切换 |
| CLI 真实模型 | DevDay 181 秒输入 → Shorts 3 条成片，视频 / 封面 / 文案 / ZIP 齐全，实际追加片尾，无渲染警告 |
| 英文访谈窗口渲染 | 使用已生成的英文包装离线渲染 8 秒编辑片段，字幕正常、片尾成功、无警告 |
| MCP 真实模型 | stdio 客户端握手 1.5.0，调用新工具 → 中文抖音 + 英文 Shorts 共 6 条满屏版成片，完整发布包、无渲染警告 |

真实模型验收经负责人授权，仅将公开 OpenAI DevDay 片段字幕及抽样帧发送到百炼 `qwen-plus` / `qwen3-vl-plus`，AI 生图关闭。
MCP 成片时长约 45.8 / 17.7 / 87.8 秒（各两种语言），两边实际采用人物取景，中文没有被当成一个英文单词挤满画面。

### 横版满屏字幕 case

原项目 `7c3ac491-0047-4eab-b965-45ee5e87a9e3`，问题输出 `2baf754928874bb8bc3e75e5881b8610`。
原始 SRT 一条 cue 从 573.520 到 668.080 秒，约 95 秒、1518 个字符；旧横版没有 `line_limit`，整个段落被同时显示。
另一漏洞是先裁切 cue 再分页，截取中间会重新分配整段文字。现在两种路径统一先按源时间轴分页，后裁切。
同一份素材和时间范围重新渲染得到 183.07 秒、1920×1080 的成片，包含片尾、没有警告；抽查 0.3、4、64.1 秒均为两行分页。
已有成片不被改写，需要重新生成 / 导出；旧导出的字幕缓存使用新的版本键。

没有可靠词级时间的长 cue 仍按文字长度估算分页时间。本版解决排版及裁切问题，逐词同步精度仍受原始 ASR 时间质量影响；Whisper 词时间清洗按原计划延后。

## 同事拿到测试包后

### wheel 人物取景发布阻塞项（2026-10-01）

同事发现旧测试 wheel 漏打包 `face_detection_yunet_2023mar.onnx`，访谈 / 播客式因此回退到完整横画面。
源码与桌面包包含该文件；此前真实模型验收从源码运行，旧 wheel 检查只覆盖入口、字体和片尾，漏掉了新安装后的人物检测。
已修 `pyproject.toml`，同时打包 ONNX 和 MIT 许可证；CI 新增安装 wheel 后从真实访谈视频抽帧、生成两种裁切轨迹的检查。

原包保留在 `dist/rejected-cli-mcp-e23dc999/`，ZIP SHA256 为 `543c7f1f819a7d5c3981e2daa9c0b2b7a39a4b4dce3245737e0bcd5c80b2f418`，明确不可作为通过验收的版本。
同一安装包检查对原 wheel 报模型缺失，对修复后的 wheel 通过。另用 DevDay 已有素材与包装，清除所有旧取景轨迹后，从安装后的模型重新检测并渲染中文播客、英文播客、英文访谈三条短样片：1080×1920、实际片尾成功、无警告。
补测未调用付费模型，新增模型费用为零；原模型验收的记录与成本保留。复测证据在 `dist/acceptance-1.5/wheel-framing-report.json`、`wheel-portrait/report.json`。

实际成片抽查还发现字体家族名不匹配：macOS CoreText 将原 `Noto Sans SC` 回退为西文字体、中文显示方框；Linux CI 则依赖系统中文字体兜底，未使用随包字体。
已统一改用文件中的家族名 `Noto Sans SC Thin`。源码回归与安装 wheel 校验都增加真实 ASS 渲染，确认匹配随包字体且没有缺字。

桌面候选构建 `36860101368` 的 macOS / Windows 打包已通过；Windows 1.4→1.5 覆盖升级也已成功。
其安装后视频检查因测试脚本把文本连接测试的 `success` 字段错写为 `ok` 而中断，已修脚本，仍须重跑整个安装冒烟，不能计为通过。

复测已完成：代码提交 `ee73e594` 的 [全量 CI](https://github.com/zhouxiaoka/autoclip/actions/runs/36865434865) 全绿，Linux 安装 wheel 后的检测与中文字体检查通过。
[Windows 完整补测](https://github.com/zhouxiaoka/autoclip/actions/runs/36865502695) 也通过：1.4→1.5 覆盖升级、桌面启动、本地真实视频制作，以及从新 wheel 检测人物和匹配中文字体；模型调用为本机协议 fixture，无付费调用。
macOS 本机新 wheel 检查通过；三条约 46 秒的实际取景 / 字体 / 片尾样片在 `dist/autoclip-1.5.0-portrait-demo-e3e57236.zip`。
测试入口验证不能代替下节的完整界面、链接和无字幕验收；正式 tag 构建仍需使用最终源码。

本机文件在 `dist/acceptance-1.5/`；已验收代码的 CLI / MCP 安装包为 `dist/autoclip-1.5.0-cli-mcp-test-ee73e594.zip`，`dist/autoclip-1.5.0-cli-mcp-test.zip` 指向同一份新包。
包内有 Python wheel、固定依赖的 `requirements.txt`、本说明、CLI / MCP 使用指南和不含真实密钥的模型配置示例。
包不含开发者的模型配置、数据库、`node_modules` 或 benchmark 报告。测试包的哈希记录在旁边的 SHA256 文件。

```bash
# 解压到一个目录后，建立同事自己的虚拟环境。建议 Python 3.11，需 FFmpeg / FFprobe 在 PATH。
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --force-reinstall --no-deps autoclip-1.5.0-py3-none-any.whl
autoclip --version

# 复用已保存的桌面模型配置；已有字幕可跳过语音识别。
autoclip produce /absolute/path/talk.mp4 --srt /absolute/path/talk.srt --platform douyin --portrait-style podcast --json
autoclip outputs PROJECT_ID --export-kits
```

Windows 用 `.venv\Scripts\Activate.ps1` 激活。MCP 客户端的 `command` 使用该虚拟环境中 `autoclip` 的绝对路径，`args` 为 `["mcp"]`。
候选版本号仍为 1.5.0，更新旧候选 wheel 必须强制重装，避免普通安装保留旧代码。demo 前建议预装 `opencv-python-headless>=4.10`；应用也会按需下载人物识别运行库。
调用 `get_version` 后使用 `start_quick_output` + `get_quick_output_status`，示例见 [CLI / MCP 指南](CLI_AND_MCP.md)。
需要独立测试数据时设置 `AUTOCLIP_DATA_DIR`，将示例改成同事自己的连接和密钥，保存为该目录的 `ai-model-settings.json`。
本地语音识别需可用 Whisper；这轮真实模型验证使用已有 SRT，没有验证新的云端 ASR 调用或真实链接重新下载。
CLI / MCP 与桌面共用项目格式；同一数据目录制作时保持一个入口运行，另开 CLI 查询进度可以。
YouTube 横版当前要求单条完整片段至少 180 秒，因此短 demo 选 Shorts 或 B站；本轮短输入的横版请求已确认明确报无合格长片段。

## 切 tag 时的验收快照

本节记录切 tag 时的范围；正式产物后续检查及是否转为 latest 见上方 Release 与构建链接。

- [x] 最终 PR 与 main CI 全绿，按负责人 2026-10-01 的授权合并并打 `v1.5.0` tag，自动先出 Pre-release。
- [ ] Windows 安装覆盖升级、干净安装、设置保存、本地及链接导入、预览、导出、片尾关闭再导出。
- [ ] macOS 安装包同样四项；核对 1.4 的项目与模型设置保留。
- [ ] 真实链接导入和无字幕转写：桌面 / CLI / MCP 各入口检查数据和产物一致。
- [x] 正式 tag 双平台安装包、签名更新清单与 CLI/MCP 资产已核对，已转为 latest；本次按负责人尽快正式发布的要求推进，Windows 缺人工界面验收和未完成观察期已在 Release 中明确。官网由负责人另行更新。

下一版仍保留：词级时间清洗、讲解 / 录屏 / 分屏模板、并行包装的配色避让、封面设计线程优化、跨编码器拼接专项验证和低影响的反馈关闭图标。
本轮不删除原来的 `frontend/node_modules` 软链接或 `benchmarks/fast_output/reports/`。

## 发布前埋点收口与授权

2026-10-01 负责人已授权合并 main、打 v1.5.0 与发布。客户端补齐发布包、AI 封面后台终态、单条重试/备选生成、版式选择、片尾设置及实际添加/降级结果；前端 198 passed，typecheck/lint/build 通过，明细见 [埋点验收](analytics/QUICK_OUTPUT_RELEASE_1_5.md)。正式 tag 在双平台构建成功后，从同一提交构建并冷安装验收 CLI/MCP wheel，随版附无密钥 ZIP 与 SHA256。

## YouTube 长视频候选排序发布阻塞项（2026-10-01）

同事 case 03 的 21 条候选中，唯一合格长片段在全局前十之外；原版本先选前十再按 180 秒过滤，留下一个 213.306 秒的 `on_demand` 版本，没有渲染任务，generation 却持续 `rendering`。原始状态、复现与建议补丁位于同事验收目录的 `fixes/`，补丁没有应用到旧安装包。

现已按各平台先过滤资格、再从合格候选选前十。保留备选；全部候选不合格时继续明确拒绝，不降低 YouTube 长视频的时长要求。分发失败或只剩备选、没有可执行任务时补上失败终态，避免 CLI/MCP 无限等待。新增 5 个回归覆盖单条低分长片段、多平台各选前十、无合格片段、只有备选与缺草稿。

针对性回归 126 passed；最后的状态收尾和共享资格规则调整后，备选/智能导入相关回归 79 passed。原 case 03 的视频、字幕、完整候选和已精修边界在隔离目录重放，使用新安装的 wheel 与真实渲染，不触碰原失败记录，不增加模型费用。复测结果独立写入 `dist/acceptance-1.5/`，不将 B站 03R 作为 YouTube 长视频通过的证据。

安装包重放已通过：21 条候选保留、20 条短候选排除，唯一合格长片段自动生成 1920×1080、215.13 秒的视频（含实际 1.8 秒片尾），无渲染警告；自动设计封面与视频/文案 ZIP 齐全，CLI 与 MCP 独立进程都返回 `completed`。本次候选分析与边界复用原缓存，文案走无模型离线降级，不能据此宣称新的长视频模型文案验收。报告为 `youtube-long-case03-replay.json` 及对应 CLI/MCP 状态，原失败证据与成本保留。
