# Windows 验收机拉包脚本（E9）

- `pull_run_installer.sh <run_id>`：从 Desktop Build 的某次 run 拉 `autoclip-desktop-windows-x64`，在验收机 `C:\winqa\inst` 落成 `candidate-setup.exe`。
  - 必填 `WINQA_HOST`；可选 `WINQA_USER`、`WINQA_IDENTITY`、`WINQA_REPO`、`WINQA_PARTS`。
  - 不含凭据：GitHub 令牌运行时由 `gh auth token` 取，签名下载地址只经 scp 传到验收机，用完即删。
  - artifact 没有有效 sha256 digest 时退出码 4，不下载、不安装。
  - 有 `internal-desktop-provenance`（或 `internal-desktop-provenance-windows-x64`）时，解出的 exe 必须和其中记录的 sha256 一致。
- `ps/pull_run_installer.ps1`：验收机端，分段下载、校验 zip/exe 哈希；缺 digest 同样退出码 4。
- `exe_provenance.py`：CI 里给 Windows 安装包写 sha256 清单。
- `redact.py`：证据脱敏，去掉 QA key、掩码 key 和个人目录（`C:\Users\x`、`/Users/x`、`/home/x`）。
- 退出码：2 无 artifact；3 无下载地址；4 无有效 digest；5 provenance 列出但下载/解析失败；6 下载/HTTP 失败；7 哈希不符（坏分片已删）。

## 测试依赖（必需）

- `pytest backend/tests/test_winqa_scripts.py` 需要 **PowerShell 7（pwsh）**；没装时 PowerShell 用例直接失败，不会跳过。
  - macOS：`brew install --cask powershell`；Linux：见 PowerShell 官方安装说明；GitHub ubuntu/windows runner 自带。
  - 也可用 `WINQA_TEST_PWSH=/path/to/pwsh` 指定。
- 可选 `WINQA_TEST_BASH32=/path/to/bash-3.2`，额外在 bash 3.2 下跑 .sh 用例（macOS 上自动用 /bin/bash）。
- `python3` 必需（.sh 的 provenance 解析和诊断脱敏都调 python3）。
