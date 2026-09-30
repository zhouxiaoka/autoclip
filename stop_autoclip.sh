#!/usr/bin/env bash
# Stop only PID-recorded services belonging to this checkout.
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/scripts/runtime/local.sh" stop "$@"
