#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_PATH="${APP_PATH:-${ROOT_DIR}/src-tauri/target/release/bundle/macos/AutoClip Desktop.app}"
APP_BIN="${APP_PATH}/Contents/MacOS/autoclip-desktop"
LOG_FILE="${LOG_FILE:-/private/tmp/autoclip-desktop-app-smoke.log}"
BUILD_APP="${BUILD_APP:-1}"
VERIFY_DATA_DIR="${AUTOCLIP_DATA_DIR:-/private/tmp/autoclip-desktop-app-smoke-data}"

if [[ "${BUILD_APP}" == "1" ]]; then
  (cd "${ROOT_DIR}/src-tauri" && cargo tauri build --bundles app)
fi

if [[ ! -x "${APP_BIN}" ]]; then
  echo "missing app executable: ${APP_BIN}" >&2
  exit 1
fi

rm -f "${LOG_FILE}"
AUTOCLIP_APP_DIR="${VERIFY_DATA_DIR}" AUTOCLIP_DATA_DIR="${VERIFY_DATA_DIR}" "${APP_BIN}" >"${LOG_FILE}" 2>&1 &
APP_PID=$!

cleanup() {
  if kill -0 "${APP_PID}" >/dev/null 2>&1; then
    kill "${APP_PID}" >/dev/null 2>&1 || true
    wait "${APP_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

port=""
deadline=$((SECONDS + 45))
while [[ -z "${port}" && ${SECONDS} -lt ${deadline} ]]; do
  if ! kill -0 "${APP_PID}" >/dev/null 2>&1; then
    echo "desktop app exited before reporting backend port" >&2
    tail -n 80 "${LOG_FILE}" >&2 || true
    exit 1
  fi

  port="$(sed -n 's/^Backend started on port: //p' "${LOG_FILE}" | tail -n 1)"
  if [[ -z "${port}" ]]; then
    port="$(sed -n 's/^PORT=//p' "${LOG_FILE}" | tail -n 1)"
  fi
  sleep 0.5
done

if [[ -z "${port}" ]]; then
  echo "desktop app did not report backend port" >&2
  tail -n 120 "${LOG_FILE}" >&2 || true
  exit 1
fi

python3 - "${port}" <<'PY'
import json
import sys
from urllib.request import urlopen

port = sys.argv[1]

with urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as response:
    health = response.read().decode("utf-8")

with urlopen(f"http://127.0.0.1:{port}/api/v1/video-categories", timeout=5) as response:
    categories = json.loads(response.read().decode("utf-8"))

if "categories" not in categories or "default_category" not in categories:
    raise SystemExit(f"invalid video categories response: {categories}")

print(f"HEALTH={health}")
print(f"VIDEO_CATEGORIES={len(categories['categories'])}")
PY

if grep -E "BACKEND_ERROR=|Traceback|Application startup failed|加载视频分类失败|Failed to load video categories" "${LOG_FILE}" >/dev/null; then
  echo "desktop app log contains startup/category errors" >&2
  grep -E "BACKEND_ERROR=|Traceback|Application startup failed|加载视频分类失败|Failed to load video categories" "${LOG_FILE}" >&2 || true
  exit 1
fi

echo "APP=${APP_PATH}"
echo "PORT=${port}"
echo "LOG=${LOG_FILE}"
