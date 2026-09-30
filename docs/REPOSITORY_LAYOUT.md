# 仓库目录与旧文件用途

更新时间不等于有效性。判断文件能否删除，要看 Dockerfile / CI / 文档 / 代码是否仍引用，以及行为是否符合当前实现。本次核查日期：2026-09-30，范围为根目录入口、构建配置及常用安装/开发文档；未对全部业务文档逐项验收。

## 当前维护入口

| 目录 / 文件 | 当前用途 |
| --- | --- |
| `frontend/` | Web 与桌面共用 UI，唯一 Node 依赖及锁文件 |
| `backend/` | Web、桌面、CLI、MCP 与转写/剪辑处理 |
| `src-tauri/` | 桌面宿主和 Rust 配置；构建使用 `cargo tauri` |
| `scripts/` | 构建、验证、社区维护与共用运行管理逻辑 |
| `docs/README.md` | 使用和开发文档索引 |
| `requirements.txt` / `pyproject.toml` | Python 依赖与 CLI/MCP 包入口，不是重复文件 |
| `Dockerfile*` / `docker-compose*.yml` | 生产 Web 和源码开发的不同容器路线 |
| `data/` / `logs/` / `uploads/` | 本地运行数据，不作为源码提交 |

## 截图中旧文件的处理

| 文件 | 核查结果与处理 |
| --- | --- |
| `docker-entrypoint.sh` | 生产镜像仍通过 ENTRYPOINT 使用。保留，改用共享数据库初始化；Redis 失败明确报错，删除虚假的“SQLite 替代 broker”提示。 |
| `docker-dev-entrypoint.sh` | 开发镜像入口被 Compose 内另一套命令覆盖。保留并恢复为唯一入口，修复构建时未复制源码就执行 build、`sh` 使用 `source`、Worker 不支持的 `--reload` 等问题。 |
| `docker-start/status/stop.sh` | 原实现只支持 Compose v1，开发模式选错配置，状态与清理范围失真。改为兼容转发器，共用 `scripts/runtime/docker.sh`，只管理选定项目。 |
| `init_database.py` | 手动维护入口仍有用途，但重复建表且提示不存在的启动脚本。保留为共享初始化入口，导入时不改变工作目录，失败返回非零值。 |
| `status_autoclip.sh` / `stop_autoclip.sh` | 仍被启动指南使用。改为兼容转发器，验证当前 checkout 的进程归属及创建时间，不再全局 `pkill`。 |
| `start_autoclip.sh` / `quick_start.sh` | Web 源码开发仍需要。实现移至 `scripts/runtime/start.sh`，合并启动逻辑，快速入口只负责后台模式；失败不再宣称启动成功。 |
| `CONTRIBUTING.md` / `.github/` 社区模板 | 贡献入口仍需维护。按现行 CI 修正测试命令与工具要求，补充 PR 模板；社区表单不再依赖旧版本号和过时供应商清单。 |
| `SECURITY.md` | 原文件含占位邮箱、伪 CVE、过时支持表和未履行承诺。重写为真实维护与联系政策。 |

保留文件名是为了让已有命令、书签和使用习惯继续生效；实现只维护一份。桌面客户端不需要用户手动运行这些 Web 管理脚本。

## 删除的冗余文件

- 根目录 `package.json` / `package-lock.json`：只有旧 Tauri 2 RC CLI，现行脚本和 CI 使用 Cargo；Node 依赖统一在 `frontend/`。
- `install_llm_dependencies.py`：SDK 已纳入 `requirements.txt` 的固定版本，旧安装器会另行无约束升级，失败也返回成功。
- `check_whisper_status.sh` / `scripts/monitor_whisper.py`：按系统命令行猜测 Whisper 任务并全局终止“重复”进程，无法表示当前进程内转写和 SenseVoice 子进程的真实任务状态。任务状态以项目页面和处理日志为准。

## 文档与历史

- 当前操作入口：根目录 README、STARTUP_GUIDE、DOCKER、BUILD_GUIDE、RELEASE_CHECKLIST，以及 `docs/README.md` 索引。
- QUICK_START_GUIDE、QUICK_REFERENCE、MULTI_LLM_PROVIDER_GUIDE 保留原链接，指向现行指南，避免维护冲突的副本。
- DEVELOPER_GUIDE 删除模板仓库地址和不存在的构建路线，引用实际维护入口。
- SYSTEM_REBUILD_GUIDE 标记为历史排障记录；HANDOFF 下方旧快照、CHANGELOG 和既有验收记录保留为可追溯证据，不作为当前操作步骤。
- 临时备份、密钥、下载模型和产物按 [归档规范](REPOSITORY_ARCHIVE_POLICY.md) 留在 Git 之外，不应因为这次整理删除用户本机数据。

以后清理文件时，先更新引用和验证受影响路线，再删除没有用途的实现；不要只根据 GitHub 的 `last year` 标签判断。
