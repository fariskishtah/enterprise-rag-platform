#!/usr/bin/env python3
"""Upgrade the configured database, safely adopting pre-Alembic installations."""

from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.config import get_settings
from app.db.session import create_database_engine


def inferred_revision(tables: set[str]) -> str | None:
    if not tables:
        return None
    if "media_sources" in tables:
        return "0003_media_intelligence"
    if "document_chunks" in tables:
        return "0002_rag"
    if "knowledge_bases" in tables:
        return "0001_phase1"
    raise RuntimeError("The database has unknown tables and cannot be adopted automatically.")


def main() -> int:
    settings = get_settings()
    configuration = Config("/workspace/backend/alembic.ini")
    configuration.set_main_option("sqlalchemy.url", settings.database_url)
    engine = create_database_engine(settings.database_url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    if "alembic_version" not in tables:
        revision = inferred_revision(tables)
        if revision is not None:
            command.stamp(configuration, revision)
    command.upgrade(configuration, "head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
