# Backup, restoration, and migration

Maintenance tools run inside containers; Python and tar utilities are not required on the host. The examples use helper-container names reserved for this operation. Do not use names that already belong to another task.

## Consistent backup

Stop writes and create a portable archive. Do not copy only the SQLite file while services are writing.

```sh
mkdir -p backups
docker compose stop backend worker
docker compose run --name mra-backup --no-deps maintenance backup /tmp/meeting-backup.tar.gz
docker cp mra-backup:/tmp/meeting-backup.tar.gz ./backups/meeting-backup.tar.gz
docker rm mra-backup
docker compose start backend worker
```

To include models, append `--include-models` to the backup command. Internal cache links are stored as regular files to allow offline restoration; this may increase archive size. Links pointing outside the model volume are excluded. The archive contains a SQLite copy made through its backup API, media, transcripts, and exports, plus a manifest and SHA-256 checksums. Authentication and tokens are excluded. Protect the backup because it contains meetings and business data. Store it in `backups/`, which is excluded from Git and the Docker context. Files matching `*.tar.gz` and `*.tgz` are also excluded if copied elsewhere; these rules do not protect already tracked files or replace backup access controls or encryption.

Do not restart services until the copy finishes; files and database must belong to the same maintenance window. The lock prevents backup while the worker is active; the operator must also stop the API.

## Restore into new volumes

Select a new Compose project; do not overwrite an installation containing data. Also copy the application code/version and any required non-sensitive configuration files.

```sh
docker compose -p meeting-restored build backend worker frontend initialize maintenance
docker compose -p meeting-restored run --rm --no-deps initialize python -m app.initialize --prepare-only
docker compose -p meeting-restored run -d --name mra-restore --no-deps --entrypoint sleep maintenance infinity
docker cp ./backups/meeting-backup.tar.gz mra-restore:/tmp/meeting-backup.tar.gz
docker exec mra-restore python -m app.maintenance restore /tmp/meeting-backup.tar.gz
docker rm -f mra-restore
docker compose -p meeting-restored up -d
```

Stop the original installation first if both publish the same APP_PORT. Restoration rejects volumes containing data, unsafe archive paths, links, entries outside allowed directories, incorrect checksums, and SQLite databases without referential integrity. Subsequent startup runs Alembic and checks health.

## Move between machines

1. Create a consistent backup and take the code, lockfiles, and backup to the new machine.
2. Install Docker/Compose on the new machine. Build natively for its architecture.
3. Restore into new volumes using the procedure above.
4. Configure adequate resources and verify projects, meetings, transcripts, requirements, and exports.
5. Connect ChatGPT again. The new installation creates a different host ID and does not receive the previous machine's tokens.

Sessions remain in the original installation until disconnected. Do not transfer authentication volumes as part of a data backup. Keep the original backup until validation finishes. `docker compose down` preserves data; `down -v` deletes it.

## Diagnostics

`docker compose ps` shows health, `docker compose logs backend worker` shows operational stages/errors, and `docker stats` shows CPU/RAM usage. An unhealthy container does not restart automatically just because of its healthcheck; restart policy acts when the process exits. If a job was interrupted, retry from the UI; do not edit SQLite manually.

## Reproducible checks

```sh
sh scripts/test.sh
sh scripts/test-operations.sh
sh scripts/test-worker-recovery.sh
sh scripts/check-platform.sh linux/amd64
sh scripts/check-platform.sh linux/arm64
```

The operations test uses exclusive projects with process-ID suffixes, checks that a second worker is excluded, creates synthetic data, streams the backup between containers, restores it, and recreates services. It stops its containers when finished and retains volumes for inspection. It does not access normal application data.

The platform check loads local images and runs native imports and FFmpeg. On an amd64 machine, running arm64 through QEMU is emulation. This check does not replace real inference or native macOS testing.

The recovery test runs only Mock in an isolated project, waits for checkpoints, sends SIGKILL to the worker, and verifies that the job is interrupted without losing committed blocks or automatically resuming inference.
