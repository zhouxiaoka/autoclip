#!/usr/bin/env bash
# Compatibility entrypoint for the maintained source Web launcher.
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/scripts/runtime/start.sh" "$@"
