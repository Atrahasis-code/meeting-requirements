from alembic import context
from app.db import Base, engine
from app import models  # noqa: F401


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


provided = context.config.attributes.get("connection")
if provided is not None:
    run(provided)
else:
    with engine.connect() as connection:
        run(connection)
