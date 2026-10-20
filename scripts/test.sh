#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
# These resources never share a name with the normal application's volumes.
project=${MRA_TEST_PROJECT:-meeting-ai-test}
case "$project" in
  meeting-ai-test|meeting-ai-test-*) ;;
  *) echo "Use meeting-ai-test or a meeting-ai-test-* project to protect normal installations." >&2; exit 2 ;;
esac
compose() { docker compose -p "$project" -f compose.yaml -f compose.test.yaml "$@"; }
trap 'compose down' EXIT INT TERM
compose build backend worker frontend-tests integration-tests initialize frontend
compose run --rm backend pytest
compose run --rm backend ruff check app tests
compose run --rm frontend-tests
compose up -d --wait backend worker frontend
compose run --rm integration-tests
