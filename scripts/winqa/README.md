# Windows 安装包自动验收 harness（命令行部分）

从一台 Linux/macOS 机器通过 SSH 驱动**专用** Windows 验收机（实体机或虚拟机均可，例如 Windows Server 2025 / Windows 11），
把 [RELEASE_CHECKLIST.md](../../RELEASE_CHECKLIST.md) 3.2「Windows」里**能用命令验证**的部分跑一遍，并留下证据目录。
做法与 `.github/workflows/desktop-build.yml` 的 `smoke-windows-x64` / `scripts/windows_upgrade_smoke.ps1` 一致，
区别是：真实 Windows 机器、真实交互桌面里启动的应用，上一版是真的在运行（不只是模拟残留进程）。

> 仓库里不放任何主机、账号、密码、SSH 私钥、模型地址或 API key。全部从环境变量 / 参数读。
> 证据目录默认写到仓库外；原始证据（截图、日志、JSON）不要提交，只提交人工审阅过的脱敏摘要。

## 前提

- 验收机开了 OpenSSH Server，你的公钥已加入该账号；SSH 用密钥登录（`BatchMode=yes`，不会提示输入密码）。
- 验收机上 `WINQA_USER` 有一个**已登录的交互桌面**（RDP 窗口开着即可，不要注销）。没人登录时脚本退回 session 0 直接启动，
  结果里 `mode=direct-session0`，界面相关结论不成立。
- 仓库 checkout 要和候选包同一提交（默认用本仓库根目录；CI 冒烟脚本和示例素材从这里拷到验收机）。
- **每次运行都会先卸载 AutoClip 并删除用户数据**（`%APPDATA%\AutoClip`、`%LOCALAPPDATA%\com.autoclip.desktop`、安装目录、临时冒烟目录），
  所以验收机上不要放别的东西。

## 环境变量

| 变量 | 必需 | 说明 |
|---|---|---|
| `WINQA_HOST` | 是 | 验收机地址（IP 或主机名） |
| `WINQA_USER` | 是 | 验收机 Windows 账号（需已登录交互桌面） |
| `WINQA_SSH_IDENTITY` | 否 | SSH 私钥**文件路径**；不设则用 ssh-agent / `~/.ssh/config` |
| `WINQA_REPO` | 否 | 仓库 checkout，默认本仓库根目录 |
| `WINQA_EVIDENCE_ROOT` | 否 | 证据根目录，默认 `${TMPDIR:-/tmp}/autoclip-winqa` |
| `WINQA_MODEL_API_KEY` | `--real` 时 | 真实模型 key。只经 ssh stdin 传给验收机上的 Python，不进命令行、不写盘；证据由 `redact.py` 精确脱敏 |
| `WINQA_MODEL_BASE_URL` / `WINQA_MODEL` / `WINQA_MODEL_PROVIDER` | `--real` 时 | 第 10 步保存的模型接口、模型名、提供商（也可用 `--model-base-url` / `--model` / `--model-provider`） |

## 怎么跑

```bash
export WINQA_HOST=<验收机地址> WINQA_USER=<Windows 账号>
scripts/winqa/run_winqa.sh \
  --prev      /path/AutoClip.Desktop_<上一正式版>_x64-setup.exe \
  --candidate "/path/AutoClip Desktop_<候选>_x64-setup.exe" \
  --version   <候选版本号>
# 可选：--prev-version X.Y.Z  --marker 'resources\backend\...'（只在新版存在的文件）
#       --with-asr  --no-smoke  --no-failure  --out DIR
# 续跑：--out <原证据目录> --from-step N [--to-step M]
```

真实模型场景（第 10–14 步）**会产生模型费用**，需要发版负责人授权后再跑：

```bash
read -rs WINQA_MODEL_API_KEY && export WINQA_MODEL_API_KEY   # 不要写进 shell 历史
scripts/winqa/run_winqa.sh ... --real --model-base-url <接口地址> --model <模型> [--model-provider dashscope] \
  [--bili-url <B 站公开短视频>] [--hf-mirror] --from-step 10 --to-step 14
```

安装包按哈希比对，已在验收机 `C:\winqa\inst` 且哈希一致就不会重传；网络差时分 12 片、`sftp reput` 续传。

## 步骤与证据

| 步骤 | 内容 | 证据文件 |
|---|---|---|
| 0–1 | 本地准备、上传脚本 / 安装包 / CI 冒烟用到的仓库文件 | `inputs.json` |
| 2 | 环境（系统版本、WebView2、虚拟化、包哈希）+ 幂等清理 | `env.json` `clean.json` |
| 3 | 干净安装上一版并在交互桌面启动、造数据（关崩溃报告、假 key 连接、20 秒项目） | `install-prev.json` `launch-prev.json` `seed.json` |
| 4 | 上一版**运行中** + 残留 python 占住 `_asyncio.pyd`，在用户会话里静默覆盖安装候选 | `install-upgrade.json` |
| 5 | 启动候选；`/health` 版本、设置、升级后数据保留、预检、updater 清单、无 Celery | `launch-candidate.json` `check-candidate.json` |
| 6 | 失败/回退探针（loopback 假模型，零费用）：初筛 500 回退字幕路线；分析全 500 带 `failure_stage`/`http_status`/`route`；连不上的端口 | `failure.json` |
| 7 | CI 同款冒烟：包内 Python 跑 `scripts/verify_windows_install.py --launch-desktop` | `smoke.json` `windows-smoke.json` |
| 8 | 收集应用日志（`ps/collect_logs.ps1`：后端与桌面壳日志）并脱敏 | `app-logs/`、`collect-logs-final.json` |
| 9 | 汇总 | `summary.md` `windows-rows.draft.json` |
| 10–14（`--real`） | 真实模型连接 + #266；Whisper 安装/模型下载；本地无字幕视频出片；B 站链接导入；项目列表终态 | `real/*.json` |

