#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-${ROOT_DIR}/venv/bin/python}"
VERIFY_DATA_DIR="${AUTOCLIP_DATA_DIR:-/private/tmp/autoclip-desktop-verify-data}"
export VERIFY_DATA_DIR

if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi
export PYTHON_BIN

cd "${ROOT_DIR}/src-tauri"
cargo check

cd "${ROOT_DIR}"
"${PYTHON_BIN}" - <<'PY'
import os
import json
import select
import subprocess
import time
from urllib.request import urlopen

python = os.environ.get("PYTHON_BIN") or "python3"
env = os.environ.copy()
env["AUTOCLIP_DESKTOP_MODE"] = "true"
env["AUTOCLIP_MODE"] = "desktop"
env.setdefault("AUTOCLIP_APP_DIR", os.environ["VERIFY_DATA_DIR"])
env.setdefault("AUTOCLIP_DATA_DIR", os.environ["VERIFY_DATA_DIR"])

proc = subprocess.Popen(
    [python, "-m", "backend.desktop_main"],
    cwd=".",
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    env=env,
)

port = None
try:
    deadline = time.time() + 25
    while time.time() < deadline:
        ready, _, _ = select.select([proc.stdout], [], [], 0.5)
        if ready:
            line = proc.stdout.readline()
            if line:
                print(line, end="")
                if line.startswith("PORT="):
                    port = int(line.split("=", 1)[1])
                    break
                if line.startswith("BACKEND_ERROR="):
                    raise RuntimeError(line.strip())
        if proc.poll() is not None:
            break

    if port is None:
        raise RuntimeError("desktop backend did not report a port")

    with urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as response:
        print("HEALTH=" + response.read().decode("utf-8"))

    with urlopen(f"http://127.0.0.1:{port}/api/v1/video-categories", timeout=5) as response:
        categories = json.loads(response.read().decode("utf-8"))
        if "categories" not in categories or "default_category" not in categories:
            raise RuntimeError(f"invalid video categories response: {categories}")
        print(f"VIDEO_CATEGORIES={len(categories['categories'])}")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
PY
