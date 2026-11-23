import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Calculator,
  Sparkles,
  Copy,
  ExternalLink,
  MessageSquareText,
  Truck,
} from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type LandedCost, type QuoteResponse } from "../lib/api";
import { cn, conditionLabel, dateShort, dzd, eur, imageUrl, scoreColor, specsSummary } from "../lib/utils";
import { toast } from "../lib/toast";
import { Badge, Button, Card, CardHeader, DealBadge, Input, Label, ScoreRing, Select, Skeleton, Textarea } from "../components/ui";

const VERDICT_STYLE: Record<string, string> = {
  great: "border-success-border bg-success-bg text-success-ink",
  good: "border-success-border bg-success-bg text-success-ink",
  fair: "border-warning-border bg-warning-bg text-warning-ink",
  skip: "border-border-control bg-surface-muted text-ink-label",
};

function confidenceBadge(level?: string) {
  if (!level) return null;
  const style =
    level === "high"
      ? "border-success-border bg-success-bg text-success-ink"
      : level === "medium"
        ? "border-warning-border bg-warning-bg text-warning-ink"
        : "border-border-control bg-surface-muted text-ink-label";
  return <Badge className={style}>{level}</Badge>;
}

function CostTable({ cost, title }: { cost: LandedCost; title: string }) {
  return (
    <Card>
      <CardHeader title={title} subtitle={`Parallel rate ${cost.parallel_rate} DZD/€`} action={<Truck className="h-4 w-4 text-ink-faint" />} />
      <div className="divide-y divide-border-subtle text-sm">
        {cost.breakdown.map((row) => (
          <div key={row.key} className="flex items-center justify-between px-4 py-2">
            <span className="text-ink-label">{row.label}</span>
            <span className="text-right">
              <span className="font-medium">{eur(row.eur, 2)}</span>
              <span className="ml-2 text-xs text-ink-faint">{dzd(row.dzd)}</span>
            </span>
          </div>
        ))}
        <div className="flex items-center justify-between bg-surface-sunken px-4 py-3">
          <span className="font-semibold">Landed total</span>
          <span className="text-right">
            <span className="text-base font-semibold">{eur(cost.total_eur, 2)}</span>
            <span className="ml-2 text-xs text-ink-muted">{dzd(cost.total_dzd)}</span>
          </span>
        </div>
      </div>
    </Card>
  );
}

