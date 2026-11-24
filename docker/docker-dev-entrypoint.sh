#!/usr/bin/env bash
# Run the two development servers; worker runs in its own Compose service.
set -euo pipefail
cd /app
export PATH="/app/venv/bin:$PATH"
python init_database.py
# Compose isolates Linux dependencies from a host's macOS/Windows node_modules.
# npm ci checks the lock file and never rewrites package manifests.
(cd frontend && npm ci)
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir backend &
API_PID=$!
(cd frontend && exec npm run dev -- --host 0.0.0.0 --port 3000 --strictPort) &
WEB_PID=$!
cleanup() {
    kill "$API_PID" "$WEB_PID" 2>/dev/null || true
    wait "$API_PID" "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# If either server exits, stop its sibling and let Compose restart the service.
set +e
wait -n "$API_PID" "$WEB_PID"
RESULT=$?
set -e
if [[ "$RESULT" == 0 ]]; then RESULT=1; fi
exit "$RESULT"
