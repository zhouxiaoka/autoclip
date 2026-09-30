#!/usr/bin/env bash
# Compatibility entrypoint; shared implementation lives in scripts/runtime/.
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/scripts/runtime/docker.sh" status "$@"
