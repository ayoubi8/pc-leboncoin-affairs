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
    from .models import Settings, DEFAULT_PORSAY_TARIFF, DEFAULT_PORSAY_PER_KG_OVER, LEGACY_PORSAY_TARIFF

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
    with SessionLocal() as db:
        existing = db.get(Settings, 1)
        if existing is not None and list(existing.porsay_tariff or []) == LEGACY_PORSAY_TARIFF:
            # still on the old made-up defaults: move to the real Porsay Colissimo prices
            existing.porsay_tariff = list(DEFAULT_PORSAY_TARIFF)
            existing.porsay_per_kg_over = DEFAULT_PORSAY_PER_KG_OVER
            db.commit()
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

    with engine.begin() as conn:
        inspector = inspect(conn)  # same connection: a second one would deadlock on SQLite's write lock
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
            conn.execute(text("UPDATE settings SET max_ad_age_hours = 48 WHERE max_ad_age_hours IS NULL"))
            conn.execute(text("UPDATE settings SET telegram_update_offset = 0 WHERE telegram_update_offset IS NULL"))
            conn.execute(text("UPDATE settings SET resale_haircut_pct = 10 WHERE resale_haircut_pct IS NULL"))
            conn.execute(text("UPDATE settings SET avg_discount_pct = 6 WHERE avg_discount_pct IS NULL"))
            conn.execute(text("UPDATE settings SET alert_pickup_only = false WHERE alert_pickup_only IS NULL"))
        if inspector.has_table("searches"):
            conn.execute(text("UPDATE searches SET kind = 'laptop' WHERE kind IS NULL OR kind = ''"))
            conn.execute(text("UPDATE searches SET notify_telegram = false WHERE notify_telegram IS NULL"))
        if inspector.has_table("listings"):
            conn.execute(text("UPDATE listings SET is_active = true WHERE is_active IS NULL"))
            conn.execute(text("UPDATE listings SET repost_count = 0 WHERE repost_count IS NULL"))
            conn.execute(text("UPDATE listings SET index_date = '' WHERE index_date IS NULL"))
            conn.execute(text("UPDATE listings SET seller_id = '' WHERE seller_id IS NULL"))
            conn.execute(text("UPDATE listings SET fingerprint = '' WHERE fingerprint IS NULL"))
            conn.execute(text("UPDATE listings SET pipeline_status = '' WHERE pipeline_status IS NULL"))
            conn.execute(text("UPDATE listings SET screen_skip = '' WHERE screen_skip IS NULL"))
        if inspector.has_table("dz_prices"):
            conn.execute(text("UPDATE dz_prices SET manual = false WHERE manual IS NULL"))
            conn.execute(text("UPDATE dz_prices SET kind = 'laptop' WHERE kind IS NULL OR kind = ''"))
