# 贡献指南

AutoClip 接受故障修复、文档与翻译改进，以及已经确认范围的功能贡献。首次参与可先看 [README](README.md)、[仓库目录说明](docs/REPOSITORY_LAYOUT.md) 和 [当前状态](HANDOFF.md)。个人业余维护，回复时间不固定。

## 先选择反馈入口

- 可复现故障：[Bug 报告](https://github.com/zhouxiaoka/autoclip/issues/new/choose)。提供实际版本或源码提交、平台、相关模型、复现步骤、预期与实际结果，以及脱敏日志。
- 使用提问：[Q&A](https://github.com/zhouxiaoka/autoclip/discussions/categories/q-a)。先查 [FAQ](docs/FAQ.md) 与 [已知问题](https://github.com/zhouxiaoka/autoclip/issues/96)。
- 新想法与功能建议：[Ideas](https://github.com/zhouxiaoka/autoclip/discussions/categories/ideas)。说明场景与遇到的问题；较大的功能先讨论范围，再开始实现。
- 安全问题：按 [SECURITY.md](SECURITY.md) 私下联系，不在公开帖子中披露漏洞细节或凭据。

Discussions 中的想法不代表开发承诺，确认后的工作才进入 Issue 与路线图，见 [社区看板](docs/COMMUNITY_BOARD.md)。

## 准备开发环境

Fork 本仓库并克隆你的 Fork，添加上游：

```bash
cd autoclip
git remote add upstream https://github.com/zhouxiaoka/autoclip.git
git fetch upstream
git switch -c fix/your-change upstream/main
```

源码 Web 环境以 [STARTUP_GUIDE.md](STARTUP_GUIDE.md) 为准；当前 CI 验证 Python 3.11 和 Node.js 20。Python 依赖统一在根目录 `requirements.txt`，Node 依赖只在 `frontend/`，安装时使用锁定依赖：

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
(cd frontend && npm ci)
cp env.example .env
```

以上命令适用于 macOS/Linux。Windows 桌面开发与打包按 [BUILD_GUIDE.md](BUILD_GUIDE.md) 和 [scripts/README.md](scripts/README.md) 准备工具链，不要直接套用 POSIX Web 启动脚本。

Web 开发需要 Redis，准备后用 `./start_autoclip.sh`；管理命令和手动启动方式见启动指南。桌面后端由 Tauri 管理，入口是 `backend/desktop_main.py`；容器部署见 [DOCKER.md](DOCKER.md)，CLI/MCP 见 [对应指南](docs/CLI_AND_MCP.md)。

## 修改与验证

保持改动聚焦，遵循相关模块已有的结构和命名。说明解决了什么问题，以及哪些条件会触发它。UI 修改遵循 [DESIGN.md](DESIGN.md)，涉及行为变化时附截图或操作说明。翻译修改遵循 [翻译维护](docs/i18n.md)。

后端测试从仓库根目录运行：

```bash
python -m pytest backend/tests -q
# 开发时可先运行与改动相关的现有测试文件
```

前端验证使用 `frontend/package.json` 中的真实脚本：

```bash
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

CI 的后端 lint 使用 Ruff，目前是非阻塞检查；测试及前端检查仍需通过。项目没有统一配置 Black、isort 或 Prettier，不要为无关修改重新格式化整个仓库。修复可复现的代码故障时补充有意义的回归覆盖；纯文档修改检查命令、链接和对应实现即可。

涉及启动、Docker、桌面安装或平台差异时，应验证受影响路线并记录平台与结果。CI 通过不等于安装包已完成界面或真实出片验收，发布必须遵守 [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)。

## 提交 Pull Request

先检查改动，再按文件添加；下例用 `git add -p` 选择已有文件的修改，新文件需按实际路径添加。提交标题可使用 `fix:`、`feat:`、`docs:`、`refactor:`、`test:` 或 `chore:`，简述具体变化。推送分支后向本仓库 `main` 发起 PR：

```bash
git add -p
git commit -m "fix: describe the problem being resolved"
git push -u origin fix/your-change
```

按 [PR 模板](.github/PULL_REQUEST_TEMPLATE.md) 说明问题、最终行为和验证结果；有相关 Issue 时附链接。验证未覆盖的平台或步骤应明确写出，避免把未运行的检查标为通过。不要提交 `.env`、API Key、Cookie、私人素材、运行数据库、模型缓存或构建产物；文件归档规则见 [归档规范](docs/REPOSITORY_ARCHIVE_POLICY.md)。

收到审查反馈后在同一 PR 更新。较大的方案调整先在对应讨论中说明，避免把无关改动混在一起。合入源码与正式安装包发布是不同步骤；发布信息以 [Releases](https://github.com/zhouxiaoka/autoclip/releases) 为准。

## 社区与联系

尊重其他参与者，围绕问题和证据讨论；不接受骚扰、人身攻击或公开他人私人信息。一般提问优先使用社区入口，私密联系可发送至 [christine_zhouye@163.com](mailto:christine_zhouye@163.com)。
