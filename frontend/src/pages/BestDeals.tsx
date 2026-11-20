import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Card, EmptyState, Skeleton } from "../components/ui";
import ListingCard from "../components/ListingCard";

export default function BestDeals() {
  const { data, isLoading } = useQuery({ queryKey: ["best-deals"], queryFn: api.listings.bestDeals });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Best deals</h1>
        <p className="text-xs text-ink-muted">
          Ads you generated an honest verdict for, ranked by resale profit in Algeria (skips hidden).
        </p>
      </div>
      {isLoading ? (
        <Skeleton className="h-64" />
      ) : data && data.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {data.map((card) => (
            <ListingCard key={card.id} card={card} />
          ))}
        </div>
      ) : (
        <Card>
          <EmptyState title="No verdicts yet" description="Open an ad and press Generate verdict to rank it here." />
        </Card>
      )}
    </div>
  );
}
