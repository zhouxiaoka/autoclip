# Docker deployment and troubleshooting

[简体中文](../DOCKER.md) · [README](../README-EN.md) · [FAQ](FAQ.en.md)

Use Docker for Linux, Intel Mac, servers, or a web interface. Install Docker and Docker Compose v2; the commands use `docker compose`. Allow additional disk space for footage, models, caches, and exports.

## First startup

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env
```

Edit `.env` to set `LLM_PROVIDER`, `API_MODEL_NAME`, and the provider’s API key. Alternatively, configure them in the web Settings after startup. Example:

```dotenv
LLM_PROVIDER=dashscope
API_MODEL_NAME=qwen-plus
API_DASHSCOPE_API_KEY=your_api_key
```

Model availability depends on your provider and account. Model settings saved in the app may take precedence over environment variables. Test the connection and save after switching providers.

```bash
mkdir -p data logs uploads
docker compose build
docker compose run --rm --no-deps --user root --entrypoint sh autoclip -c 'chown -R autoclip:autoclip /app/data /app/logs /app/uploads'
docker compose up -d
docker compose ps
```

The ownership command makes the three project bind mounts writable by the image’s `autoclip` user, particularly on Linux. It changes ownership of these directories and their contents; use empty directories for a new deployment. World-writable `777` permissions are unnecessary.

| Entry point | Default address |
| --- | --- |
| Web interface | [http://localhost:3000](http://localhost:3000) |
| API documentation | [http://localhost:8000/docs](http://localhost:8000/docs) |
| Health check | [http://localhost:8000/api/v1/health/](http://localhost:8000/api/v1/health/) |
| Flower task monitor | [http://localhost:5555](http://localhost:5555) |

The default stack starts the app, Redis, Celery Worker, Celery Beat, and Flower. It is intended for local or trusted-network use. Public hosting needs access controls and network isolation; do not expose Redis or Flower directly to the internet.

## Models and subtitles

See [env.example](../env.example) and [docker-compose.yml](../docker-compose.yml) for supported provider variables. Model configuration can be saved through web Settings; environment variables are not the only option.

Start local model services on the host. Example for host Ollama with Docker Desktop:

```dotenv
LLM_PROVIDER=ollama
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
API_MODEL_NAME=qwen2.5:7b
```

Linux Docker Engine may require this under both the `autoclip` and `celery-worker` services:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Resolving the hostname is not enough: the model service must listen on an interface reachable from the container, and the firewall must allow the connection. Container `localhost` does not refer to your host. After environment or Compose changes, run `docker compose up -d` to recreate affected containers. Update any old address saved in Settings as well.

Videos without subtitles need speech components and model files. Initial setup may take time; start with a local video plus SRT to verify the pipeline. See the [installation guide](USER_INSTALLATION_GUIDE.en.md).

## Troubleshooting

```bash
docker compose ps
docker compose logs --tail=100 autoclip celery-worker
curl -f http://localhost:8000/api/v1/health/
```

| Symptom | What to check |
| --- | --- |
| Web page unavailable | App container status and port conflicts on 3000 / 8000 |
| Jobs remain queued | Worker and Redis health; keep the dedicated queue arguments in the supplied Compose file |
| Permission denied / read-only database | Container write access to `data/`, `logs/`, and `uploads/` |
| Model test fails | Provider, model, key, saved Base URL, and container access to local model services |
| No clips generated | Subtitle, analysis, scoring, and export checks in the [FAQ](FAQ.en.md) |

To change a host port, change only the left side of the mapping, for example `"3001:3000"`, then visit the new host port. Do not delete the database to fix startup problems.

## Data and backups

The supplied Compose file uses bind mounts, not a video data volume named `autoclip_data`:

| Host | Container | Contents |
| --- | --- | --- |
| `./data` | `/app/data` | Database, projects, settings, and related data |
| `./logs` | `/app/logs` | Logs |
| `./uploads` | `/app/uploads` | Uploaded files |

`redis_data` stores Redis data; it is not a project backup. Wait for active jobs to finish, stop services, and back up the three directories plus `.env`:

```bash
docker compose stop
tar -czf "../autoclip-backup-$(date +%Y%m%d-%H%M%S).tar.gz" data logs uploads .env
docker compose start
```

Backups contain videos and settings that may include keys. Store them securely. Before restoring, stop services and preserve a copy of the current directories, then restore and check ownership. Never overwrite your only copy.

## Updating and stopping

Back up, update the source, and rebuild. Check `git status` and resolve local changes first; do not force-overwrite them.

```bash
git pull --ff-only
docker compose up -d --build
```

Use `docker compose stop` to pause services or `docker compose down` to remove containers while retaining bind-mounted data. Routine restarts do not need `--volumes`.

## Development mode

The [development stack](../docker-compose.dev.yml) is for source development and may use the same ports as production. Do not run both at once:

```bash
docker compose -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.dev.yml logs -f
```

See the [FAQ](FAQ.en.md) for more troubleshooting and [Releases](https://github.com/zhouxiaoka/autoclip/releases) for version changes.
