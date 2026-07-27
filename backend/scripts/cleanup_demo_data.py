#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from app.core.config import get_settings
from app.db.session import create_database_engine, create_session_factory, session_scope
from app.services.cleanup import DemoCleanupService


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean expired EnterpriseRAG demo data safely.")
    parser.add_argument("--dry-run", action="store_true", help="Report without deleting anything.")
    arguments = parser.parse_args()
    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        result = DemoCleanupService(session, settings).run(dry_run=arguments.dry_run)
    print(json.dumps(result.__dict__, sort_keys=True))
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
