from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- settings
class SettingsOut(ORMModel):
    id: int
    porsay_address: str = ""
    eur_dzd_parallel: float = 276.0
    eur_dzd_official: float = 151.2
    llm_enabled: bool = True
    llm_provider: str = "openrouter"
    llm_api_key: str = ""
    llm_model: str = ""
    customs_mode: str = "personal"
    duty_rate: float = 0.05
    vat_rate: float = 0.19
    solidarity_rate: float = 0.03
    personal_exemption_dzd: float = 50000
    personal_flat_threshold_dzd: float = 100000
    personal_flat_rate: float = 0.30
    customs_fixed_fee_eur: float = 0.0
    transfer_fee_eur: float = 0.0
    porsay_tariff: list[dict[str, Any]] = Field(default_factory=list)
    porsay_per_kg_over: float = 8.0
    porsay_handling_eur: float = 0.0
    default_packaging_kg: float = 0.3
    laptop_weight_kg: float = 2.5
    gpu_weight_kg: float = 1.8
    laptop_box_cm: list[float] = Field(default_factory=lambda: [40, 30, 8])
    gpu_box_cm: list[float] = Field(default_factory=lambda: [35, 20, 10])
    auto_check_enabled: bool = True
    llm_key_set: bool = False
    updated_at: Optional[datetime] = None


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    porsay_address: Optional[str] = None
    eur_dzd_parallel: Optional[float] = None
    eur_dzd_official: Optional[float] = None
    llm_enabled: Optional[bool] = None
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    customs_mode: Optional[str] = None
    duty_rate: Optional[float] = None
    vat_rate: Optional[float] = None
    solidarity_rate: Optional[float] = None
    personal_exemption_dzd: Optional[float] = None
    personal_flat_threshold_dzd: Optional[float] = None
    personal_flat_rate: Optional[float] = None
    customs_fixed_fee_eur: Optional[float] = None
    transfer_fee_eur: Optional[float] = None
    porsay_tariff: Optional[list[dict[str, Any]]] = None
    porsay_per_kg_over: Optional[float] = None
    porsay_handling_eur: Optional[float] = None
    default_packaging_kg: Optional[float] = None
    laptop_weight_kg: Optional[float] = None
    gpu_weight_kg: Optional[float] = None
    laptop_box_cm: Optional[list[float]] = None
    gpu_box_cm: Optional[list[float]] = None
    auto_check_enabled: Optional[bool] = None


# ---------------------------------------------------------------- searches
class SearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    keyword: str = ""
    cpu: str = ""
    cpu_family: str = ""
    ram_min: Optional[int] = None
    storage_min: Optional[int] = None
    gpu: str = ""
    screen_min: Optional[float] = None
    screen_max: Optional[float] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    brand: str = ""
    condition: str = ""
    location: str = ""
    shipping_available: bool = False
    include_missing_specs: bool = True
    category: str = ""
    auto_check_enabled: bool = False
    interval: Literal["daily", "6h", "weekly"] = "daily"


class SearchUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    keyword: Optional[str] = None
    cpu: Optional[str] = None
    cpu_family: Optional[str] = None
    ram_min: Optional[int] = None
    storage_min: Optional[int] = None
    gpu: Optional[str] = None
    screen_min: Optional[float] = None
    screen_max: Optional[float] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    brand: Optional[str] = None
    condition: Optional[str] = None
    location: Optional[str] = None
    shipping_available: Optional[bool] = None
    include_missing_specs: Optional[bool] = None
    category: Optional[str] = None
    auto_check_enabled: Optional[bool] = None
    interval: Optional[str] = None


class SearchOut(ORMModel):
    id: int
    name: str
    keyword: str = ""
    cpu: str = ""
    cpu_family: str = ""
    ram_min: Optional[int] = None
    storage_min: Optional[int] = None
    gpu: str = ""
    screen_min: Optional[float] = None
    screen_max: Optional[float] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    brand: str = ""
    condition: str = ""
    location: str = ""
    shipping_available: bool = False
    include_missing_specs: bool = True
    category: str = ""
    auto_check_enabled: bool = False
    interval: str = "daily"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    result_count: int = 0


class QueryPreview(BaseModel):
    queries: list[str]
    leboncoin_urls: list[str]


# ---------------------------------------------------------------- runs
class RunOut(ORMModel):
    id: int
    search_id: int
    search_name: Optional[str] = None
    trigger: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    queries_total: int = 0
    results_total: int = 0
    new_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    datadome_blocked: bool = False
    error: Optional[str] = None


