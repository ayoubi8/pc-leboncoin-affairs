import { Link } from "react-router-dom";
import { AlertTriangle, ExternalLink, MapPin, Sparkles } from "lucide-react";
import type { ListingCard as ListingCardType } from "../lib/api";
import { cn, conditionLabel, dateShort, dzd, eur, imageUrl, scoreColor, specsSummary } from "../lib/utils";
import { Badge, DealBadge } from "./ui";

export function ageLabel(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return "";
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))} min ago`;
  if (hours < 48) return `${Math.round(hours)} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

function freshnessTone(score: number | null | undefined): string {
  if (score === null || score === undefined) return "";
  if (score >= 75) return "border-success-border bg-success-bg text-success-soft-ink";
  if (score >= 45) return "border-warning-border bg-warning-bg text-warning-ink";
  return "border-danger-border bg-danger-bg text-danger-ink";
}

export default function ListingCard({
  card,
  selectable = false,
  selected = false,
  onToggle,
}: {
  card: ListingCardType;
  selectable?: boolean;
  selected?: boolean;
  onToggle?: (id: number) => void;
}) {
  const image = imageUrl((card.images || [])[0]);
  const summary = specsSummary(card.specs || {});

  return (
    <div
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-xl border bg-surface transition-shadow hover:shadow-md",
        selected
          ? "border-primary ring-1 ring-primary"
          : "border-border",
      )}
    >
      {selectable ? (
        <label className="absolute left-2 top-2 z-10 flex h-6 w-6 cursor-pointer items-center justify-center rounded-md border border-border-control bg-surface/95">
          <input
            type="checkbox"
            className="h-4 w-4 accent-primary"
            checked={selected}
            onChange={() => onToggle?.(card.id)}
          />
        </label>
      ) : null}

      <Link to={`/listings/${card.id}`} className="block">
        <div className="relative aspect-video overflow-hidden bg-surface-muted">
          {image ? (
            <img
              src={image}
              alt={card.subject}
              loading="lazy"
              referrerPolicy="no-referrer"
              className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-ink-faint">No image</div>
          )}
          <div className="absolute bottom-2 left-2 flex flex-wrap gap-1 rounded-md bg-surface/85 p-0.5 backdrop-blur-sm empty:hidden">
            {card.is_new ? (
              <Badge className="border-success-border bg-success-bg text-success-soft-ink">
                <Sparkles className="h-3 w-3" /> New
              </Badge>
            ) : null}
            {card.condition ? <Badge>{conditionLabel(card.condition)}</Badge> : null}
          </div>
          <div className="absolute right-2 top-2 flex flex-col items-end gap-1 rounded-md bg-surface/85 p-0.5 backdrop-blur-sm empty:hidden">
            {!card.is_active ? <Badge className="border-danger-border bg-danger-bg text-danger-ink">Gone / sold</Badge> : null}
            {card.age_hours !== null && card.is_active ? (
              <Badge className={freshnessTone(card.freshness_score)} >{ageLabel(card.age_hours)}</Badge>
            ) : null}
            {card.ship_ok === "no" ? <Badge className="border-warning-border bg-warning-bg text-warning-ink">Pickup only</Badge> : null}
          </div>
        </div>
      </Link>

      <div className="flex flex-1 flex-col gap-2 p-3">
        <Link to={`/listings/${card.id}`} className="line-clamp-2 text-sm font-medium hover:underline">
          {card.subject}
        </Link>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-lg font-semibold leading-none">{eur(card.price_eur)}</span>
          {card.ai_verdict_label ? <DealBadge label={card.ai_verdict_label} /> : null}
        </div>

        {card.profit_ask_eur !== null && card.profit_ask_eur !== undefined ? (
          <div
            className={cn(
              "rounded-md border px-2 py-1.5 text-xs",
              card.profit_ask_eur > 0 ? "border-success-border bg-success-bg text-success-soft-ink" : "border-danger-border bg-danger-bg text-danger-ink",
            )}
            title="Resale profit if you pay the asking price, after shipping and a resale haircut"
          >
            <b className="text-sm">
              {card.profit_ask_eur >= 0 ? "+" : "−"}
              {eur(Math.abs(card.profit_ask_eur))}
            </b>{" "}
            profit at asking price
            {card.ai_profit_eur !== null && card.ai_profit_eur !== undefined && Math.round(card.ai_profit_eur) !== Math.round(card.profit_ask_eur)
              ? ` · ${eur(card.ai_profit_eur)} after the usual discount`
              : ""}
          </div>
        ) : (
          <p className="rounded-md border border-border-subtle bg-surface-muted px-2 py-1.5 text-xs text-ink-muted" title="No Algerian price yet, so profit cannot be calculated">
            Not priced yet
          </p>
        )}

        {card.screen_skip ? (
          <p className="flex items-center gap-1 text-[11px] text-danger-ink">
            <AlertTriangle className="h-3 w-3" /> {card.screen_skip}
          </p>
        ) : card.risk_flags?.length ? (
          <p className="flex items-start gap-1 text-[11px] text-warning-ink">
            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" /> {card.risk_flags[0]}
          </p>
        ) : null}

        {summary ? <p className="text-xs text-ink-label">{summary}</p> : null}
        {card.ai_description ? <p className="line-clamp-3 text-[11px] italic text-ink-muted" title="Written by the spec model">{card.ai_description}</p> : null}

        {card.pipeline_status ? (
          <p className="text-[11px] font-medium capitalize text-info-ink">In pipeline: {card.pipeline_status}</p>
        ) : null}

        <details className="group/more text-[11px]">
          <summary className="cursor-pointer select-none text-ink-muted hover:text-ink">More numbers</summary>
          <dl className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-1 text-ink-muted">
            {card.market_median_eur ? (
              <>
                <dt>France median</dt>
                <dd className="text-right text-ink">{eur(card.market_median_eur)}</dd>
              </>
            ) : null}
            {card.dz_price_median_dzd ? (
              <>
                <dt>Algeria price</dt>
                <dd className="text-right text-ink">{dzd(card.dz_price_median_dzd)}</dd>
                <dt>Landed in Algeria</dt>
                <dd className="text-right text-ink">
                  {dzd(card.dz_landed_dzd)}
                  {card.dz_saving_pct !== null && card.dz_saving_pct !== undefined
                    ? ` (${card.dz_saving_pct >= 0 ? "−" : "+"}${Math.abs(Math.round(card.dz_saving_pct))}%)`
                    : ""}
                </dd>
              </>
            ) : null}
            <dt>Spec match</dt>
            <dd className={cn("text-right font-medium", scoreColor(card.match_score))}>{card.match_score ?? "—"}</dd>
            <dt>Cost score</dt>
            <dd className={cn("text-right font-medium", scoreColor(card.acquisition_score))}>{card.acquisition_score ?? "—"}</dd>
          </dl>
        </details>

        <div className="mt-auto flex items-center justify-between border-t border-border-subtle pt-2 text-[11px] text-ink-muted">
          <span className="flex items-center gap-1">
            <MapPin className="h-3 w-3" />
            {card.city || "—"}
            <span className="text-ink-faint" title="Date published on Leboncoin">
              · {dateShort(card.first_publication_date || card.found_at)}
            </span>
          </span>
          <a
            href={card.url}
            target="_blank"
            rel="noreferrer"
            onClick={(event) => event.stopPropagation()}
            className="flex items-center gap-1 hover:text-ink"
          >
            <ExternalLink className="h-3 w-3" /> Open ad
          </a>
        </div>
      </div>
    </div>
  );
}
