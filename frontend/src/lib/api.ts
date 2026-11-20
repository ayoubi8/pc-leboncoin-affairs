export type SortKey =
  | "best_deal"
  | "price_asc"
  | "price_desc"
  | "ram_desc"
  | "match_desc"
  | "acquisition_desc"
  | "newest"
  | "profit_desc"
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

export interface Settings {
  id: number;
  porsay_address: string;
  eur_dzd_parallel: number;
  eur_dzd_official: number;
  llm_enabled: boolean;
  llm_provider: string;
  llm_api_key: string;
  llm_model: string;
  dz_price_enabled: boolean;
  gemini_model: string;
  verdict_model: string;
  telegram_enabled: boolean;
  telegram_bot_token: string;
  telegram_chat_id: string;
  telegram_token_set: boolean;
  notify_min_verdict: string;
  notify_max_per_run: number;
  customs_mode: string;
  duty_rate: number;
  vat_rate: number;
  solidarity_rate: number;
  personal_exemption_dzd: number;
  personal_flat_threshold_dzd: number;
  personal_flat_rate: number;
  customs_fixed_fee_eur: number;
  transfer_fee_eur: number;
  porsay_tariff: { up_to_kg: number; price_eur: number }[];
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

  settings: {
    get: () => request<Settings>("/api/settings"),
    update: (payload: Partial<Settings>) =>
      request<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(payload) }),
    telegramDetect: () => request<{ chat_id: string; title: string }>("/api/settings/telegram/detect", { method: "POST" }),
    telegramTest: () => request<{ ok: boolean }>("/api/settings/telegram/test", { method: "POST" }),
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
    dz_confidence: string | null;
    profit_eur: number;
    profit_dzd: number;
    margin_pct: number;
    max_buy_for_good_eur: number;
  };
}
