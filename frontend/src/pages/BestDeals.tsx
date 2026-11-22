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
          Every ad that has a verdict, ranked by resale profit in Algeria. For what to buy right now, use “Act now” on the
          Dashboard: it only shows fresh ads.
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
          <EmptyState title="No verdicts yet" description="Ads get a verdict automatically once they are priced. If this stays empty, check Live activity for a key problem." />
        </Card>
      )}
    </div>
  );
}
