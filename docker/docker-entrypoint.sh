#!/usr/bin/env bash
# Production image entrypoint; database creation shares the supported backend path.
set -euo pipefail
cd /app
export PYTHONPATH=/app PYTHONUNBUFFERED=1
mkdir -p data/projects data/uploads data/temp data/output logs
python init_database.py
python - <<'PY'
import os
import sys
import redis
try:
    redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0'),
                        socket_connect_timeout=5, socket_timeout=5).ping()
except Exception as error:
    print(f'Redis unavailable ({type(error).__name__}); Celery requires a working broker.', file=sys.stderr)
    sys.exit(1)
print('Redis connected')
PY
exec "$@"
