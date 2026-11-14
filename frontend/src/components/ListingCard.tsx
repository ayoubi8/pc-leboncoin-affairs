import { Link } from "react-router-dom";
import { ExternalLink, MapPin, Sparkles } from "lucide-react";
import type { ListingCard as ListingCardType } from "../lib/api";
import { cn, conditionLabel, eur, imageUrl, scoreColor, specsSummary, timeAgo } from "../lib/utils";
import { Badge, DealBadge, ScoreRing } from "./ui";

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
        "group relative flex flex-col overflow-hidden rounded-xl border bg-white transition-shadow hover:shadow-md dark:bg-zinc-900",
        selected
          ? "border-zinc-900 ring-1 ring-zinc-900 dark:border-zinc-100 dark:ring-zinc-100"
          : "border-zinc-200 dark:border-zinc-800",
      )}
    >
      {selectable ? (
        <label className="absolute left-2 top-2 z-10 flex h-6 w-6 cursor-pointer items-center justify-center rounded-md border border-zinc-300 bg-white/95 dark:border-zinc-600 dark:bg-zinc-900/95">
          <input
            type="checkbox"
            className="h-4 w-4 accent-zinc-900 dark:accent-zinc-100"
            checked={selected}
            onChange={() => onToggle?.(card.id)}
          />
        </label>
      ) : null}

      <Link to={`/listings/${card.id}`} className="block">
        <div className="relative aspect-video overflow-hidden bg-zinc-100 dark:bg-zinc-800">
          {image ? (
            <img
              src={image}
              alt={card.subject}
              loading="lazy"
              referrerPolicy="no-referrer"
              className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-zinc-400">No image</div>
          )}
          <div className="absolute bottom-2 left-2 flex flex-wrap gap-1">
            {card.is_new ? (
              <Badge className="border-emerald-200 bg-emerald-100 text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/20 dark:text-emerald-200">
                <Sparkles className="h-3 w-3" /> New
              </Badge>
            ) : null}
            {card.condition ? <Badge>{conditionLabel(card.condition)}</Badge> : null}
          </div>
        </div>
      </Link>

      <div className="flex flex-1 flex-col gap-2 p-3">
        <div className="flex items-start justify-between gap-2">
          <Link to={`/listings/${card.id}`} className="line-clamp-2 text-sm font-medium hover:underline">
            {card.subject}
          </Link>
          <ScoreRing value={card.deal_score} />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-base font-semibold">{eur(card.price_eur)}</span>
          {card.market_median_eur ? (
            <span className="text-xs text-zinc-500 dark:text-zinc-400">median {eur(card.market_median_eur)}</span>
          ) : null}
          <DealBadge label={card.deal_label} />
        </div>

        {summary ? <p className="text-xs text-zinc-600 dark:text-zinc-400">{summary}</p> : null}

        <div className="mt-auto flex items-center justify-between pt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
          <span className="flex items-center gap-1">
            <MapPin className="h-3 w-3" />
            {card.city || "—"}
          </span>
          <span>{timeAgo(card.found_at || card.first_publication_date)}</span>
        </div>

        <div className="flex items-center justify-between border-t border-zinc-100 pt-2 text-[11px] dark:border-zinc-800">
          <span className={cn("font-medium", scoreColor(card.match_score))}>match {card.match_score ?? "—"}</span>
          <span className={cn("font-medium", scoreColor(card.acquisition_score))}>
            landed {card.acquisition_score ?? "—"}
          </span>
          <a
            href={card.url}
            target="_blank"
            rel="noreferrer"
            onClick={(event) => event.stopPropagation()}
            className="flex items-center gap-1 text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
          >
            <ExternalLink className="h-3 w-3" /> ad
          </a>
        </div>
      </div>
    </div>
  );
}
