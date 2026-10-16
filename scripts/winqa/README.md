# Windows 验收机拉包脚本（E9）

- `pull_run_installer.sh <run_id>`：从 Desktop Build 的某次 run 拉 `autoclip-desktop-windows-x64`，在验收机 `C:\winqa\inst` 落成 `candidate-setup.exe`。
  - 必填 `WINQA_HOST`；可选 `WINQA_USER`、`WINQA_IDENTITY`、`WINQA_REPO`、`WINQA_PARTS`。
  - 不含凭据：GitHub 令牌运行时由 `gh auth token` 取，签名下载地址只经 scp 传到验收机，用完即删。
  - artifact 没有有效 sha256 digest 时退出码 4，不下载、不安装。
  - 有 `internal-desktop-provenance`（或 `internal-desktop-provenance-windows-x64`）时，解出的 exe 必须和其中记录的 sha256 一致。
- `ps/pull_run_installer.ps1`：验收机端，分段下载、校验 zip/exe 哈希；缺 digest 同样退出码 4。
- `exe_provenance.py`：CI 里给 Windows 安装包写 sha256 清单。
