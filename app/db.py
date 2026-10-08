from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory: sessionmaker[Session] | None = None


def init_db(url: str) -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    if url.startswith("sqlite"):
        # WAL: the API keeps reading while the workers write.
        @event.listens_for(_engine, "connect")
        def _use_wal(connection, _record):
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=15000")
    _session_factory = sessionmaker(_engine, expire_on_commit=False)

    from app import models  # noqa: F401  (register tables)

    Base.metadata.create_all(_engine)
    _add_missing_columns(_engine)


def _add_missing_columns(engine) -> None:
    """Upgrade a database created by an earlier version, keeping its data.

    Only handles what the application needs so far: new columns that are
    nullable or have a constant default. Anything beyond that calls for a
    real migration tool (Alembic).
    """
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            existing = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl = f"ALTER TABLE {table.name} ADD COLUMN {column.name} " \
                      f"{column.type.compile(engine.dialect)}"
                if not column.nullable:
                    ddl += f" DEFAULT {column.default.arg!r} NOT NULL"
                connection.execute(text(ddl))


@contextmanager
def session_scope() -> Iterator[Session]:
    if _session_factory is None:
        raise RuntimeError("init_db() must be called first")
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as session:
        yield session
