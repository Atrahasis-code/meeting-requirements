"""Trusted execution context, never derived from model output."""

from contextvars import ContextVar

organization = ContextVar("organization", default="local")
actor = ContextVar("actor", default=None)


def current_actor():
    return actor.get() or {"id": "local-owner", "label": "Usuario local", "kind": "local"}
