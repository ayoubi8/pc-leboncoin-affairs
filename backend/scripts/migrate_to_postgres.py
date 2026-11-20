"""Copy the local SQLite database into Postgres (Supabase).

Usage (from backend/):  python scripts/migrate_to_postgres.py "postgresql://user:pass@host:5432/postgres"
Run it once, against an EMPTY database. Use the direct (port 5432) connection string.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402

from app import config, models  # noqa: E402,F401
from app.db import Base  # noqa: E402


def main(target_url: str) -> None:
    source = create_engine(f"sqlite:///{(config.DATA_DIR / 'app.db').as_posix()}", future=True)
    target = create_engine(config._normalize_db_url(target_url), future=True)
    Base.metadata.create_all(target)
    with source.connect() as src, target.begin() as dst:
        existing = dst.execute(text("SELECT count(*) FROM settings")).scalar()
        if existing:
            dst.execute(text("DELETE FROM settings"))  # drop the default row init_db may have made
        for table in Base.metadata.sorted_tables:
            rows = [dict(r._mapping) for r in src.execute(table.select())]
            if rows:
                dst.execute(table.insert(), rows)
            if "id" in table.c and rows:
                dst.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), (SELECT max(id) FROM {table.name}))"
                ))
            print(f"{table.name}: {len(rows)} rows")
    print("done")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