`windows-rows.draft.json` 按 `scripts/internal_acceptance.py` 的行格式生成：自动项只在真过了才写 passed，界面项保持 pending；
`summarize.py` 里的回归行 id 跟版本走，每个版本按本版 CHANGELOG 调整。

## 仍需人工 / 界面的部分

脚本**不能**给出 passed：首次引导和设置页真实保存/重启、真实模型出片后的预览与原生保存导出（亲眼看首/中/尾）、
导入页拦截与修复入口的界面表现、YouTube（验收机需代理）、视觉生成、失败后的界面重试入口、隐私监控（需 validation 构建）、
首页卡片状态。VM 上没有界面的项（WebView2 画面）要人工看截图确认，并在记录里注明「虚拟机」与系统版本。

## 文件

- `run_winqa.sh`：入口（在控制机上跑）。
- `ps/*.ps1`：上传到验收机 `C:\winqa\ps`。只用 ASCII（Windows PowerShell 5.1 按 ANSI 读无 BOM 文件）。
  `common.ps1` 的 `Start-Interactive` 用一次性计划任务（`LogonType Interactive`）在已登录用户的桌面里启动应用。
- `py/winqa_probe.py`：`seed` / `check` / `failure`，用包内 Python 跑，只调 127.0.0.1。
- `py/winqa_real.py`：`model` / `whisper` / `local` / `link` / `final` 真实场景；key 只从 stdin 读。
- `summarize.py`：证据目录 → `summary.md` + `windows-rows.draft.json`。
- `redact.py`：按 `WINQA_MODEL_API_KEY` 精确替换证据里的 key 和应用的打码形式。它是 scripts/winqa 下唯一的脱敏实现：`py/winqa_probe.py`、`py/winqa_real.py` 的 `save()` 先对整个结果（`scrub_obj`）脱敏再落盘，第 1 步随 py/ 一起上传。控制机本地从不留原文：实时日志逐行经 `redact.py --lines` 再写 run.log；拉回的文件先在验收机上脱敏（含 app-logs.zip 内的文件），再在私有临时目录里带真实 key 脱敏一遍，失败的文件直接丢弃，之后才进证据目录；任何中断都由 trap 删除临时目录并再脱敏一遍证据目录。验收机上没有可用的 Python 时，app-logs.zip 移到 `C:\winqa\raw`、不拉回（原始日志只留在验收机上）。

## 验收机拉包脚本（E9）

- `pull_run_installer.sh <run_id>`：从 Desktop Build 的某次 run 拉 `autoclip-desktop-windows-x64`，在验收机 `C:\winqa\inst` 落成 `candidate-setup.exe`。
  - 必填 `WINQA_HOST`；可选 `WINQA_USER`、`WINQA_IDENTITY`、`WINQA_REPO`、`WINQA_PARTS`。
  - 不含凭据：GitHub 令牌运行时由 `gh auth token` 取，签名下载地址只经 scp 传到验收机，用完即删。
  - artifact 没有有效 sha256 digest 时退出码 4，不下载、不安装。
  - 有 `internal-desktop-provenance`（或 `internal-desktop-provenance-windows-x64`）时，解出的 exe 必须和其中记录的 sha256 一致。
- `ps/pull_run_installer.ps1`：验收机端，分段下载、校验 zip/exe 哈希；缺 digest 同样退出码 4。
- `exe_provenance.py`：CI 里给 Windows 安装包写 sha256 清单。
- `redact.py`：证据脱敏，去掉 QA key、掩码 key 和个人目录（`C:\Users\x`、`/Users/x`、`/home/x`）。唯一实现：按编码（BOM / utf-8 / gb18030）严格解码、逐层还原转义后线性扫描，原编码和换行写回。`pull_run_installer.sh` 的全部输出（gh、curl、ssh、scp、远端 ps1、清理步骤的 stdout 和 stderr）都经 `redact.py --stdin`；redact 出错时输出丢弃、脚本非 0 退出（运行本身成功时退出码 8）。`ps/pull_run_installer.ps1` 自己不脱敏，**不要在 Windows 上手动直接运行它来收集证据**。边界规则：根目录后的名字从分隔符一直遮到下一个真正的分隔符（POSIX 只认 `/`，Windows 认 `\` 和 `/`）或行尾；原文、逐层解码后、各候选编码几种读法的遮盖范围取并集。样本表：`backend/tests/fixtures/winqa_redact_corpus.json`。
- 退出码：2 无 artifact；3 无下载地址；8 诊断脱敏失败；4 无有效 digest；5 provenance 列出但下载/解析失败；6 下载/HTTP 失败；7 哈希不符（坏分片已删）。

### 测试依赖（必需）

- `pytest backend/tests/test_winqa_scripts.py` 需要 **PowerShell 7（pwsh）**；没装时 PowerShell 用例直接失败，不会跳过。
  - macOS：`brew install --cask powershell`；Linux：见 PowerShell 官方安装说明；GitHub ubuntu/windows runner 自带。
  - 也可用 `WINQA_TEST_PWSH=/path/to/pwsh` 指定。
- 可选 `WINQA_TEST_BASH32=/path/to/bash-3.2`，额外在 bash 3.2 下跑 .sh 用例（macOS 上自动用 /bin/bash）。
- `python3` 必需（.sh 的 provenance 解析和诊断脱敏都调 python3）。
