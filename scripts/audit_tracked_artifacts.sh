#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

git ls-files | rg '(^frontend/dist/|^src-tauri/target/|^build/|^dist/|^backend/data/|^data/|\.log$|\.pid$|\.DS_Store$|^\.env$|^frontend/node_modules/)'
