# Optional local PostgreSQL

SQLite remains the default. PostgreSQL does not add a subscription or turn the installation into a hosted service.

Create a private file with a random password and set `POSTGRES_PASSWORD_FILE` to its absolute path. Do not commit it to the repository. Then run:

```sh
docker compose -f compose.yaml -f compose.postgres.yaml up --build -d
```

The PostgreSQL service publishes no ports. The root initializer reads only the explicit password file, which can retain 0600 permissions on the host. It copies the password into two separate private volumes: one for PostgreSQL (UID 999) and one for the application (UID 10001), using 0700 directories and 0600 files. Services mount them read-only and receive no other host secrets. Changing the file does not automatically change an existing database's password: a mismatch stops initialization and requires explicit rotation. The official image is pinned by digest; the queue uses short transactions, and an advisory lock prevents duplicate local workers. Keep a separate database per installation and avoid sharing it between active installations.

Tests without personal credentials:

```sh
sh scripts/test-postgres.sh
```

## Migrate from SQLite

1. Stop the backend and worker and create the consistent backup described in OPERATIONS.md. Retain the source and verify the manifest/checksums.
2. Initialize an empty PostgreSQL destination through Compose. Do not reuse a database containing data. Stop its application services before importing.
3. Copy the backup into the maintenance container and use `restore`: it verifies the archive, imports the SQLite snapshot into PostgreSQL, and restores volume files. The destination schema must already be migrated.
4. The importer preserves identifiers, originals, revisions, and relationships, checks counts and logical hashes, and rejects nonempty destinations. The transaction rolls back on error.
5. Reconnect ChatGPT if this is another installation. Backups exclude credentials and do not transfer OAuth.

To import only a database copy, the container command is `python -m app.migrate_database --source /tmp/snapshot.sqlite3`; media, transcripts, and exports must be transferred using the full backup. Never use the active SQLite database as a migration source.

Local PostgreSQL backup generates a portable SQLite snapshot with the current schema, alongside the files, to reuse integrity checks and the restoration format. It neither uses nor requires PostgreSQL tools on the host.
