"""SQLAlchemy engine, session, and Flask-SQLAlchemy compatibility shim for models.

La intranet usa **PostgreSQL** (driver psycopg v3). La URI se resuelve en
``config.Config.SQLALCHEMY_DATABASE_URI`` a partir de variables de entorno.
"""
from __future__ import annotations

import os
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.orm import DeclarativeBase, backref, relationship, scoped_session, sessionmaker

from config import Config

_engine = None
_db_session = None
_SessionFactory = None


def _default_uri() -> str:
    return os.environ.get("SQLALCHEMY_DATABASE_URI") or Config.SQLALCHEMY_DATABASE_URI


def _engine_options() -> dict:
    return dict(getattr(Config, "SQLALCHEMY_ENGINE_OPTIONS", None) or {})


def configure_engine(uri: str | None = None, engine_options: dict | None = None) -> None:
    """(Re)crea el engine y la scoped session — usado por tests y el app factory."""
    global _engine, _db_session, _SessionFactory
    uri = uri or _default_uri()
    opts = dict(engine_options if engine_options is not None else _engine_options())
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(uri, **opts)
    _SessionFactory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    if _db_session is not None:
        _db_session.remove()
    _db_session = scoped_session(_SessionFactory)


configure_engine()


class _QueryProperty:
    """Flask-SQLAlchemy–style ``Model.query`` (descriptor, not a bound classmethod)."""

    def __get__(self, obj, owner):
        cls = owner if obj is None else type(obj)
        return _db_session.query(cls)


class Base(DeclarativeBase):
    query = _QueryProperty()


class Database:
    """Flask-SQLAlchemy compatibility: db.Model, db.Column, db.session, etc."""

    Model = Base
    func = func
    Column = Column
    Integer = Integer
    String = String
    Text = Text
    DateTime = DateTime
    Date = Date
    Time = Time
    Boolean = Boolean
    Float = Float
    Numeric = Numeric
    ForeignKey = ForeignKey
    Index = Index
    UniqueConstraint = UniqueConstraint
    relationship = staticmethod(relationship)
    backref = staticmethod(backref)

    @property
    def session(self):
        return _db_session

    @property
    def engine(self):
        return _engine

    def create_all(self):
        Base.metadata.create_all(bind=_engine)

    def drop_all(self):
        Base.metadata.drop_all(bind=_engine)


db = Database()
