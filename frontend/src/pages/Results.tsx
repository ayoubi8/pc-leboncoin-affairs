import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Copy, Download, Filter, MessageSquareText, Send, X } from "lucide-react";
import { api, type NegotiationOut, type SortKey } from "../lib/api";
import { eur } from "../lib/utils";
import { toast } from "../lib/toast";
import { Button, Card, CardHeader, EmptyState, Input, Label, Select, Skeleton } from "../components/ui";
import ListingCard from "../components/ListingCard";
import { RunningScan } from "../components/LivePanel";
import AiPanel, { useEnrich } from "../components/AiPanel";
import { useLive } from "../lib/useLive";

const SORTS: { value: SortKey; label: string }[] = [
  { value: "opportunity", label: "Best opportunity (profit × freshness)" },
  { value: "newest", label: "Newest first" },
  { value: "price_asc", label: "Lowest price" },
  { value: "profit_desc", label: "Highest profit" },
];

type Preset = "hot" | "fresh" | "all";
const PRESETS: { id: Preset; label: string; hint: string }[] = [
  { id: "hot", label: "Hot deals", hint: "Good verdict, under 14 days, still online, newest first. Opening it looks up the Algerian price of up to 5 new products" },
  { id: "fresh", label: "Fresh ads", hint: "Under 14 days, still online, matching your search, newest first. Opening it looks up the Algerian price of up to 5 new products" },
  { id: "all", label: "Everything", hint: "Every stored ad, including old and sold" },
];

