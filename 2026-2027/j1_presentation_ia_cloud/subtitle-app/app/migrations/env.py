"""Alembic environment.

Two ways in: the services pass an open connection (app.db.migrate), the alembic
command line connects to DATABASE_URL.
"""

from alembic import context
from sqlalchemy import create_engine

from app import models  # noqa: F401  (register tables)
from app.config import get_settings
from app.db import Base

target_metadata = Base.metadata


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = create_engine(get_settings().database_url)
    with engine.connect() as connection:
        _run(connection)
        connection.commit()
    engine.dispose()


run_migrations()
