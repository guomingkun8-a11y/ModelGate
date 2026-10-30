"""Async database engine and startup schema migrations."""

from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.persistence.models import Base

BACKEND_DIR = Path(__file__).resolve().parents[2]
BASE_TABLES = set(Base.metadata.tables) - {"users", "auth_sessions"}
ACCOUNT_TABLES = {"users", "auth_sessions"}


def create_engine_and_sessionmaker(settings: Settings):
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


def legacy_revision(tables: set[str], columns: dict[str, set[str]]) -> str | None:
    """Return the baseline revision for a complete unversioned ModelGate schema."""
    app_tables = BASE_TABLES | ACCOUNT_TABLES
    if not tables & app_tables:
        return None

    current_schema = set(Base.metadata.tables)
    if current_schema <= tables and all(
        {column.name for column in Base.metadata.tables[table].columns} <= columns[table]
        for table in current_schema
    ):
        return "head"

    old_columns = {
        table: {column.name for column in Base.metadata.tables[table].columns} - {"owner_id"}
        for table in BASE_TABLES
    }
    if (
        BASE_TABLES <= tables
        and not (ACCOUNT_TABLES & tables)
        and all(expected <= columns.get(table, set()) for table, expected in old_columns.items())
    ):
        return "0001_initial"

    raise RuntimeError(
        "ModelGate database has an incomplete unversioned schema. "
        "Restore a backup or repair the schema before starting the server."
    )


def _run_alembic(database_url: str, stamp_revision: str | None) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["database_url"] = database_url
    if stamp_revision:
        command.stamp(config, stamp_revision)
    command.upgrade(config, "head")


async def upgrade_schema(engine, settings: Settings) -> None:
    """Upgrade a fresh, legacy, or already-versioned PostgreSQL database."""
    if engine.dialect.name != "postgresql":
        raise RuntimeError("ModelGate production migrations require PostgreSQL.")

    async with engine.connect() as connection:
        await connection.execute(text(
            "SELECT pg_advisory_lock(hashtext(current_database()), hashtext('modelgate-migrations'))"
        ))
        try:
            def inspect_schema(sync_connection):
                inspector = inspect(sync_connection)
                tables = set(inspector.get_table_names())
                if "alembic_version" in tables:
                    return None
                columns = {
                    table: {column["name"] for column in inspector.get_columns(table)}
                    for table in tables & (BASE_TABLES | ACCOUNT_TABLES)
                }
                return legacy_revision(tables, columns)

            stamp_revision = await connection.run_sync(inspect_schema)
            await asyncio.to_thread(_run_alembic, settings.database_url, stamp_revision)
        finally:
            await connection.execute(text(
                "SELECT pg_advisory_unlock(hashtext(current_database()), hashtext('modelgate-migrations'))"
            ))
