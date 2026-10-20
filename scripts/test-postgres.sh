#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
compose() { docker compose -p meeting-ai-pg-test -f compose.yaml -f compose.test.yaml -f compose.postgres.test.yaml "$@"; }
trap 'compose down' EXIT INT TERM
compose build backend worker initialize
compose up -d --wait postgres
compose run --rm backend pytest tests/test_flow.py tests/test_postgres.py
compose up -d --wait backend worker
compose run --rm integration-tests
