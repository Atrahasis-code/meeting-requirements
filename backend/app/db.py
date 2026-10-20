import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, with_loader_criteria
from .config import settings
from .context import organization


class Base(DeclarativeBase):
    pass


def utcnow():
    return datetime.now(timezone.utc)


class Record:
    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        default=lambda: organization.get(), server_default="local", index=True
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


def make_engine(url):
    from sqlalchemy.engine import make_url

    args = {"timeout": 5, "check_same_thread": False} if make_url(url).get_backend_name() == "sqlite" else {}
    instance = create_engine(url, connect_args=args, hide_parameters=True, pool_pre_ping=True)
    if instance.dialect.name == "sqlite":

        @event.listens_for(instance, "connect")
        def sqlite_options(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("PRAGMA synchronous=FULL")

    return instance


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


@event.listens_for(SessionLocal, "do_orm_execute")
def tenant_scope(execution):
    tenant = organization.get()
    execution.statement = execution.statement.options(
        with_loader_criteria(Record, lambda cls: cls.organization_id == tenant, include_aliases=True)
    )


@event.listens_for(SessionLocal, "after_begin")
def transaction_scope(session, transaction, connection):
    if connection.dialect.name == "postgresql":
        from sqlalchemy import text

        connection.execute(
            text("SELECT set_config('mra.organization_id', :tenant, true)"), {"tenant": organization.get()}
        )


@event.listens_for(SessionLocal, "before_flush")
def check_tenant_writes(session, *_):
    for instance in session.new | session.dirty | session.deleted:
        if (
            isinstance(instance, Record)
            and instance.organization_id is not None
            and instance.organization_id != organization.get()
        ):
            raise ValueError("Operación fuera de la organización activa")


def session_dependency():
    with SessionLocal() as session:
        yield session


@event.listens_for(SessionLocal, "after_begin")
def actor_scope(session, transaction, connection):
    if connection.dialect.name == "postgresql":
        from sqlalchemy import text
        from .context import current_actor

        value = current_actor()
        connection.execute(
            text("SELECT set_config('mra.user_id',:user,true),set_config('mra.role',:role,true)"),
            {"user": value["id"], "role": value.get("role", "owner")},
        )
