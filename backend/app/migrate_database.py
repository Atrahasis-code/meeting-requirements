"""Import a verified SQLite backup into an empty, migrated PostgreSQL database."""

import argparse
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
import sqlalchemy as sa
from .db import engine
from . import models  # noqa: F401
from .db import Base, make_engine


def convert(column, value):
    if value is None:
        return None
    if isinstance(column.type, sa.JSON):
        return json.loads(value) if isinstance(value, str) else value
    if isinstance(column.type, sa.DateTime):
        return datetime.fromisoformat(value) if isinstance(value, str) else value
    if isinstance(column.type, sa.Date):
        return date.fromisoformat(value) if isinstance(value, str) else value
    if isinstance(column.type, sa.Boolean):
        return bool(value)
    return value


def checksum(rows):
    return hashlib.sha256(
        json.dumps(
            sorted(rows, key=lambda x: str(x.get("id", x.get("key", "")))),
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        ).encode()
    ).hexdigest()


def migrate(source_path):
    if engine.dialect.name != "postgresql":
        raise ValueError("El destino debe ser PostgreSQL")
    path = Path(source_path).resolve()
    if not path.is_file():
        raise ValueError("Indica una copia SQLite existente, no la base en uso")
    source = make_engine("sqlite:///file:" + str(path) + "?mode=ro&uri=true")
    counts = {}
    try:
        with source.connect() as incoming, engine.begin() as target:
            if (
                incoming.exec_driver_sql("PRAGMA integrity_check").scalar() != "ok"
                or incoming.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            ):
                raise ValueError("Backup SQLite inválido")
            tables = [
                t for t in Base.metadata.sorted_tables if t.name in sa.inspect(incoming).get_table_names()
            ]
            if any(target.scalar(sa.select(sa.func.count()).select_from(t)) for t in tables):
                raise ValueError("El destino debe estar vacío")
            for table in tables:
                names = [c["name"] for c in sa.inspect(incoming).get_columns(table.name)]
                data = [
                    {name: convert(table.c[name], row[name]) for name in names}
                    for row in incoming.exec_driver_sql('SELECT * FROM "' + table.name + '"').mappings()
                ]
                if data:
                    target.execute(table.insert(), data)
                copied = [
                    {name: row[name] for name in names} for row in target.execute(table.select()).mappings()
                ]
                if checksum(data) != checksum(copied):
                    raise ValueError("Verificación fallida en " + table.name)
                counts[table.name] = {"rows": len(data), "sha256": checksum(copied)}
    finally:
        source.dispose()
    return {"source_unchanged": True, "credentials_imported": False, "tables": counts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    print(json.dumps(migrate(args.source), sort_keys=True))


if __name__ == "__main__":
    main()
