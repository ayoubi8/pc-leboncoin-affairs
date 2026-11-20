from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, future=True)
else:
    # Postgres (Supabase). Its pooler runs in transaction mode, so no server-side prepared
    # statements, and serverless instances should not keep idle connections open.
    engine = create_engine(
        DATABASE_URL,
        connect_args={"prepare_threshold": None},
        poolclass=NullPool,
        future=True,
    )
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (register models)
    from .models import Settings, DEFAULT_PORSAY_TARIFF

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
    with SessionLocal() as db:
        if db.get(Settings, 1) is None:
            db.add(
                Settings(
                    id=1,
                    porsay_tariff=list(DEFAULT_PORSAY_TARIFF),
                )
            )
            db.commit()


def _add_missing_columns() -> None:
    """Tiny SQLite-friendly migration: add columns new models declare but the table lacks."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {col_type}'))
        # Old default rate was 276; the working rate is now 280 DA per EUR.
        if inspector.has_table("settings"):
            conn.execute(text("UPDATE settings SET eur_dzd_parallel = 280 WHERE eur_dzd_parallel = 276"))
            conn.execute(text("UPDATE settings SET dz_price_enabled = true WHERE dz_price_enabled IS NULL"))
            conn.execute(text("UPDATE settings SET verdict_model = 'anthropic/claude-haiku-5.5' WHERE verdict_model IS NULL OR verdict_model = ''"))
            conn.execute(text("UPDATE settings SET gemini_model = 'google/gemini-2.5-flash-lite' WHERE gemini_model IS NULL OR gemini_model NOT LIKE '%/%'"))
            conn.execute(text("UPDATE settings SET telegram_enabled = false WHERE telegram_enabled IS NULL"))
            conn.execute(text("UPDATE settings SET telegram_bot_token = '' WHERE telegram_bot_token IS NULL"))
            conn.execute(text("UPDATE settings SET telegram_chat_id = '' WHERE telegram_chat_id IS NULL"))
            conn.execute(text("UPDATE settings SET notify_min_verdict = 'good' WHERE notify_min_verdict IS NULL OR notify_min_verdict = ''"))
            conn.execute(text("UPDATE settings SET notify_max_per_run = 5 WHERE notify_max_per_run IS NULL"))
        if inspector.has_table("searches"):
            conn.execute(text("UPDATE searches SET notify_telegram = false WHERE notify_telegram IS NULL"))
