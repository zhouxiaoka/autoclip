# 开发者指南

项目仓库：[zhouxiaoka/autoclip](https://github.com/zhouxiaoka/autoclip)。目录、维护入口与旧文件处理见 [仓库说明](REPOSITORY_LAYOUT.md)。

## 环境与验证

源码 Web 模式按 [STARTUP_GUIDE.md](../STARTUP_GUIDE.md) 准备 Python 3.11、Node.js 20 和 Redis。桌面模式使用 Tauri 和独立后端入口，打包流程以 [BUILD_GUIDE.md](../BUILD_GUIDE.md) 与 [scripts/README.md](../scripts/README.md) 为准；不要套用 Web 模式的 Redis/Celery 启动命令。

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
(cd frontend && npm ci)
python -m pytest backend/tests -q
(cd frontend && npm run lint && npm run typecheck && npm test && npm run build)
```

完整 CI 还验证生产 Docker 编排和开发编排。桌面发布必须遵守 [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)，源码合入与安装包发布是不同步骤。

## 主要入口

- Web API：`backend/main.py`，模块方式启动 `python -m uvicorn backend.main:app`。
- 桌面 API：`backend/desktop_main.py`；由 Tauri 客户端管理生命周期。
- CLI / MCP：见 [CLI_AND_MCP.md](CLI_AND_MCP.md)。
- UI：`frontend/src/`；视觉修改先阅读 [DESIGN.md](../DESIGN.md)。
- 模型与本地字幕转写：见 [AI_MODEL_CONFIGURATION.md](AI_MODEL_CONFIGURATION.md)。
- 数据模型与初始化：`backend/models/` 和 `backend/core/database.py`。

贡献流程见 [CONTRIBUTING.md](../CONTRIBUTING.md)，产品规划见 [ROADMAP.md](../ROADMAP.md)，近期事实与历史快照分界见 [HANDOFF.md](../HANDOFF.md)。