export default function Results() {
  const { id } = useParams();
  const searchId = Number(id);
  const [sort, setSort] = useState<SortKey>("newest");
  const [preset, setPreset] = useState<Preset | null>("fresh");
  const [showFilters, setShowFilters] = useState(false);
  const queryClient = useQueryClient();
  const { live } = useLive();
  const scanning = live?.running.find((r) => r.search_id === Number(id));
  const [selected, setSelected] = useState<number[]>([]);
  const [tone, setTone] = useState<"friendly" | "direct" | "firm">("friendly");
  const [messages, setMessages] = useState<NegotiationOut[] | null>(null);

  const [filters, setFilters] = useState({
    min_price: "",
    max_price: "",
    min_ram: "",
    min_storage: "",
    brand: "",
    condition: "",
    city: "",
    hide_missing_specs: false,
    new_only: false,
    new_within: "24h",
    good_only: false,
    relevant_only: true,
    show_gone: false,
    max_age_hours: "336",
  });

  const params = useMemo(
    () => ({
      sort,
      min_price: filters.min_price || undefined,
      max_price: filters.max_price || undefined,
      min_ram: filters.min_ram || undefined,
      min_storage: filters.min_storage || undefined,
      brand: filters.brand || undefined,
      condition: filters.condition || undefined,
      city: filters.city || undefined,
      hide_missing_specs: filters.hide_missing_specs || undefined,
      new_only: filters.new_only || undefined,
      new_within: filters.new_only ? filters.new_within : undefined,
      good_only: filters.good_only || undefined,
      relevant_only: filters.relevant_only || undefined,
      hide_gone: filters.show_gone ? "false" : undefined,
      max_age_hours: filters.max_age_hours || undefined,
    }),
    [sort, filters],
  );

  const search = useQuery({ queryKey: ["search", searchId], queryFn: () => api.searches.get(searchId) });
  const results = useQuery({
    queryKey: ["results", searchId, params],
    queryFn: () => api.searches.results(searchId, params),
  });

  const negotiateMutation = useMutation({
    mutationFn: () => api.listings.bulkNegotiate(selected, tone),
    onSuccess: (data) => {
      setMessages(data);
      toast(`${data.length} negotiation message(s) generated`, "success");
    },
    onError: (error) => toast(error instanceof Error ? error.message : "Generation failed", "error"),
  });

  function toggle(id: number) {
    setSelected((current) => (current.includes(id) ? current.filter((value) => value !== id) : [...current, id]));
  }

  const runNow = useMutation({
    mutationFn: () => api.searches.runAsync(searchId),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["live"] });
      if (result.already_running) toast("This search is already scanning", "info");
      else toast("Scan started. Progress shows here and in the sidebar.", "info");
    },
    onError: (error) => toast(error instanceof Error ? error.message : "Could not start the scan", "error"),
  });

  const alertNow = useMutation({
    mutationFn: () => api.searches.alertNow(searchId),
    onSuccess: (r) => {
      queryClient.invalidateQueries({ queryKey: ["results"] });
      queryClient.invalidateQueries({ queryKey: ["enrich", searchId] });
      if (r.sent) toast(`${r.sent} deal${r.sent === 1 ? "" : "s"} sent to Telegram`, "success");
      else if (r.quiet) toast("Quiet hours: the deals will be sent after quiet hours end", "info");
      else if (!r.fresh) toast("No fresh ads left to send (all older than the max age, gone, or already sent)", "info");
      else toast(`Checked ${r.fresh} fresh ads: none rated “${r.min_verdict}” or better. Lower the minimum verdict in Settings to get more.`, "info");
    },
    onError: (error) => toast(error instanceof Error ? error.message : "Could not send deals", "error"),
  });

  function editFilters(update: (current: typeof filters) => typeof filters) {
    setPreset(null);
    setFilters(update);
  }

  function applyPreset(next: Preset) {
    setPreset(next);
    setSort("newest");
    setFilters((current) => ({
      ...current,
      good_only: next === "hot",
      max_age_hours: next === "all" ? "" : "336",
      relevant_only: next !== "all",
      show_gone: next === "all",
      new_only: false,
      min_price: "", max_price: "", min_ram: "", min_storage: "", brand: "", condition: "", city: "",
      hide_missing_specs: false,
    }));
  }

  const items = results.data?.items || [];
  // AI only runs from these two views, on the first 5 ads that still need it (never during scans).
  const enrich = useEnrich(searchId, preset === "hot" || preset === "fresh");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-start gap-2">
          <Link to="/searches">
            <Button size="sm" variant="ghost">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-semibold">{search.data?.name || `Search #${searchId}`}</h1>
            <p className="text-xs text-ink-muted">
              {results.data ? `${results.data.total} listings` : "Loading…"}
              {search.data?.last_run_at ? ` · last check ${new Date(search.data.last_run_at + "Z").toLocaleString("en-GB")}` : ""}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <a href={api.searches.exportUrl(searchId)}>
            <Button size="sm" variant="secondary">
              <Download className="h-4 w-4" /> CSV
            </Button>
          </a>
          <Button
            size="sm"
            variant="secondary"
            disabled={alertNow.isPending}
            onClick={() => alertNow.mutate()}
            title="Price and judge the freshest ads, then send the good ones to Telegram"
          >
            <Send className="h-4 w-4" /> {alertNow.isPending ? "Checking deals…" : "Send best deals now"}
          </Button>
          <Button size="sm" variant="primary" disabled={!!scanning} onClick={() => runNow.mutate()}>
            {scanning ? "Scanning…" : "Run now"}
          </Button>
        </div>
      </div>

      {scanning ? (
        <Card>
          <div className="p-3">
            <RunningScan run={scanning} />
          </div>
        </Card>
      ) : null}

      <AiPanel enrich={enrich} />

      <div className="flex flex-wrap items-center gap-2">
        {PRESETS.map((item) => (
          <Button key={item.id} size="sm" variant={preset === item.id ? "primary" : "secondary"} title={item.hint} onClick={() => applyPreset(item.id)}>
            {item.label}
          </Button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <Label htmlFor="sort" className="mb-0">Sort</Label>
          <Select id="sort" value={sort} onChange={(event) => setSort(event.target.value as SortKey)} className="h-8 w-auto py-1 text-xs">
            {SORTS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
          <Button size="sm" variant="secondary" onClick={() => setShowFilters((value) => !value)}>
            <Filter className="h-4 w-4" /> {showFilters ? "Fewer filters" : "More filters"}
          </Button>
        </div>
      </div>

      {showFilters ? (
        <Card>
          <CardHeader title="More filters" subtitle="Applied to the stored ads of this search. Changing one clears the preset" />
          <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label>Price min</Label>
                <Input
                  type="number"
                  value={filters.min_price}
                  onChange={(event) => editFilters((current) => ({ ...current, min_price: event.target.value }))}
                  placeholder="€"
                />
              </div>
              <div>
                <Label>Price max</Label>
                <Input
                  type="number"
                  value={filters.max_price}
                  onChange={(event) => editFilters((current) => ({ ...current, max_price: event.target.value }))}
                  placeholder="€"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label>RAM min</Label>
                <Input
                  type="number"
                  value={filters.min_ram}
                  onChange={(event) => editFilters((current) => ({ ...current, min_ram: event.target.value }))}
                  placeholder="GB"
                />
              </div>
              <div>
                <Label>Disk min</Label>
                <Input
                  type="number"
                  value={filters.min_storage}
                  onChange={(event) => editFilters((current) => ({ ...current, min_storage: event.target.value }))}
                  placeholder="GB"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label>Brand</Label>
                <Input
                  value={filters.brand}
                  onChange={(event) => editFilters((current) => ({ ...current, brand: event.target.value }))}
                  placeholder="Lenovo"
                />
              </div>
              <div>
                <Label>City</Label>
                <Input
                  value={filters.city}
                  onChange={(event) => editFilters((current) => ({ ...current, city: event.target.value }))}
                  placeholder="Paris"
                />
              </div>
            </div>
            <div>
              <Label>Condition</Label>
              <Select
                value={filters.condition}
                onChange={(event) => editFilters((current) => ({ ...current, condition: event.target.value }))}
              >
                <option value="">Any</option>
                <option value="new">New</option>
                <option value="like_new">Like new</option>
                <option value="very_good">Very good</option>
                <option value="good">Good</option>
                <option value="fair">Fair</option>
                <option value="parts">For parts</option>
              </Select>
            </div>
            <label className="flex items-end gap-2 pb-2 text-xs text-ink-label">
              <input
                type="checkbox"
                className="h-4 w-4 accent-primary"
                checked={filters.hide_missing_specs}
                onChange={(event) => editFilters((current) => ({ ...current, hide_missing_specs: event.target.checked }))}
              />
              Hide listings without CPU
            </label>
            <label className="flex items-end gap-2 pb-2 text-xs text-ink-label">
              <input
                type="checkbox"
                className="h-4 w-4 accent-primary"
                checked={filters.good_only}
                onChange={(event) => editFilters((current) => ({ ...current, good_only: event.target.checked }))}
              />
              Good deals only
            </label>
            <label className="flex items-end gap-2 pb-2 text-xs text-ink-label">
              <input
                type="checkbox"
                className="h-4 w-4 accent-primary"
                checked={filters.relevant_only}
                onChange={(event) => editFilters((current) => ({ ...current, relevant_only: event.target.checked }))}
              />
              Only ads matching my search (CPU/GPU/RAM/storage)
            </label>
            <label className="flex items-end gap-2 pb-2 text-xs text-ink-label">
              <input
                type="checkbox"
                className="h-4 w-4 accent-primary"
                checked={filters.show_gone}
                onChange={(event) => editFilters((current) => ({ ...current, show_gone: event.target.checked }))}
              />
              Show sold / gone ads
            </label>
            <div className="flex items-end gap-2">
              <span className="pb-2 text-xs text-ink-label">Max age</span>
              <Select
                value={filters.max_age_hours}
                onChange={(event) => editFilters((current) => ({ ...current, max_age_hours: event.target.value }))}
                className="h-8 w-28 py-1 text-xs"
              >
                <option value="">Any</option>
                <option value="6">6 h</option>
                <option value="24">24 h</option>
                <option value="48">48 h</option>
                <option value="168">7 days</option>
                <option value="336">14 days</option>
              </Select>
            </div>
            <div className="flex items-end gap-2">
              <label className="flex items-end gap-2 pb-2 text-xs text-ink-label">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-primary"
                  checked={filters.new_only}
                  onChange={(event) => editFilters((current) => ({ ...current, new_only: event.target.checked }))}
                />
                New only
              </label>
              <Select
                value={filters.new_within}
                disabled={!filters.new_only}
                onChange={(event) => editFilters((current) => ({ ...current, new_within: event.target.value }))}
                className="h-8 w-32 py-1 text-xs"
              >
                <option value="last_run">Last check</option>
                <option value="24h">Last 24 h</option>
                <option value="7d">Last 7 days</option>
              </Select>
            </div>
          </div>
        </Card>
      ) : null}

      {results.isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-72" />
          ))}
        </div>
      ) : results.isError ? (
        <Card>
          <EmptyState title="Could not load results" description={results.error instanceof Error ? results.error.message : undefined} />
        </Card>
      ) : !items.length ? (
        <Card>
          <EmptyState
            title="No listings for this search"
            description="Run the search now, or import a CSV export from Leboncoin when r.jina.ai is blocked."
            action={<Button onClick={() => api.searches.run(searchId).then(() => results.refetch())}>Run now</Button>}
          />
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((card) => (
            <ListingCard
              key={card.id}
              card={card}
              selectable
              selected={selected.includes(card.id)}
              onToggle={toggle}
            />
          ))}
        </div>
      )}

      {selected.length ? (
        <div className="fixed bottom-16 left-0 right-0 z-30 px-3 lg:bottom-4">
          <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-2 rounded-xl border border-border-control bg-surface/95 p-2 shadow-lg backdrop-blur">
            <span className="px-2 text-xs font-medium">{selected.length} selected</span>
            <Select value={tone} onChange={(event) => setTone(event.target.value as typeof tone)} className="h-8 w-32 py-1 text-xs">
              <option value="friendly">Friendly</option>
              <option value="direct">Direct</option>
              <option value="firm">Firm</option>
            </Select>
            <Button size="sm" variant="primary" onClick={() => negotiateMutation.mutate()} disabled={negotiateMutation.isPending}>
              <MessageSquareText className="h-3.5 w-3.5" />
              {negotiateMutation.isPending ? "Generating…" : "Generate messages"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setSelected([])}>
              <X className="h-3.5 w-3.5" /> Clear
            </Button>
            <span className="ml-auto hidden text-[11px] text-ink-muted sm:block">
              approx. {eur(items.filter((item) => selected.includes(item.id)).reduce((sum, item) => sum + (item.price_eur || 0), 0))}
            </span>
          </div>
        </div>
      ) : null}

      {messages ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-scrim p-0 sm:items-center sm:p-4">
          <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-t-2xl bg-surface p-4 shadow-xl sm:rounded-2xl">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold">Negotiation messages ({messages.length})</h2>
              <Button size="sm" variant="ghost" onClick={() => setMessages(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="space-y-3">
              {messages.map((message) => (
                <div key={message.id} className="rounded-lg border border-border p-3">
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-ink-muted">
                    <span>ask {eur(message.ask_price_eur)}</span>
                    <span>→ offer {eur(message.offer_price_eur)}</span>
                    <span>target {eur(message.target_price_eur)}</span>
                    <span>max {eur(message.max_price_eur)}</span>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="ml-auto"
                      onClick={() => {
                        navigator.clipboard.writeText(message.message_fr);
                        toast("Copied", "success");
                      }}
                    >
                      <Copy className="h-3 w-3" /> Copy
                    </Button>
                  </div>
                  <p className="whitespace-pre-wrap text-sm">{message.message_fr}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
