# Docker 部署与排错

[English](docs/DOCKER.en.md) · [返回首页](README.md) · [常见问题](docs/FAQ.md)

适合 Linux、Intel Mac、服务器或希望使用 Web 界面的用户。需要 Docker 和 Docker Compose v2；命令使用 `docker compose`。视频、模型、缓存和导出文件会占用额外磁盘，按素材规模预留空间。

## 首次启动

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env
```

编辑 `.env`，设置 `LLM_PROVIDER`、`API_MODEL_NAME` 和对应的 API Key，也可以启动后在 Web 设置页配置。例：

```dotenv
LLM_PROVIDER=dashscope
API_MODEL_NAME=qwen-plus
API_DASHSCOPE_API_KEY=your_api_key
```

模型是否可用取决于服务商与账号权限。设置页已保存的模型配置可能优先于环境变量；更换提供商后应测试连接并保存。

```bash
mkdir -p data logs uploads
docker compose build
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
docker compose ps
```

目录归属命令让镜像中的 `autoclip` 用户能够写入三个项目绑定目录，尤其适用于 Linux。它会修改这些目录及其内容的文件归属；新部署可先在空目录中完成。无需将权限设为 `777`。

| 入口 | 默认地址 |
| --- | --- |
| Web 界面 | [http://localhost:3000](http://localhost:3000) |
| API 文档 | [http://localhost:8000/docs](http://localhost:8000/docs) |
| 健康检查 | [http://localhost:8000/api/v1/health/](http://localhost:8000/api/v1/health/) |
| Flower 任务监控 | [http://localhost:5555](http://localhost:5555) |

默认编排同时启动主应用、Redis、Celery Worker、Celery Beat 和 Flower。它面向本地或可信网络使用；若部署到公网，需要另行设置访问控制与网络隔离，尤其不要直接开放 Redis 和 Flower。

## 模型与字幕

支持的提供商与环境变量以 [env.example](env.example) 和 [docker-compose.yml](docker-compose.yml) 为准。Web 设置页可以保存模型配置，不需要仅靠环境变量。

本地模型需要在宿主机启动。Docker Desktop 访问宿主机 Ollama 的示例：

```dotenv
LLM_PROVIDER=ollama
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
API_MODEL_NAME=qwen2.5:7b
```

Linux Docker Engine 可能需要在 `autoclip` 和 `celery-worker` 两个服务下加入：

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

该主机名能解析并不保证模型可连接：宿主机模型服务还需要监听容器可访问的接口，防火墙允许相应连接。容器中的 `localhost` 不能访问宿主机的模型服务。环境变量或编排变更后运行 `docker compose up -d` 重建受影响容器；若设置页保存过旧地址，也要同步修改。

没有字幕的视频需要准备本地转写组件与模型。首次安装较耗时，建议先使用本地视频加 SRT 验证主流程，详见 [安装指南](docs/USER_INSTALLATION_GUIDE.md)。

## 排错

```bash
docker compose ps
docker compose logs --tail=100 autoclip celery-worker
curl -f http://localhost:8000/api/v1/health/
```

| 现象 | 检查项 |
| --- | --- |
| 页面打不开 | `autoclip` 是否运行，3000 / 8000 端口是否被其他进程占用 |
| 项目一直排队 | `celery-worker` 与 Redis 是否健康，是否保留了编排中的专用队列参数 |
| Permission denied / 数据库只读 | `data/`、`logs/`、`uploads/` 是否对容器用户可写 |
| 模型测试失败 | 提供商、模型名、API Key 和保存的 Base URL；本地模型是否能从容器访问 |
| 没有生成片段 | 按字幕、分析、评分、导出阶段排查，见 [FAQ](docs/FAQ.md) |

修改宿主机端口时，只修改映射左侧，例如 `"3001:3000"`，再使用新的宿主机端口访问。不要删除数据库来解决启动问题。

## 数据与备份

默认 Compose 使用绑定目录，而不是名为 `autoclip_data` 的视频数据卷：

| 宿主机 | 容器 | 内容 |
| --- | --- | --- |
| `./data` | `/app/data` | 数据库、项目、配置等 |
| `./logs` | `/app/logs` | 日志 |
| `./uploads` | `/app/uploads` | 上传文件 |

`redis_data` 是 Redis 的命名卷，不能代替项目文件备份。备份前等待任务结束并停止服务，再复制三个目录和 `.env`：

```bash
docker compose stop
tar -czf "../autoclip-backup-$(date +%Y%m%d-%H%M%S).tar.gz" data logs uploads .env
docker compose start
```

备份含本地视频和可能含密钥的配置，请保存在受控位置。恢复前停止服务、保留当前目录副本，然后恢复数据并核对文件归属；不要直接覆盖唯一一份数据。

## 更新与停止

备份后更新源码并重建。存在本地改动时先检查 `git status` 并处理改动，不要强制覆盖。

```bash
git pull --ff-only
docker compose up -d --build
```

暂时停止使用 `docker compose stop`；删除容器但保留绑定数据使用 `docker compose down`。不要为了日常重启加 `--volumes`。

## 开发模式

[开发编排](docker-compose.dev.yml) 用于源码开发；它与生产编排可能使用相同端口，不要同时启动：

```bash
docker compose -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.dev.yml logs -f
```

更多排错见 [FAQ](docs/FAQ.md)，版本变更见 [Releases](https://github.com/zhouxiaoka/autoclip/releases)。
