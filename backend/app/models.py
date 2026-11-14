from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


DEFAULT_PORSAY_TARIFF = [
    {"max_kg": 1, "price_eur": 40.0},
    {"max_kg": 2, "price_eur": 52.0},
    {"max_kg": 5, "price_eur": 70.0},
    {"max_kg": 10, "price_eur": 115.0},
    {"max_kg": 15, "price_eur": 150.0},
    {"max_kg": 20, "price_eur": 180.0},
    {"max_kg": 25, "price_eur": 210.0},
    {"max_kg": 30, "price_eur": 240.0},
]
DEFAULT_PORSAY_PER_KG_OVER = 8.0


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, default=1)

    porsay_address = Column(String(500), default="")
    eur_dzd_parallel = Column(Float, default=276.0)
    eur_dzd_official = Column(Float, default=151.2)

    llm_enabled = Column(Boolean, default=True)
    llm_provider = Column(String(50), default="openrouter")
    llm_api_key = Column(String(500), default="")
    llm_model = Column(String(200), default="google/gemini-2.0-flash-lite-001")

    customs_mode = Column(String(30), default="personal")
    duty_rate = Column(Float, default=0.05)
    vat_rate = Column(Float, default=0.19)
    solidarity_rate = Column(Float, default=0.03)
    personal_exemption_dzd = Column(Float, default=50000.0)
    personal_flat_threshold_dzd = Column(Float, default=100000.0)
    personal_flat_rate = Column(Float, default=0.30)
    customs_fixed_fee_eur = Column(Float, default=0.0)
    transfer_fee_eur = Column(Float, default=0.0)

    porsay_tariff = Column(JSON, default=lambda: list(DEFAULT_PORSAY_TARIFF))
    porsay_per_kg_over = Column(Float, default=DEFAULT_PORSAY_PER_KG_OVER)
    porsay_handling_eur = Column(Float, default=0.0)
    default_packaging_kg = Column(Float, default=0.3)
    laptop_weight_kg = Column(Float, default=2.5)
    gpu_weight_kg = Column(Float, default=1.8)
    laptop_box_cm = Column(JSON, default=lambda: [40, 30, 8])
    gpu_box_cm = Column(JSON, default=lambda: [35, 20, 10])

    auto_check_enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class Search(Base):
    __tablename__ = "searches"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    keyword = Column(String(300), default="")

    # hardware criteria (all optional)
    cpu = Column(String(120), default="")
    cpu_family = Column(String(60), default="")
    ram_min = Column(Integer, nullable=True)
    storage_min = Column(Integer, nullable=True)  # GB
    gpu = Column(String(120), default="")
    screen_min = Column(Float, nullable=True)
    screen_max = Column(Float, nullable=True)

    # price / meta
    price_min = Column(Float, nullable=True)
    price_max = Column(Float, nullable=True)
    brand = Column(String(80), default="")
    condition = Column(String(40), default="")
    location = Column(String(120), default="")
    shipping_available = Column(Boolean, default=False)
    include_missing_specs = Column(Boolean, default=True)
    category = Column(String(20), default="")

    # behaviour
    auto_check_enabled = Column(Boolean, default=False)
    interval = Column(String(20), default="daily")  # daily | 6h | weekly
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    last_run_at = Column(DateTime, nullable=True)
    last_run_status = Column(String(30), nullable=True)

    runs = relationship("Run", back_populates="search", cascade="all, delete-orphan")
    links = relationship("SearchListing", back_populates="search", cascade="all, delete-orphan")


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True)
    search_id = Column(Integer, ForeignKey("searches.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger = Column(String(20), default="manual")  # manual | auto
    status = Column(String(20), default="running")  # running | success | failed | blocked
    started_at = Column(DateTime, default=utcnow)
    finished_at = Column(DateTime, nullable=True)
    queries_total = Column(Integer, default=0)
    results_total = Column(Integer, default=0)
    new_count = Column(Integer, default=0)
    updated_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    datadome_blocked = Column(Boolean, default=False)
    error = Column(Text, nullable=True)

    search = relationship("Search", back_populates="runs")


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True)
    list_id = Column(String(60), unique=True, index=True, nullable=True)
    url = Column(String(700), index=True, default="")
    subject = Column(String(500), default="")
    price_cents = Column(Integer, nullable=True)
    price_eur = Column(Float, nullable=True)
    category_id = Column(String(20), index=True, default="")
    city = Column(String(120), default="")
    zipcode = Column(String(20), default="")
    department = Column(String(120), default="")
    brand = Column(String(120), default="")
    condition = Column(String(60), default="")
    description = Column(Text, default="")
    images = Column(JSON, default=list)
    first_publication_date = Column(String(40), default="")
    is_boosted = Column(Boolean, default=False)
    is_pro = Column(Boolean, default=False)

    # extraction
    specs = Column(JSON, default=dict)
    spec_confidence = Column(JSON, default=dict)
    spec_method = Column(JSON, default=dict)
    model_key = Column(String(160), index=True, default="")

    # intelligence (cached)
    market_low_eur = Column(Float, nullable=True)
    market_median_eur = Column(Float, nullable=True)
    market_high_eur = Column(Float, nullable=True)
    market_confidence = Column(String(20), nullable=True)
    market_samples = Column(Integer, default=0)
    deal_score = Column(Float, nullable=True)
    deal_label = Column(String(20), nullable=True)
    match_score = Column(Float, nullable=True)
    acquisition_score = Column(Float, nullable=True)

    raw = Column(JSON, default=dict)
    first_seen_at = Column(DateTime, default=utcnow)
    last_seen_at = Column(DateTime, default=utcnow)
    last_analyzed_at = Column(DateTime, nullable=True)

    links = relationship("SearchListing", back_populates="listing", cascade="all, delete-orphan")
    snapshots = relationship("PriceSnapshot", back_populates="listing", cascade="all, delete-orphan")
    negotiations = relationship("Negotiation", back_populates="listing", cascade="all, delete-orphan")


class SearchListing(Base):
    __tablename__ = "search_listings"
    __table_args__ = (UniqueConstraint("search_id", "listing_id", name="uq_search_listing"),)

    id = Column(Integer, primary_key=True)
    search_id = Column(Integer, ForeignKey("searches.id", ondelete="CASCADE"), nullable=False, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True)
    found_at = Column(DateTime, default=utcnow)

    search = relationship("Search", back_populates="links")
    listing = relationship("Listing", back_populates="links")


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True)
    price_eur = Column(Float, nullable=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="SET NULL"), nullable=True)
    observed_at = Column(DateTime, default=utcnow, index=True)

    listing = relationship("Listing", back_populates="snapshots")


class Negotiation(Base):
    __tablename__ = "negotiations"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(String(40), nullable=True, index=True)
    tone = Column(String(20), default="friendly")
    ask_price_eur = Column(Float, nullable=True)
    offer_price_eur = Column(Float, nullable=True)
    target_price_eur = Column(Float, nullable=True)
    max_price_eur = Column(Float, nullable=True)
    message_fr = Column(Text, default="")
    model = Column(String(120), default="")
    created_at = Column(DateTime, default=utcnow)

    listing = relationship("Listing", back_populates="negotiations")


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(Integer, primary_key=True)
    search_id = Column(Integer, ForeignKey("searches.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(300), default="")
    rows_total = Column(Integer, default=0)
    rows_imported = Column(Integer, default=0)
    rows_skipped = Column(Integer, default=0)
    status = Column(String(20), default="success")
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class LlmCache(Base):
    __tablename__ = "llm_cache"

    id = Column(Integer, primary_key=True)
    cache_key = Column(String(64), unique=True, index=True, nullable=False)
    kind = Column(String(40), default="")
    response = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)
