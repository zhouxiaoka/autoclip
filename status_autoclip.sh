#!/usr/bin/env bash
# Compatibility entrypoint; maintained implementation lives in scripts/.
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/scripts/runtime/local.sh" status "$@"
