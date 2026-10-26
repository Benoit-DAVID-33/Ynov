import threading

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app import db
from app.db import Base, init_db, session_scope
from app.models import Upload, User


def _engine(settings):
    return create_engine(settings.database_url)


def test_migrations_build_exactly_the_schema_of_the_models(settings):
    """A model changed without its migration shows up here as a difference."""
    init_db(settings.database_url)
    with _engine(settings).connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert differences == []


def test_migrating_twice_changes_nothing(settings):
    init_db(settings.database_url)
    with session_scope() as session:
        session.add(User(username="kept", password_hash="x"))
    init_db(settings.database_url)
    with session_scope() as session:
        assert session.query(User).filter_by(username="kept").count() == 1


def test_services_starting_together_migrate_once(settings):
    errors = []

    def start():
        try:
            db.migrate(create_engine(settings.database_url))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=start) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    with _engine(settings).connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM alembic_version")).scalar() == 1


def test_tables_of_the_versions_before_accounts_are_replaced(settings):
    legacy = _engine(settings)
    with legacy.begin() as connection:
        connection.execute(text("CREATE TABLE uploads (id VARCHAR(32) PRIMARY KEY, owner_id VARCHAR(32))"))
        connection.execute(text("INSERT INTO uploads VALUES ('u1', 'cookie')"))
    init_db(settings.database_url)
    columns = {c["name"] for c in inspect(legacy).get_columns("uploads")}
    assert "filename" in columns
    with legacy.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM uploads")).scalar() == 0


def test_only_postgresql_is_supported():
    with pytest.raises(ValueError, match="PostgreSQL"):
        init_db("sqlite:///x.db")


def test_a_file_over_2_gib_fits_in_the_schema(client):
    with session_scope() as session:
        owner = session.query(User).one()
        session.add(Upload(
            filename="big.mp4", kind="video", path="/x", size_bytes=3 * 1024**3, owner_id=owner.id,
        ))
    with session_scope() as session:
        assert session.query(Upload).one().size_bytes == 3 * 1024**3
