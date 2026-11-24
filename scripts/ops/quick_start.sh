#!/usr/bin/env bash
# Detached startup uses exactly the same checks and PID ownership as full startup.
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/start_autoclip.sh" --detach "$@"
