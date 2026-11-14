import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, BellRing, ListChecks, Plus, Radar, Search, TrendingDown } from "lucide-react";
import { api } from "../lib/api";
import { cn, dateShort, eur, timeAgo } from "../lib/utils";
import { Badge, Button, Card, CardHeader, DealBadge, EmptyState, Skeleton } from "../components/ui";
import ListingCard from "../components/ListingCard";

function Stat({
  label,
  value,
  hint,
  icon: Icon,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</p>
        <Icon className="h-4 w-4 text-zinc-400" />
      </div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
      {hint ? <p className="mt-1 truncate text-xs text-zinc-500 dark:text-zinc-400">{hint}</p> : null}
    </Card>
  );
}

export default function Dashboard() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.dashboard,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-40" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <EmptyState
        title="Could not load the dashboard"
        description={error instanceof Error ? error.message : "Is the backend running on port 8000?"}
        action={<Button onClick={() => window.location.reload()}>Retry</Button>}
      />
    );
  }

  const { kpis, recent_runs, best_deals, alerts } = data;
  const best = kpis.best_deal;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">Dashboard</h1>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Live picture of your Leboncoin laptop hunt and landed costs.
          </p>
        </div>
        <Link to="/searches/new">
          <Button variant="primary" size="sm">
            <Plus className="h-4 w-4" /> New search
          </Button>
        </Link>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Active searches" value={kpis.active_searches} icon={Search} hint="with a run or auto-check" />
        <Stat label="New today" value={kpis.new_today} icon={ListChecks} hint="first seen since midnight" />
        <Stat label="Total listings" value={kpis.total_listings} icon={Radar} hint="deduplicated inventory" />
        <Stat
          label="Best deal"
          value={best ? eur(best.price_eur) : "—"}
          icon={TrendingDown}
          hint={best ? `${best.subject}` : "run a search to see one"}
        />
      </div>

      {alerts.length ? (
        <Card>
          <CardHeader title="Alerts" subtitle="Price drops and failed checks" action={<BellRing className="h-4 w-4 text-zinc-400" />} />
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {alerts.map((alert, index) => (
              <li key={`${alert.type}-${index}`} className="flex items-start justify-between gap-3 px-4 py-2.5 text-sm">
                <div className="min-w-0">
                  <p className="truncate">
                    {alert.type === "price_drop" && alert.listing_id ? (
                      <Link to={`/listings/${alert.listing_id}`} className="hover:underline">
                        {alert.subject}
                      </Link>
                    ) : alert.search_name ? (
                      <Link to={`/searches/${alert.search_id}/results`} className="hover:underline">
                        {alert.search_name}
                      </Link>
                    ) : (
                      "Check failed"
                    )}
                  </p>
                  <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">{alert.message}</p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {alert.type === "price_drop" ? (
                    <Badge className="border-emerald-200 bg-emerald-100 text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-300">
                      −{eur((alert.old_eur || 0) - (alert.new_eur || 0))}
                    </Badge>
                  ) : (
                    <Badge className="border-rose-200 bg-rose-100 text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/15 dark:text-rose-300">
                      {alert.status || "failed"}
                    </Badge>
                  )}
                  <span className="text-[11px] text-zinc-400">{timeAgo(alert.at)}</span>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Best deals"
          subtitle="Highest deal score across every search"
          action={
            <Link to="/searches" className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100">
              All searches <ArrowRight className="h-3 w-3" />
            </Link>
          }
        />
        {best_deals.length ? (
          <div className="grid gap-3 p-3 sm:grid-cols-2 xl:grid-cols-3">
            {best_deals.map((deal) => (
              <ListingCard key={deal.id} card={deal} />
            ))}
          </div>
        ) : (
          <EmptyState
            title="No analyzed deals yet"
            description="Create a search, run it, and best deals will appear here once the market sample builds up."
          />
        )}
      </Card>

      <Card>
        <CardHeader title="Recent runs" subtitle="Manual and scheduled checks share the same pipeline" />
        {recent_runs.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-zinc-500 dark:text-zinc-400">
                <tr className="border-b border-zinc-200 dark:border-zinc-800">
                  <th className="px-4 py-2 font-medium">Search</th>
                  <th className="px-4 py-2 font-medium">Trigger</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 text-right font-medium">New</th>
                  <th className="px-4 py-2 text-right font-medium">Total</th>
                  <th className="px-4 py-2 text-right font-medium">When</th>
                </tr>
              </thead>
              <tbody>
                {recent_runs.map((run) => (
                  <tr key={run.id} className="border-b border-zinc-100 last:border-0 dark:border-zinc-800/60">
                    <td className="max-w-52 truncate px-4 py-2">
                      {run.search_id ? (
                        <Link to={`/searches/${run.search_id}/results`} className="hover:underline">
                          {run.search_name || `Search #${run.search_id}`}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-2 capitalize text-zinc-500 dark:text-zinc-400">{run.trigger}</td>
                    <td className="px-4 py-2">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium capitalize",
                          run.status === "completed"
                            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300"
                            : run.status === "running"
                              ? "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300"
                              : "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300",
                        )}
                        title={run.error || undefined}
                      >
                        {run.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">{run.new_count}</td>
                    <td className="px-4 py-2 text-right">{run.results_total}</td>
                    <td className="px-4 py-2 text-right text-zinc-500 dark:text-zinc-400">
                      {run.started_at ? dateShort(run.started_at) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No runs yet" description="Use Run now on a search, or enable auto-check intervals in Settings." />
        )}
      </Card>
    </div>
  );
}
