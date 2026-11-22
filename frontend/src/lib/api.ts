export type SortKey =
  | "best_deal"
  | "price_asc"
  | "price_desc"
  | "ram_desc"
  | "match_desc"
  | "acquisition_desc"
  | "newest"
  | "profit_desc"
  | "opportunity"
  | "landed_asc";

export interface Search {
  id: number;
  name: string;
  keyword: string;
  cpu: string;
  cpu_family: string;
  ram_min: number | null;
  storage_min: number | null;
  gpu: string;
  screen_min: number | null;
  screen_max: number | null;
  price_min: number | null;
  price_max: number | null;
  brand: string;
  condition: string;
  location: string;
  shipping_available: boolean;
  include_missing_specs: boolean;
  category: string;
  auto_check_enabled: boolean;
  interval: string;
  kind: "laptop" | "gpu";
  notify_telegram: boolean;
  created_at: string | null;
  updated_at: string | null;
  last_run_at: string | null;
  last_run_status: string | null;
  result_count: number;
}

export type SearchInput = Omit<
  Search,
  | "id"
  | "created_at"
  | "updated_at"
  | "last_run_at"
  | "last_run_status"
  | "result_count"
>;

export interface Run {
  id: number;
  search_id: number;
  search_name: string | null;
  trigger: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  queries_total: number;
  results_total: number;
  new_count: number;
  updated_count: number;
  skipped_count: number;
  datadome_blocked: boolean;
  error: string | null;
}

export interface ListingCard {
  id: number;
  url: string;
  subject: string;
  price_eur: number | null;
  city: string;
  brand: string;
  condition: string;
  images: any[];
  first_publication_date: string;
  specs: Record<string, any>;
  spec_confidence: Record<string, string>;
  ai_description: string;
  deal_score: number | null;
  deal_label: string | null;
  match_score: number | null;
  acquisition_score: number | null;
  market_median_eur: number | null;
  dz_price_median_dzd: number | null;
  dz_landed_dzd: number | null;
  dz_saving_pct: number | null;
  ai_verdict_label: string | null;
  ai_profit_eur: number | null;
  profit_ask_eur: number | null;
  freshness_score: number | null;
  age_hours: number | null;
  is_active: boolean;
  ship_ok: string | null;
  risk_flags: string[];
  screen_skip: string;
  pipeline_status: string;
  is_new: boolean;
  found_at: string | null;
}

export interface ResultsResponse {
  search_id: number;
  search_name: string;
  total: number;
  returned: number;
  sort: string;
  items: ListingCard[];
}

export interface PricePoint {
  observed_at: string;
  price_eur: number | null;
}

export interface LandedCost {
  kind: string;
  price_eur: number;
  shipping: Record<string, any>;
  customs: Record<string, any>;
  transfer_fee_eur: number;
  total_eur: number;
  total_dzd: number;
  parallel_rate: number;
  breakdown: { key: string; label: string; eur: number; dzd: number }[];
}

export interface NegotiationRecs {
  ask_eur: number | null;
  offer_eur: number | null;
  target_eur: number | null;
  max_eur: number | null;
  rationale: string;
}

export interface ListingDetail {
  id: number;
  list_id: string | null;
  url: string;
  subject: string;
  price_cents: number | null;
  price_eur: number | null;
  category_id: string;
  city: string;
  zipcode: string;
  department: string;
  brand: string;
  condition: string;
  description: string;
  images: any[];
  first_publication_date: string;
  is_boosted: boolean;
  is_pro: boolean;
  specs: Record<string, any>;
  spec_confidence: Record<string, string>;
  spec_method: Record<string, string>;
  ai_description: string;
  spec_notes: { model?: string; at?: string; evidence?: Record<string, string>; filled?: string[] };
  model_key: string;
  market_low_eur: number | null;
  market_median_eur: number | null;
  market_high_eur: number | null;
  market_confidence: string | null;
  market_samples: number;
  deal_score: number | null;
  deal_label: string | null;
  match_score: number | null;
  acquisition_score: number | null;
  dz_price_low_dzd: number | null;
  dz_price_median_dzd: number | null;
  dz_price_high_dzd: number | null;
  dz_landed_dzd: number | null;
  dz_saving_pct: number | null;
  dz_confidence: string | null;
  dz_query: string | null;
  dz_sources: { title: string; url: string }[];
  ai_verdict: Verdict | null;
  ai_verdict_label: string | null;
  ai_profit_eur: number | null;
  profit_ask_eur: number | null;
  freshness_score: number | null;
  is_active: boolean;
  gone_at: string | null;
  ship_ok: string | null;
  risk_flags: string[];
  screen_skip: string;
  index_date: string;
  repost_count: number;
  pipeline_status: string;
  bought_price_eur: number | null;
  sold_price_dzd: number | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  last_analyzed_at: string | null;
  price_history: PricePoint[];
  market_explanation: string;
  negotiation: NegotiationRecs;
  landed_cost: LandedCost;
  dz_error: string;
}

