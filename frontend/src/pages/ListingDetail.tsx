import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Calculator,
  Copy,
  ExternalLink,
  MessageSquareText,
  Truck,
} from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type LandedCost, type QuoteResponse } from "../lib/api";
import { cn, conditionLabel, dateShort, dzd, eur, imageUrl, scoreColor, specsSummary, timeAgo } from "../lib/utils";
import { toast } from "../lib/toast";
import { Badge, Button, Card, CardHeader, DealBadge, Input, Label, ScoreRing, Select, Skeleton, Textarea } from "../components/ui";

function confidenceBadge(level?: string) {
  if (!level) return null;
  const style =
    level === "high"
      ? "border-emerald-200 bg-emerald-100 text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-300"
      : level === "medium"
        ? "border-amber-200 bg-amber-100 text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-300"
        : "border-zinc-200 bg-zinc-100 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400";
  return <Badge className={style}>{level}</Badge>;
}

function CostTable({ cost, title }: { cost: LandedCost; title: string }) {
  return (
    <Card>
      <CardHeader title={title} subtitle={`Parallel rate ${cost.parallel_rate} DZD/€`} action={<Truck className="h-4 w-4 text-zinc-400" />} />
      <div className="divide-y divide-zinc-100 text-sm dark:divide-zinc-800">
        {cost.breakdown.map((row) => (
          <div key={row.key} className="flex items-center justify-between px-4 py-2">
            <span className="text-zinc-600 dark:text-zinc-400">{row.label}</span>
            <span className="text-right">
              <span className="font-medium">{eur(row.eur, 2)}</span>
              <span className="ml-2 text-xs text-zinc-400">{dzd(row.dzd)}</span>
            </span>
          </div>
        ))}
        <div className="flex items-center justify-between bg-zinc-50 px-4 py-3 dark:bg-zinc-800/40">
          <span className="font-semibold">Landed total</span>
          <span className="text-right">
            <span className="text-base font-semibold">{eur(cost.total_eur, 2)}</span>
            <span className="ml-2 text-xs text-zinc-500 dark:text-zinc-400">{dzd(cost.total_dzd)}</span>
          </span>
        </div>
      </div>
    </Card>
  );
}

export default function ListingDetail() {
  const { id } = useParams();
  const listingId = Number(id);
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
            <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
              <span className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{eur(listing.price_eur)}</span>
              <DealBadge label={listing.deal_label} score={listing.deal_score} />
              {listing.city ? <span>{listing.city}</span> : null}
              {specs.condition ? <span>{conditionLabel(specs.condition)}</span> : null}
              <span>{timeAgo(listing.first_seen_at)}</span>
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
            <div className="aspect-video bg-zinc-100 dark:bg-zinc-800">
              {images[activeImage] ? (
                <img src={images[activeImage]} alt={listing.subject} referrerPolicy="no-referrer" className="h-full w-full object-contain" />
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-zinc-400">No image</div>
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
                      index === activeImage ? "border-zinc-900 dark:border-zinc-100" : "border-transparent",
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
            <div className="grid grid-cols-2 gap-px bg-zinc-100 text-sm dark:bg-zinc-800 sm:grid-cols-3">
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
                <div key={String(label)} className="bg-white p-3 dark:bg-zinc-900">
                  <div className="flex items-center justify-between gap-1">
                    <p className="text-[11px] uppercase tracking-wide text-zinc-400">{label}</p>
                    {confidenceBadge(confidence as string)}
                  </div>
                  <p className="mt-1 truncate text-sm font-medium">{value ? String(value) : "—"}</p>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader title="Description" subtitle={listing.is_pro ? "Pro seller" : "Private seller"} />
            <p className="whitespace-pre-wrap p-4 text-sm text-zinc-700 dark:text-zinc-300">{listing.description || "No description."}</p>
          </Card>

          {listing.price_history.length > 1 ? (
            <Card>
              <CardHeader title="Price history" subtitle="Every observed price from your runs" />
              <div className="h-48 p-3">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={listing.price_history.map((point) => ({ date: dateShort(point.observed_at), price: point.price_eur }))}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-800" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} width={45} />
                    <Tooltip formatter={(value: number) => eur(value)} />
                    <Line type="monotone" dataKey="price" stroke="#0ea5e9" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>
          ) : null}
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Market value" subtitle={`${listing.market_samples} comparable(s)`} />
            <div className="p-4">
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-[11px] uppercase text-zinc-400">Low</p>
                  <p className="text-sm font-semibold">{eur(listing.market_low_eur)}</p>
                </div>
                <div className="rounded-lg bg-zinc-50 py-1 dark:bg-zinc-800/50">
                  <p className="text-[11px] uppercase text-zinc-400">Median</p>
                  <p className="text-base font-semibold">{eur(listing.market_median_eur)}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase text-zinc-400">High</p>
                  <p className="text-sm font-semibold">{eur(listing.market_high_eur)}</p>
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between">
                {confidenceBadge(listing.market_confidence || "none")}
                <div className="flex items-center gap-3 text-xs">
                  <span className={cn("font-medium", scoreColor(listing.match_score))}>match {listing.match_score ?? "—"}</span>
                  <span className={cn("font-medium", scoreColor(listing.acquisition_score))}>
                    landed {listing.acquisition_score ?? "—"}
                  </span>
                </div>
              </div>
              <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">{listing.market_explanation}</p>
            </div>
          </Card>

          <Card>
            <CardHeader title="Negotiation plan" subtitle={listing.negotiation.rationale} />
            <div className="grid grid-cols-3 gap-2 p-4 text-center">
              <div>
                <p className="text-[11px] uppercase text-zinc-400">Open</p>
                <p className="text-sm font-semibold">{eur(listing.negotiation.offer_eur)}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase text-zinc-400">Target</p>
                <p className="text-sm font-semibold">{eur(listing.negotiation.target_eur)}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase text-zinc-400">Max</p>
                <p className="text-sm font-semibold">{eur(listing.negotiation.max_eur)}</p>
              </div>
            </div>
            <div className="space-y-2 border-t border-zinc-100 p-4 dark:border-zinc-800">
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
                <div className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-700">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-[11px] text-zinc-400">Generated message</span>
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
            <CardHeader title="Calculator" subtitle="Recalculate landed cost" action={<Calculator className="h-4 w-4 text-zinc-400" />} />
            <div className="space-y-3 p-4">
              {quote ? (
                <div className="flex items-center gap-3 rounded-lg bg-zinc-50 p-2 dark:bg-zinc-800/50">
                  <ScoreRing value={quote.deal_score} />
                  <div className="text-xs">
                    <p className="font-medium capitalize">{quote.deal_label || "not rated"}</p>
                    <p className="text-zinc-500 dark:text-zinc-400">
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