export default function ListingDetail() {
  const { id } = useParams();
  const listingId = Number(id);
  const queryClient = useQueryClient();
  const { data: listing, isLoading, isError, error } = useQuery({
    queryKey: ["listing", listingId],
    queryFn: () => api.listings.get(listingId),
  });

  const [activeImage, setActiveImage] = useState(0);
  const [offerPrice, setOfferPrice] = useState("");
  const [weight, setWeight] = useState("");
  const [kind, setKind] = useState<"laptop" | "gpu" | "custom">("laptop");
  const [box, setBox] = useState({ l: "", w: "", h: "" });
  const [quote, setQuote] = useState<QuoteResponse | null>(null);
  const [tone, setTone] = useState<"friendly" | "direct" | "firm">("friendly");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (listing) {
      setOfferPrice(String(listing.price_eur ?? ""));
      setKind(listing.specs?.gpu && !listing.specs?.cpu ? "gpu" : "laptop");
    }
  }, [listing]);

  const dzMutation = useMutation({
    mutationFn: () => api.listings.refreshDz(listingId),
    onSuccess: (data) => {
      queryClient.setQueryData(["listing", listingId], data);
      if (data.dz_price_median_dzd) toast("Algerian price updated", "success");
      else toast(data.dz_error || "No Algerian price found", "error");
    },
    onError: (err: Error) => toast(err.message, "error"),
  });

  const [myPrice, setMyPrice] = useState("");
  const refreshListing = () => queryClient.invalidateQueries({ queryKey: ["listing", listingId] });
  const recheckMutation = useMutation({
    mutationFn: () => api.ops.recheck(listingId),
    onSuccess: (result) => {
      if (result.state === "gone") toast("This ad is gone (sold or removed)", "error");
      else if (result.state === "active") toast("Still online", "success");
      else toast("Could not verify (Leboncoin may be blocking the check)", "error");
      refreshListing();
    },
    onError: (err: Error) => toast(err.message, "error"),
  });
  const myPriceMutation = useMutation({
    mutationFn: () => api.ops.setMyPrice(listingId, Number(myPrice)),
    onSuccess: () => {
      toast("Saved. This price now applies to every similar ad.", "success");
      setMyPrice("");
      refreshListing();
      queryClient.invalidateQueries({ queryKey: ["price-book"] });
    },
    onError: (err: Error) => toast(err.message, "error"),
  });
  const pipelineMutation = useMutation({
    mutationFn: (status: string) => api.ops.setPipeline(listingId, { status }),
    onSuccess: () => {
      refreshListing();
      queryClient.invalidateQueries({ queryKey: ["pipeline"] });
    },
    onError: (err: Error) => toast(err.message, "error"),
  });

  // Ask Gemini automatically the first time an ad without an Algerian price is opened.
  const autoAsked = useRef<number | null>(null);
  useEffect(() => {
    if (listing && !listing.dz_price_median_dzd && !listing.dz_error && autoAsked.current !== listing.id) {
      autoAsked.current = listing.id;
      dzMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listing]);

  const verdictMutation = useMutation({
    mutationFn: () => api.listings.verdict(listingId, offerPrice ? Number(offerPrice) : null),
    onSuccess: (data) => {
      queryClient.setQueryData(["listing", listingId], data);
      queryClient.invalidateQueries({ queryKey: ["best-deals"] });
    },
    onError: (err: Error) => toast(err.message, "error"),
  });

  const quoteMutation = useMutation({
    mutationFn: () => {
      const dims = [box.l, box.w, box.h].map((value) => Number(value));
      return api.listings.quote(listingId, {
        offer_price_eur: offerPrice ? Number(offerPrice) : null,
        weight_kg: weight ? Number(weight) : null,
        kind,
        package_cm: dims.every((value) => Number.isFinite(value) && value > 0) ? dims : null,
      });
    },
    onSuccess: setQuote,
    onError: (mutationError) =>
      toast(mutationError instanceof Error ? mutationError.message : "Quote failed", "error"),
  });

  const negotiationMutation = useMutation({
    mutationFn: () =>
      api.listings.negotiate(listingId, {
        tone,
        offer_price_eur: offerPrice ? Number(offerPrice) : null,
        custom_note: note,
      }),
    onSuccess: (data) => {
      setMessage(data.message_fr);
      toast("Message generated", "success");
    },
    onError: (mutationError) =>
      toast(mutationError instanceof Error ? mutationError.message : "Generation failed", "error"),
  });

  const images = useMemo(() => (listing?.images || []).map(imageUrl).filter(Boolean) as string[], [listing]);
  const cost = quote?.landed_cost || listing?.landed_cost;

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-56" />
        <Skeleton className="h-64" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  if (isError || !listing) {
    return (
      <Card>
        <div className="p-8 text-center text-sm">
          Could not load this listing. {error instanceof Error ? error.message : ""}
        </div>
      </Card>
    );
  }

  const specs = listing.specs || {};

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
            <h1 className="max-w-2xl text-lg font-semibold leading-snug">{listing.subject}</h1>
            <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-muted">
              <span className="text-base font-semibold text-ink">{eur(listing.price_eur)}</span>
              <DealBadge label={listing.deal_label} score={listing.deal_score} />
              {listing.city ? <span>{listing.city}</span> : null}
              {specs.condition ? <span>{conditionLabel(specs.condition)}</span> : null}
              <span>{dateShort(listing.first_publication_date || listing.first_seen_at)}</span>
            </p>
          </div>
        </div>
        <a href={listing.url} target="_blank" rel="noreferrer">
          <Button size="sm" variant="primary">
            <ExternalLink className="h-4 w-4" /> Open ad
          </Button>
        </a>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card className="overflow-hidden">
            <div className="aspect-video bg-surface-muted">
              {images[activeImage] ? (
                <img src={images[activeImage]} alt={listing.subject} referrerPolicy="no-referrer" className="h-full w-full object-contain" />
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-ink-faint">No image</div>
              )}
            </div>
            {images.length > 1 ? (
              <div className="flex gap-2 overflow-x-auto p-2">
                {images.map((image, index) => (
                  <button
                    key={`${image}-${index}`}
                    type="button"
                    onClick={() => setActiveImage(index)}
                    className={cn(
                      "h-14 w-20 shrink-0 overflow-hidden rounded-md border",
                      index === activeImage ? "border-primary" : "border-transparent",
                    )}
                  >
                    <img src={image} alt="" referrerPolicy="no-referrer" className="h-full w-full object-cover" />
                  </button>
                ))}
              </div>
            ) : null}
          </Card>

          <Card>
            <CardHeader title="Extracted specs" subtitle={specsSummary(specs) || "No specs detected yet"} />
            <div className="grid grid-cols-2 gap-px bg-surface-muted text-sm sm:grid-cols-3">
              {[
                ["CPU", specs.cpu, listing.spec_confidence.cpu],
                ["CPU family", specs.cpu_family, listing.spec_confidence.cpu],
                ["RAM", specs.ram_gb ? `${specs.ram_gb} GB` : null, listing.spec_confidence.ram_gb],
                ["Storage", specs.storage_gb ? `${specs.storage_gb} GB` : null, listing.spec_confidence.storage_gb],
                ["GPU", specs.gpu, listing.spec_confidence.gpu],
                ["Screen", specs.screen_inches ? `${specs.screen_inches}"` : null, listing.spec_confidence.screen_inches],
                ["Brand", specs.brand || listing.brand, listing.spec_confidence.brand],
                ["Condition", conditionLabel(specs.condition || listing.condition), listing.spec_confidence.condition],
                ["Model key", listing.model_key, null],
              ].map(([label, value, confidence]) => (
                <div key={String(label)} className="bg-surface p-3">
                  <div className="flex items-center justify-between gap-1">
                    <p className="text-[11px] uppercase tracking-wide text-ink-faint">{label}</p>
                    {confidenceBadge(confidence as string)}
                  </div>
                  <p className="mt-1 truncate text-sm font-medium">{value ? String(value) : "—"}</p>
                </div>
              ))}
            </div>
            {listing.ai_description || Object.keys(listing.spec_notes?.evidence || {}).length ? (
              <div className="space-y-2 border-t border-border-subtle p-4 text-sm">
                {listing.ai_description ? <p className="text-ink-strong">{listing.ai_description}</p> : null}
                {Object.keys(listing.spec_notes?.evidence || {}).length ? (
                  <ul className="space-y-0.5 text-xs text-ink-muted">
                    {Object.entries(listing.spec_notes.evidence || {}).map(([field, why]) => (
                      <li key={field}>
                        <b className="text-ink-label">{field}</b>: {why}
                      </li>
                    ))}
                  </ul>
                ) : null}
                <p className="text-[11px] text-ink-faint">
                  Filled by {listing.spec_notes?.model || "the spec model"}
                  {listing.spec_notes?.filled?.length ? ` · set ${listing.spec_notes.filled.join(", ")}` : ""}
                </p>
              </div>
            ) : null}
          </Card>

          <Card>
            <CardHeader title="Description" subtitle={listing.is_pro ? "Pro seller" : "Private seller"} />
            <p className="whitespace-pre-wrap p-4 text-sm text-ink-strong">{listing.description || "No description."}</p>
          </Card>

          {listing.price_history.length > 1 ? (
            <Card>
              <CardHeader title="Price history" subtitle="Every observed price from your runs" />
              <div className="h-48 p-3">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={listing.price_history.map((point) => ({ date: dateShort(point.observed_at), price: point.price_eur }))}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} width={45} />
                    <Tooltip formatter={(value: number) => eur(value)} />
                    <Line type="monotone" dataKey="price" className="chart-line" stroke="#0ea5e9" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>
          ) : null}
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader
              title="Is it still for sale?"
              subtitle={
                listing.gone_at
                  ? "Marked gone / sold"
                  : listing.freshness_score !== null
                    ? `Freshness ${Math.round(listing.freshness_score)}/100`
                    : "Not scored yet"
              }
              action={
                <Button size="sm" onClick={() => recheckMutation.mutate()} disabled={recheckMutation.isPending}>
                  {recheckMutation.isPending ? "Checking…" : "Check now"}
                </Button>
              }
            />
            <div className="space-y-2 p-4 text-xs">
              <p>
                Shipping:{" "}
                <strong>
                  {listing.ship_ok === "yes" ? "ships" : listing.ship_ok === "no" ? "pickup only" : "not stated"}
                </strong>
                {listing.repost_count ? ` · reposted ${listing.repost_count}x` : ""}
              </p>
              {listing.screen_skip ? <p className="text-danger-ink">Rejected: {listing.screen_skip}</p> : null}
              {listing.risk_flags?.length ? <p className="text-warning-ink">⚠ {listing.risk_flags.join(" · ")}</p> : null}
              <div className="flex flex-wrap items-center gap-1 pt-1">
                <span className="mr-1 text-ink-muted">Pipeline:</span>
                {["contacted", "bought", "shipped", "sold", "skipped"].map((status) => (
                  <Button
                    key={status}
                    size="sm"
                    variant={listing.pipeline_status === status ? "primary" : "secondary"}
                    disabled={pipelineMutation.isPending}
                    onClick={() => pipelineMutation.mutate(listing.pipeline_status === status ? "" : status)}
                  >
                    {status}
                  </Button>
                ))}
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader
              title="Market value"
              subtitle={listing.dz_query || "Price in Algeria vs landed cost"}
              action={
                <Button size="sm" onClick={() => dzMutation.mutate()} disabled={dzMutation.isPending}>
                  {dzMutation.isPending ? "Searching…" : listing.dz_price_median_dzd ? "Refresh" : "Search price"}
                </Button>
              }
            />
            <div className="p-4">
              {listing.dz_price_median_dzd ? (
                <>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div>
                      <p className="text-[11px] uppercase text-ink-faint">Low</p>
                      <p className="text-sm font-semibold">{dzd(listing.dz_price_low_dzd)}</p>
                    </div>
                    <div className="rounded-lg bg-surface-sunken py-1">
                      <p className="text-[11px] uppercase text-ink-faint">Median</p>
                      <p className="text-base font-semibold">{dzd(listing.dz_price_median_dzd)}</p>
                    </div>
                    <div>
                      <p className="text-[11px] uppercase text-ink-faint">High</p>
                      <p className="text-sm font-semibold">{dzd(listing.dz_price_high_dzd)}</p>
                    </div>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-sm">
                    <span className="text-ink-muted">Landed in Algeria</span>
                    <span className="font-semibold">{dzd(listing.dz_landed_dzd)}</span>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-sm">
                    <span className="text-ink-muted">
                      {(listing.dz_saving_pct ?? 0) >= 0 ? "Cheaper than local" : "Dearer than local"}
                    </span>
                    <span className="font-semibold">
                      {listing.dz_saving_pct === null ? "—" : `${Math.abs(listing.dz_saving_pct).toFixed(1)}%`}
                    </span>
                  </div>
                  <div className="mt-3 flex items-center justify-between">
                    {confidenceBadge(listing.dz_confidence || "none")}
                  </div>
                  {listing.dz_sources?.length ? (
                    <ul className="mt-2 space-y-0.5 text-xs">
                      {listing.dz_sources.slice(0, 4).map((source) => (
                        <li key={source.url} className="truncate">
                          <a href={source.url} target="_blank" rel="noreferrer" className="text-ink-muted hover:text-ink hover:underline">
                            {source.title || source.url}
                          </a>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </>
              ) : (
                <p className="text-xs text-ink-muted">
                  {listing.dz_error || "No Algerian price yet. Add your OpenRouter key in Settings, then search."}
                </p>
              )}
              <div className="mt-3 flex items-end gap-2 border-t border-border-subtle pt-3">
                <label className="flex-1 text-xs text-ink-muted">
                  I know this price (median, DA) - applies to every similar ad
                  <Input
                    type="number"
                    value={myPrice}
                    onChange={(event) => setMyPrice(event.target.value)}
                    placeholder={listing.dz_price_median_dzd ? String(Math.round(listing.dz_price_median_dzd)) : "e.g. 90000"}
                  />
                </label>
                <Button size="sm" variant="secondary" disabled={!myPrice || myPriceMutation.isPending} onClick={() => myPriceMutation.mutate()}>
                  Save
                </Button>
              </div>
              <div className="mt-3 flex items-center justify-end gap-3 border-t border-border-subtle pt-2 text-xs">
                <span className={cn("font-medium", scoreColor(listing.match_score))}>match {listing.match_score ?? "—"}</span>
                <span className={cn("font-medium", scoreColor(listing.acquisition_score))}>
                  landed {listing.acquisition_score ?? "—"}
                </span>
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader
              title="Honest verdict"
              subtitle="Resale margin in Algeria after negotiation and shipping"
              action={
                <Button size="sm" variant="primary" onClick={() => verdictMutation.mutate()} disabled={verdictMutation.isPending}>
                  <Sparkles className="h-4 w-4" />
                  {verdictMutation.isPending ? "Thinking…" : listing.ai_verdict ? "Regenerate" : "Generate verdict"}
                </Button>
              }
            />
            <div className="p-4 text-sm">
              {listing.ai_verdict ? (
                <>
                  <div className="flex items-center gap-2">
                    <Badge className={VERDICT_STYLE[listing.ai_verdict.verdict]}>{listing.ai_verdict.verdict}</Badge>
                    <span className="font-medium">{listing.ai_verdict.headline}</span>
                  </div>
                  <div className="mt-3 divide-y divide-border-subtle rounded-lg border border-border-subtle text-xs">
                    {[
                      ["Asking price", eur(listing.ai_verdict.numbers.ask_price_eur)],
                      ["Buy price (after negotiation)", `${eur(listing.ai_verdict.numbers.buy_price_eur)} (−${eur(listing.ai_verdict.numbers.negotiation_saving_eur)})`],
                      ["Shipping", eur(listing.ai_verdict.numbers.shipping_eur, 2)],
                      ["Transfer fee", eur(listing.ai_verdict.numbers.transfer_fee_eur, 2)],
                      ["Total cost", `${eur(listing.ai_verdict.numbers.total_cost_eur, 2)} · ${dzd(listing.ai_verdict.numbers.total_cost_dzd)}`],
                      [`Algerian asking price (÷${listing.ai_verdict.numbers.rate})`, `${eur(listing.ai_verdict.numbers.dz_median_eur, 2)} · ${dzd(listing.ai_verdict.numbers.dz_median_dzd)}`],
                      ...(listing.ai_verdict.numbers.dz_net_eur !== undefined
                        ? [[`Realistic sale (−${listing.ai_verdict.numbers.resale_haircut_pct}% haircut)`, eur(listing.ai_verdict.numbers.dz_net_eur, 2)]]
                        : []),
                    ].map(([label, value]) => (
                      <div key={label} className="flex items-center justify-between px-3 py-1.5">
                        <span className="text-ink-muted">{label}</span>
                        <span className="font-medium">{value}</span>
                      </div>
                    ))}
                    <div className="flex items-center justify-between bg-surface-sunken px-3 py-2">
                      <span className="font-semibold">Your profit</span>
                      <span className="text-sm font-semibold">
                        {eur(listing.ai_verdict.numbers.profit_eur, 2)} · {dzd(listing.ai_verdict.numbers.profit_dzd)} ({listing.ai_verdict.numbers.margin_pct}%)
                      </span>
                    </div>
                    {listing.ai_verdict.numbers.profit_ask_eur !== undefined ? (
                      <div className="flex items-center justify-between px-3 py-1.5">
                        <span className="text-ink-muted">Worst case (seller refuses to negotiate)</span>
                        <span className={cn("font-medium", listing.ai_verdict.numbers.profit_ask_eur < 0 && "text-danger-ink")}>
                          {eur(listing.ai_verdict.numbers.profit_ask_eur, 2)} ({listing.ai_verdict.numbers.margin_ask_pct}%)
                        </span>
                      </div>
                    ) : null}
                  </div>
                  <p className="mt-3 text-ink-strong">{listing.ai_verdict.opinion}</p>
                  {listing.ai_verdict.risks?.length ? (
                    <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-ink-muted">
                      {listing.ai_verdict.risks.map((risk) => (
                        <li key={risk}>{risk}</li>
                      ))}
                    </ul>
                  ) : null}
                  <p className="mt-3 text-xs text-ink-muted">
                    Max to pay for a good deal: <span className="font-semibold">{eur(listing.ai_verdict.max_buy_price_eur)}</span>
                  </p>
                  <p className="mt-1 text-[11px] text-ink-faint">
                    {listing.ai_verdict.source === "ai" ? listing.ai_verdict.model : "rule-based (AI unavailable)"} · uses the offer price in the quote box if set
                  </p>
                </>
              ) : (
                <p className="text-xs text-ink-muted">
                  Click Generate to get an honest opinion: buy price after negotiation, shipping, and what it sells for in Algeria.
                </p>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Negotiation plan" subtitle={listing.negotiation.rationale} />
            <div className="grid grid-cols-3 gap-2 p-4 text-center">
              <div>
                <p className="text-[11px] uppercase text-ink-faint">Open</p>
                <p className="text-sm font-semibold">{eur(listing.negotiation.offer_eur)}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase text-ink-faint">Target</p>
                <p className="text-sm font-semibold">{eur(listing.negotiation.target_eur)}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase text-ink-faint">Max</p>
                <p className="text-sm font-semibold">{eur(listing.negotiation.max_eur)}</p>
              </div>
            </div>
            <div className="space-y-2 border-t border-border-subtle p-4">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label>Tone</Label>
                  <Select value={tone} onChange={(event) => setTone(event.target.value as typeof tone)}>
                    <option value="friendly">Friendly</option>
                    <option value="direct">Direct</option>
                    <option value="firm">Firm</option>
                  </Select>
                </div>
                <div>
                  <Label>Your offer (€)</Label>
                  <Input type="number" value={offerPrice} onChange={(event) => setOfferPrice(event.target.value)} />
                </div>
              </div>
              <div>
                <Label>Custom note (optional)</Label>
                <Textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Je peux venir demain à Paris." className="min-h-14" />
              </div>
              <Button className="w-full" variant="primary" onClick={() => negotiationMutation.mutate()} disabled={negotiationMutation.isPending}>
                <MessageSquareText className="h-4 w-4" />
                {negotiationMutation.isPending ? "Writing…" : "Generate French message"}
              </Button>
              {message ? (
                <div className="rounded-lg border border-border-control p-3 text-sm">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-[11px] text-ink-faint">Generated message</span>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        navigator.clipboard.writeText(message);
                        toast("Copied", "success");
                      }}
                    >
                      <Copy className="h-3 w-3" /> Copy
                    </Button>
                  </div>
                  <p className="whitespace-pre-wrap">{message}</p>
                </div>
              ) : null}
            </div>
          </Card>

          {cost ? <CostTable cost={cost} title={quote ? "Landed cost (your quote)" : "Landed cost"} /> : null}

          <Card>
            <CardHeader title="Calculator" subtitle="Recalculate landed cost" action={<Calculator className="h-4 w-4 text-ink-faint" />} />
            <div className="space-y-3 p-4">
              {quote ? (
                <div className="flex items-center gap-3 rounded-lg bg-surface-sunken p-2">
                  <ScoreRing value={quote.deal_score} />
                  <div className="text-xs">
                    <p className="font-medium capitalize">{quote.deal_label || "not rated"}</p>
                    <p className="text-ink-muted">
                      offer {eur(quote.offer_price_eur, 2)} · total {eur(quote.landed_cost.total_eur, 2)}
                    </p>
                  </div>
                </div>
              ) : null}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label>Offer (€)</Label>
                  <Input type="number" value={offerPrice} onChange={(event) => setOfferPrice(event.target.value)} />
                </div>
                <div>
                  <Label>Weight (kg)</Label>
                  <Input type="number" step={0.1} value={weight} onChange={(event) => setWeight(event.target.value)} placeholder="auto" />
                </div>
                <div className="col-span-2">
                  <Label>Item type</Label>
                  <Select value={kind} onChange={(event) => setKind(event.target.value as typeof kind)}>
                    <option value="laptop">Laptop</option>
                    <option value="gpu">GPU</option>
                    <option value="custom">Custom</option>
                  </Select>
                </div>
                <div className="col-span-2 grid grid-cols-3 gap-2">
                  <div>
                    <Label>L (cm)</Label>
                    <Input type="number" value={box.l} onChange={(event) => setBox((current) => ({ ...current, l: event.target.value }))} />
                  </div>
                  <div>
                    <Label>W (cm)</Label>
                    <Input type="number" value={box.w} onChange={(event) => setBox((current) => ({ ...current, w: event.target.value }))} />
                  </div>
                  <div>
                    <Label>H (cm)</Label>
                    <Input type="number" value={box.h} onChange={(event) => setBox((current) => ({ ...current, h: event.target.value }))} />
                  </div>
                </div>
              </div>
              <Button className="w-full" onClick={() => quoteMutation.mutate()} disabled={quoteMutation.isPending}>
                <Calculator className="h-4 w-4" /> {quoteMutation.isPending ? "Calculating…" : "Recalculate"}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
