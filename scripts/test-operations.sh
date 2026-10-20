#!/bin/sh
# Docker-only operations checks; retain test volumes for inspection.
set -eu
cd "$(dirname "$0")/.."
suffix=$$
source_project="meeting-ai-ops-$suffix"
target_project="meeting-ai-restored-$suffix"
backup_container="mra-backup-$suffix"
restore_container="mra-restore-$suffix"
source_compose() { docker compose -p "$source_project" -f compose.yaml -f compose.test.yaml "$@"; }
target_compose() { docker compose -p "$target_project" -f compose.yaml -f compose.test.yaml "$@"; }
cleanup() {
  docker rm -f "$backup_container" "$restore_container" >/dev/null 2>&1 || true
  source_compose down
  target_compose down
}
trap cleanup EXIT INT TERM
source_compose build backend worker initialize maintenance
source_compose up -d --wait backend worker
# A second worker must fail while the first owns the shared lock.
if source_compose run --rm --no-deps worker python -m app.worker; then
  echo 'ERROR: duplicate worker was allowed' >&2
  exit 1
fi
source_compose stop backend worker
source_compose run --rm --no-deps backend python -m app.seed
source_compose run --name "$backup_container" --no-deps maintenance backup /tmp/meeting-backup.tar.gz
target_compose run --build --rm --no-deps initialize python -m app.initialize --prepare-only
target_compose run --build -d --name "$restore_container" --no-deps --entrypoint sleep maintenance infinity
# Docker cp streams a tar archive directly; no host tar/Python or fixed host paths.
docker cp "$backup_container:/tmp/meeting-backup.tar.gz" - | docker cp - "$restore_container:/tmp/"
docker exec "$restore_container" python -m app.maintenance restore /tmp/meeting-backup.tar.gz
docker exec "$restore_container" python -c "import pathlib,sqlite3; c=sqlite3.connect('/data/db/app.sqlite3'); assert c.execute('select count(*) from requirements').fetchone()[0]>=1; assert not list(pathlib.Path('/data/auth').iterdir())"
docker rm -f "$restore_container" "$backup_container"
target_compose up --build -d --wait backend worker
target_compose up --force-recreate -d --wait backend worker
target_compose exec -T backend python -c "import sqlite3; c=sqlite3.connect('/data/db/app.sqlite3'); assert c.execute('select count(*) from requirements').fetchone()[0]>=1; print('Backup, restoration and persistence: PASS')"
echo "Test volumes retained under projects $source_project and $target_project."
