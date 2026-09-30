#!/usr/bin/env bash
# Project-scoped Compose management; no global container/image/volume pruning.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
ACTION="${1:-}"
shift || true
FILE=docker-compose.yml
CLEANUP=false
BUILD=true
for arg in "$@"; do
    case "$arg" in
        dev|--dev) FILE=docker-compose.dev.yml ;;
        --cleanup) CLEANUP=true ;;
        --no-build) BUILD=false ;;
        --force) echo '--force removed: use an explicit docker compose down --volumes after backing up data.' >&2; exit 2 ;;
        -h|--help) echo "Usage: docker-{start,status,stop}.sh [dev] [--no-build (start)] [--cleanup (stop)]"; exit 0 ;;
        *) echo "Unknown argument: $arg" >&2; exit 2 ;;
    esac
done
if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
else
    echo 'Install Docker Compose v2.' >&2; exit 1
fi
compose() { "${COMPOSE[@]}" -f "$ROOT/$FILE" "$@"; }
case "$ACTION" in
    start)
        mkdir -p data logs uploads
        if [[ ! -f .env ]]; then cp env.example .env; fi
        if [[ "$BUILD" == true ]]; then compose up -d --build; else compose up -d; fi
        compose ps
        echo 'Containers started; inspect health with docker-status.sh (add dev for development).'
        ;;
    status)
        compose ps
        failed=0
        services="$(compose config --services)"
        for service in $services; do
            ids="$(compose ps -a -q "$service")"
            if [[ -z "$ids" ]]; then echo "$service: missing container"; failed=1; continue; fi
            for id in $ids; do
                state="$(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$id")"
                case "$state" in 'running '| 'running healthy') ;; *) echo "$service: $state"; failed=1 ;; esac
            done
        done
        exit "$failed"
        ;;
    stop)
        if [[ "$CLEANUP" == true ]]; then compose down; else compose stop; fi
        echo 'Stopped selected project; data, Redis volumes and other projects retained.'
        ;;
    *) echo "Unknown action: $ACTION" >&2; exit 2 ;;
esac
