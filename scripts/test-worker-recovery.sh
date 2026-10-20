#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
compose() { docker compose -p meeting-ai-recovery-test -f compose.yaml -f compose.test.yaml "$@"; }
trap 'compose down' EXIT INT TERM
compose up --build -d --wait backend worker
compose exec -T -e PYTHONPATH=/app backend python tests/worker_probe.py prepare
compose exec -T -e PYTHONPATH=/app backend python tests/worker_probe.py checkpoint
compose kill -s SIGKILL worker
compose up -d --wait worker
compose exec -T -e PYTHONPATH=/app backend python tests/worker_probe.py recovered
compose exec -T -e PYTHONPATH=/app backend python tests/worker_probe.py resume
compose exec -T -e PYTHONPATH=/app backend python tests/worker_probe.py checkpoint
compose stop worker
compose up -d --wait worker
compose exec -T -e PYTHONPATH=/app backend python tests/worker_probe.py recovered
compose exec -T -e PYTHONPATH=/app backend python tests/worker_probe.py resume
compose exec -T -e PYTHONPATH=/app backend python tests/worker_probe.py checkpoint
compose exec -T -e PYTHONPATH=/app backend python tests/worker_probe.py cancel
