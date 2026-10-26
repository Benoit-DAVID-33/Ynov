from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
# Services start together and each one upgrades the schema: the first takes this
# lock, the others wait and then find nothing left to do.
_MIGRATION_LOCK = 4_172_001


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory: sessionmaker[Session] | None = None


def alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


def migrate(engine) -> None:
    """Bring the schema to the latest revision (see app/migrations)."""
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _MIGRATION_LOCK})
        config = alembic_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def init_db(url: str) -> None:
    global _engine, _session_factory
    if not url.startswith("postgresql"):
        raise ValueError("DATABASE_URL doit être une URL PostgreSQL (postgresql+psycopg://...)")
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(url, pool_pre_ping=True)
    _session_factory = sessionmaker(_engine, expire_on_commit=False)

    from app import models  # noqa: F401  (register tables)

    migrate(_engine)


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