export interface QuoteResponse {
  offer_price_eur: number;
  deal_score: number | null;
  deal_label: string | null;
  saving_vs_ask_eur: number | null;
  landed_cost: LandedCost;
  market: Record<string, any>;
  negotiation: NegotiationRecs;
}

export interface NegotiationOut {
  id: number;
  listing_id: number;
  batch_id: string | null;
  tone: string;
  ask_price_eur: number | null;
  offer_price_eur: number | null;
  target_price_eur: number | null;
  max_price_eur: number | null;
  message_fr: string;
  model: string;
  created_at: string | null;
}

export type EnrichStep = "specs" | "price" | "verdict";
export interface EnrichItem {
  id: number;
  subject: string;
  steps: Record<EnrichStep, "pending" | "running" | "done" | "skipped" | "error">;
  notes: Partial<Record<EnrichStep, string>>;
  verdict: string | null;
  finished: boolean;
}
export interface EnrichStatus {
  running: boolean;
  items: EnrichItem[];
  models: Partial<Record<EnrichStep, string>>;
  error: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface Settings {
  id: number;
  porsay_address: string;
  eur_dzd_parallel: number;
  eur_dzd_official: number;
  llm_enabled: boolean;
  llm_provider: string;
  llm_api_key: string;
  llm_model: string;
  spec_model: string;
  dz_price_enabled: boolean;
  gemini_model: string;
  verdict_model: string;
  telegram_enabled: boolean;
  telegram_bot_token: string;
  telegram_chat_id: string;
  telegram_token_set: boolean;
  notify_min_verdict: string;
  notify_max_per_run: number;
  max_ad_age_hours: number;
  quiet_start_hour: number | null;
  quiet_end_hour: number | null;
  resale_haircut_pct: number;
  avg_discount_pct: number;
  alert_pickup_only: boolean;
  customs_mode: string;
  duty_rate: number;
  vat_rate: number;
  solidarity_rate: number;
  personal_exemption_dzd: number;
  personal_flat_threshold_dzd: number;
  personal_flat_rate: number;
  customs_fixed_fee_eur: number;
  transfer_fee_eur: number;
  porsay_tariff: { max_kg: number; price_eur: number }[];
  porsay_per_kg_over: number;
  porsay_handling_eur: number;
  default_packaging_kg: number;
  laptop_weight_kg: number;
  gpu_weight_kg: number;
  laptop_box_cm: number[];
  gpu_box_cm: number[];
  auto_check_enabled: boolean;
  updated_at: string | null;
}

export interface Dashboard {
  kpis: {
    active_searches: number;
    new_today: number;
    best_deal: Record<string, any> | null;
    total_listings: number;
  };
  recent_runs: Run[];
  best_deals: ListingCard[];
  alerts: {
    type: string;
    listing_id?: number;
    run_id?: number;
    search_id?: number;
    search_name?: string;
    subject?: string;
    status?: string;
    old_eur?: number;
    new_eur?: number;
    at: string;
    message: string;
  }[];
}

export interface SystemHealth {
  ok: boolean;
  problems: { kind: string; severity: "error" | "warning"; message: string }[];
  openrouter_key: "ok" | "missing" | "rejected" | "unknown";
  scan: {
    last_success_at: string | null;
    minutes_since_success: number | null;
    blocked_streak: number;
    auto_searches: number;
    expected_interval_minutes: number | null;
  };
  dz_lookups_24h: { ok: number; total: number };
}

export interface LiveRun {
  run_id: number;
  search_id: number;
  search_name: string;
  trigger: string;
  stage: string;
  stage_label: string;
  pct: number;
  queries_done: number;
  queries_total: number;
  ads_found: number;
  started_at: string;
  elapsed_s: number;
}

export interface LiveEvent {
  at: string;
  kind: string;
  level: "info" | "success" | "error";
  message: string;
  search_id?: number;
}

export interface LiveStatus {
  now: string;
  scheduler: "running" | "starting" | "cron";
  uptime_s: number;
  tick_every_s: number;
  last_tick_s_ago: number | null;
  auto_enabled: boolean;
  running: LiveRun[];
  next: { search_id: number; name: string; due_in_s: number } | null;
  upcoming: { search_id: number; name: string; due_in_s: number }[];
  last_run: { id: number; search_id: number | null; status: string; new_count: number; results_total: number; finished_at: string | null } | null;
  telegram: { enabled: boolean; linked: boolean; last_poll_s_ago: number | null };
  openrouter: "ok" | "missing" | "rejected" | "unknown";
  ok: boolean;
  problems: { kind: string; severity: "error" | "warning"; message: string }[];
  events: LiveEvent[];
}

export interface ActNow {
  items: ListingCard[];
  unpriced_fresh: number;
  max_age_hours: number;
}

export interface ConnectionTest {
  ok: boolean;
  message: string;
  steps?: { name: string; ok: boolean; detail: string }[];
  ads?: number;
}

export interface PriceBookRow {
  id: number;
  key: string;
  query: string;
  kind: string;
  manual: boolean;
  ok: boolean;
  low_dzd: number | null;
  median_dzd: number | null;
  high_dzd: number | null;
  confidence: string;
  note: string;
  sources: { title: string; url: string }[];
  fetched_at: string | null;
}

export interface PipelineRow extends ListingCard {
  bought_price_eur: number | null;
  sold_price_dzd: number | null;
  realised: { cost_eur: number; revenue_eur: number; profit_eur: number; margin_pct: number } | null;
}

export interface PipelineBoard {
  count: number;
  sold: number;
  realised_profit_eur: number;
  learned: { avg_discount_pct: number; resale_haircut_pct: number };
  rows: PipelineRow[];
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers:
      init?.body instanceof FormData
        ? undefined
        : { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
      else if (Array.isArray(data?.detail)) detail = data.detail.map((d: any) => d.msg).join("; ");
    } catch {
      /* ignore non-JSON errors */
    }
    if (response.status === 401 && !path.startsWith("/api/auth/")) {
      window.dispatchEvent(new Event("auth-required"));
    }
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function qs(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "" || value === false) continue;
    search.set(key, String(value));
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

export const api = {
  auth: {
    me: () => request<{ auth_required: boolean; authenticated: boolean }>("/api/auth/me"),
    login: (password: string) =>
      request<{ ok: boolean }>("/api/auth/login", { method: "POST", body: JSON.stringify({ password }) }),
    logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  },

  dashboard: () => request<Dashboard>("/api/dashboard"),

  searches: {
    list: () => request<Search[]>("/api/searches"),
    get: (id: number) => request<Search>(`/api/searches/${id}`),
    create: (payload: Partial<SearchInput>) =>
      request<Search>("/api/searches", { method: "POST", body: JSON.stringify(payload) }),
    update: (id: number, payload: Partial<SearchInput>) =>
      request<Search>(`/api/searches/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    remove: (id: number) => request<void>(`/api/searches/${id}`, { method: "DELETE" }),
    run: (id: number, pages = 3, delay = 1.5) =>
      request<Run>(`/api/searches/${id}/run${qs({ pages, delay })}`, { method: "POST" }),
    runAsync: (id: number, pages = 3, delay = 1.5) =>
      request<{ started: boolean; already_running: boolean; finished?: boolean }>(
        `/api/searches/${id}/run-async${qs({ pages, delay })}`,
        { method: "POST" },
      ),
    enrich: (id: number, auto = true) =>
      request<EnrichStatus & { started: boolean; reason: string }>(`/api/searches/${id}/enrich${qs({ auto })}`, { method: "POST" }),
    alertNow: (id: number) =>
      request<{ sent: number; fresh: number; candidates?: number; verdicts?: number; ai_checked?: number; quiet?: number; gone?: number; min_verdict: string }>(
        `/api/searches/${id}/alert-now`,
        { method: "POST" },
      ),
    enrichStatus: (id: number) => request<EnrichStatus>(`/api/searches/${id}/enrich`),
    runs: (id: number) => request<Run[]>(`/api/searches/${id}/runs`),
    results: (id: number, params: Record<string, unknown>) =>
      request<ResultsResponse>(`/api/searches/${id}/results${qs(params)}`),
    preview: (id: number) =>
      request<{ queries: string[]; leboncoin_urls: string[] }>(
        `/api/searches/${id}/preview-queries`,
      ),
    exportUrl: (id: number) => `/api/searches/${id}/export.csv`,
    importCsv: (id: number, file: File) => {
      const body = new FormData();
      body.append("file", file);
      return request<{
        batch_id: number;
        rows_total: number;
        rows_imported: number;
        rows_skipped: number;
        errors: string[];
      }>(`/api/searches/${id}/import-csv`, { method: "POST", body });
    },
  },

  listings: {
    get: (id: number) => request<ListingDetail>(`/api/listings/${id}`),
    verdict: (id: number, buy_price_eur?: number | null) =>
      request<ListingDetail>(`/api/listings/${id}/verdict`, {
        method: "POST",
        body: JSON.stringify({ buy_price_eur: buy_price_eur ?? null }),
      }),
    bestDeals: () => request<ListingCard[]>("/api/deals/best"),
    refreshDz: (id: number) =>
      request<ListingDetail>(`/api/listings/${id}/dz-price`, { method: "POST" }),
    quote: (
      id: number,
      payload: {
        offer_price_eur?: number | null;
        weight_kg?: number | null;
        kind?: "laptop" | "gpu" | "custom";
        package_cm?: number[] | null;
        condition?: string;
      },
    ) => request<QuoteResponse>(`/api/listings/${id}/quote`, { method: "POST", body: JSON.stringify(payload) }),
    negotiate: (
      id: number,
      payload: { tone: "friendly" | "direct" | "firm"; offer_price_eur?: number | null; custom_note?: string },
    ) =>
      request<NegotiationOut>(`/api/listings/${id}/negotiation`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    bulkNegotiate: (listing_ids: number[], tone: "friendly" | "direct" | "firm") =>
      request<NegotiationOut[]>("/api/negotiations/bulk", {
        method: "POST",
        body: JSON.stringify({ listing_ids, tone }),
      }),
  },

  ops: {
    health: () => request<SystemHealth>("/api/health/system"),
    live: () => request<LiveStatus>("/api/live"),
    actNow: (limit = 6) => request<ActNow>(`/api/deals/act-now?limit=${limit}`),
    pipeline: () => request<PipelineBoard>("/api/pipeline"),
    setPipeline: (id: number, payload: { status: string; bought_price_eur?: number | null; sold_price_dzd?: number | null }) =>
      request<{ status: string }>(`/api/listings/${id}/pipeline`, { method: "PATCH", body: JSON.stringify(payload) }),
    recheck: (id: number) => request<{ state: string; freshness_score: number | null }>(`/api/listings/${id}/recheck`, { method: "POST" }),
    priceBook: () => request<PriceBookRow[]>("/api/price-book"),
    editPrice: (id: number, median_dzd: number) =>
      request<PriceBookRow>(`/api/price-book/${id}`, { method: "PUT", body: JSON.stringify({ median_dzd }) }),
    deletePrice: (id: number) => request<{ deleted: number }>(`/api/price-book/${id}`, { method: "DELETE" }),
    setMyPrice: (listingId: number, median_dzd: number) =>
      request<{ ok: boolean; dz_price_median_dzd: number }>(`/api/listings/${listingId}/dz-price`, {
        method: "PUT",
        body: JSON.stringify({ median_dzd }),
      }),
  },

  settings: {
    get: () => request<Settings>("/api/settings"),
    update: (payload: Partial<Settings>) =>
      request<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(payload) }),
    telegramDetect: () => request<{ chat_id: string; title: string }>("/api/settings/telegram/detect", { method: "POST" }),
    telegramTest: () => request<{ ok: boolean }>("/api/settings/telegram/test", { method: "POST" }),
    testOpenrouter: () => request<ConnectionTest>("/api/settings/test/openrouter", { method: "POST" }),
    testLeboncoin: () => request<ConnectionTest>("/api/settings/test/leboncoin", { method: "POST" }),
  },
};

export interface Verdict {
  verdict: "great" | "good" | "fair" | "skip";
  headline: string;
  opinion: string;
  risks: string[];
  max_buy_price_eur: number | null;
  source: "ai" | "rules";
  model: string;
  generated_at: string;
  numbers: {
    ask_price_eur: number;
    buy_price_eur: number;
    negotiation_saving_eur: number;
    shipping_eur: number;
    customs_eur: number;
    transfer_fee_eur: number;
    total_cost_eur: number;
    total_cost_dzd: number;
    rate: number;
    dz_median_dzd: number;
    dz_median_eur: number;
    dz_net_eur?: number;
    resale_haircut_pct?: number;
    assumed_discount_pct?: number;
    profit_ask_eur?: number;
    margin_ask_pct?: number;
    total_cost_ask_eur?: number;
    dz_confidence: string | null;
    profit_eur: number;
    profit_dzd: number;
    margin_pct: number;
    max_buy_for_good_eur: number;
  };
}
