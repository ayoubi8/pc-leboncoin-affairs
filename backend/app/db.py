from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
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
    with SessionLocal() as db:
        if db.get(Settings, 1) is None:
            db.add(
                Settings(
                    id=1,
                    porsay_tariff=list(DEFAULT_PORSAY_TARIFF),
                )
            )
            db.commit()
