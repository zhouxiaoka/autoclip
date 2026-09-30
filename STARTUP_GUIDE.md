# 源码 Web 服务启动指南

普通用户优先使用 [README](README.md) 中的桌面客户端；本文用于 macOS/Linux 源码开发。容器部署见 [DOCKER.md](DOCKER.md)，桌面打包见 [BUILD_GUIDE.md](BUILD_GUIDE.md)。

## 准备环境

使用 Python 3.11、Node.js 20、Redis，以及可用的 FFmpeg。CI 使用 Python 3.11 / Node.js 20；前端依赖只在 `frontend/` 管理。

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
(cd frontend && npm ci)
cp env.example .env
```

编辑 `.env` 配置模型与 Redis，配置项见 [env.example](env.example)。macOS 可用 `brew install redis && brew services start redis`；Linux 使用发行版服务管理器启动 Redis。远程 Redis 不可用时，启动器会报错，不会用本地 Redis 或 SQLite 替代。

## 启动与管理

```bash
./start_autoclip.sh             # 前台运行，Ctrl+C 停止本次启动的服务
./quick_start.sh                # 同一启动流程，通过健康检查后转入后台
./status_autoclip.sh            # 返回非零状态表示服务缺失或检查失败
./stop_autoclip.sh              # 停止当前 checkout 记录的服务及子进程
```

脚本从自身所在目录运行，可以从其他目录调用。后台模式也可使用 `./start_autoclip.sh --detach`。默认 API 为 `http://localhost:8000`、Web 为 `http://localhost:3000`；用 `BACKEND_PORT` / `FRONTEND_PORT` 环境变量调整。启动器不会杀掉占用端口的其他进程；确认所属服务后再处理端口冲突。

运行记录保存在 `backend.pid` / `frontend.pid` / `celery.pid` 和对应 `.pid.json`，日志位于 `logs/`。停止前验证进程命令、工作目录与创建时间；无法确认归属会报错，不会全局查找并终止 Vite/Celery。Redis 可能被其他项目共享，停止脚本不会关闭它。

数据库由共享初始化函数创建。必要时可运行 `python init_database.py`，它不会清空已有数据；不要用删除数据库的方式解决启动失败。

## 手动开发

激活虚拟环境并配置环境变量后，分别在终端运行：

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
celery -A backend.core.celery_app worker --loglevel=info --concurrency=1 -Q celery,processing,video,notification,upload
(cd frontend && npm run dev -- --port 3000)
```

手动启动的进程没有脚本 PID 记录，请在各自终端用 Ctrl+C 停止。状态脚本检查已记录进程及 API/Web/Redis 可用性；Worker 进程存活不保证某个任务已经完成，任务队列与转写进度应查看 `logs/celery.log` 和项目页面。

排错见 [FAQ](docs/FAQ.md)，入口与历史文件说明见 [仓库目录说明](docs/REPOSITORY_LAYOUT.md)。
