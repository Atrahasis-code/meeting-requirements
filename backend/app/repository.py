from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.inspection import inspect
from .models import AppSetting
from .context import organization


def get(session, model, identity):
    obj = session.get(model, identity)
    if obj is None:
        raise HTTPException(404, "Registro no encontrado")
    return obj


def rows(session, model, *conditions):
    return session.scalars(select(model).where(*conditions)).all()


def serialize(obj):
    from .runtime import runtime

    return runtime.public_record(
        obj, {column.key: getattr(obj, column.key) for column in inspect(obj).mapper.column_attrs}
    )


def setting(session, key, default=None):
    key = key if organization.get() == "local" else organization.get() + ":" + key
    obj = session.get(AppSetting, key)
    return obj.value if obj else default


def set_setting(session, key, value):
    key = key if organization.get() == "local" else organization.get() + ":" + key
    obj = session.get(AppSetting, key)
    if obj:
        obj.value = value
    else:
        session.add(AppSetting(key=key, value=value))