# ---------------------------------------------------------------- listings
class ListingOut(ORMModel):
    id: int
    list_id: Optional[str] = None
    url: str = ""
    subject: str = ""
    price_cents: Optional[int] = None
    price_eur: Optional[float] = None
    category_id: str = ""
    city: str = ""
    zipcode: str = ""
    department: str = ""
    brand: str = ""
    condition: str = ""
    description: str = ""
    images: list[Any] = Field(default_factory=list)
    first_publication_date: str = ""
    is_boosted: bool = False
    is_pro: bool = False
    specs: dict[str, Any] = Field(default_factory=dict)
    spec_confidence: dict[str, Any] = Field(default_factory=dict)
    spec_method: dict[str, Any] = Field(default_factory=dict)
    model_key: str = ""
    market_low_eur: Optional[float] = None
    market_median_eur: Optional[float] = None
    market_high_eur: Optional[float] = None
    market_confidence: Optional[str] = None
    market_samples: int = 0
    deal_score: Optional[float] = None
    deal_label: Optional[str] = None
    match_score: Optional[float] = None
    acquisition_score: Optional[float] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    last_analyzed_at: Optional[datetime] = None


class ListingCard(BaseModel):
    id: int
    url: str = ""
    subject: str = ""
    price_eur: Optional[float] = None
    city: str = ""
    brand: str = ""
    condition: str = ""
    images: list[Any] = Field(default_factory=list)
    first_publication_date: str = ""
    specs: dict[str, Any] = Field(default_factory=dict)
    spec_confidence: dict[str, Any] = Field(default_factory=dict)
    deal_score: Optional[float] = None
    deal_label: Optional[str] = None
    match_score: Optional[float] = None
    acquisition_score: Optional[float] = None
    market_median_eur: Optional[float] = None
    is_new: bool = False
    found_at: Optional[datetime] = None


class ResultsResponse(BaseModel):
    search_id: int
    search_name: str
    total: int
    returned: int
    sort: str
    items: list[ListingCard]


class PricePoint(BaseModel):
    observed_at: datetime
    price_eur: Optional[float] = None


class ListingDetail(ListingOut):
    price_history: list[PricePoint] = Field(default_factory=list)
    market_explanation: str = ""
    negotiation: dict[str, Any] = Field(default_factory=dict)
    landed_cost: dict[str, Any] = Field(default_factory=dict)


class QuoteRequest(BaseModel):
    offer_price_eur: Optional[float] = None
    weight_kg: Optional[float] = None
    kind: Literal["laptop", "gpu", "custom"] = "laptop"
    package_cm: Optional[list[float]] = None
    condition: str = ""


class QuoteResponse(BaseModel):
    offer_price_eur: float
    deal_score: Optional[float] = None
    deal_label: Optional[str] = None
    saving_vs_ask_eur: Optional[float] = None
    landed_cost: dict[str, Any]
    market: dict[str, Any]
    negotiation: dict[str, Any]


# ---------------------------------------------------------------- negotiation
class NegotiationRequest(BaseModel):
    tone: Literal["friendly", "direct", "firm"] = "friendly"
    offer_price_eur: Optional[float] = None
    custom_note: str = ""


class BulkNegotiationRequest(BaseModel):
    listing_ids: list[int]
    tone: Literal["friendly", "direct", "firm"] = "friendly"


class NegotiationOut(ORMModel):
    id: int
    listing_id: int
    batch_id: Optional[str] = None
    tone: str
    ask_price_eur: Optional[float] = None
    offer_price_eur: Optional[float] = None
    target_price_eur: Optional[float] = None
    max_price_eur: Optional[float] = None
    message_fr: str = ""
    model: str = ""
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------- dashboard
class DashboardKPIs(BaseModel):
    active_searches: int
    new_today: int
    best_deal: Optional[dict[str, Any]] = None
    total_listings: int


class DashboardOut(BaseModel):
    kpis: DashboardKPIs
    recent_runs: list[RunOut]
    best_deals: list[ListingCard]
    alerts: list[dict[str, Any]]


# ---------------------------------------------------------------- imports
class ImportResult(BaseModel):
    batch_id: int
    rows_total: int
    rows_imported: int
    rows_skipped: int
    errors: list[str] = Field(default_factory=list)
