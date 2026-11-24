#!/usr/bin/env bash
# Stop only PID-recorded services belonging to this checkout.
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/../runtime/local.sh" stop "$@"
