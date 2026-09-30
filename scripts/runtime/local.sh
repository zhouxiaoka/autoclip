#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
if [[ -x venv/bin/python ]]; then
    PYTHON="$ROOT/venv/bin/python"
else
    PYTHON="${AUTOCLIP_PYTHON:-python3}"
fi
# dotenv is parsed as data; never execute configuration as shell code.
exec "$PYTHON" -c 'import sys; from dotenv import load_dotenv; load_dotenv(".env", override=False); from scripts.local_services import main; sys.exit(main())' "$@"
