import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowRight, BellRing, CheckCircle2, ListChecks, Plus, Radar, Search, TrendingDown } from "lucide-react";
import { api } from "../lib/api";
import { cn, dateShort, eur, timeAgo } from "../lib/utils";
import { Badge, Button, Card, CardHeader, DealBadge, EmptyState, Skeleton } from "../components/ui";
import ListingCard from "../components/ListingCard";
import SetupChecklist from "../components/SetupChecklist";
import { formatDuration, remaining, useLive, useTicker } from "../lib/useLive";

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
        <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</p>
        <Icon className="h-4 w-4 text-ink-faint" />
      </div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
      {hint ? <p className="mt-1 truncate text-xs text-ink-muted">{hint}</p> : null}
    </Card>
  );
}

function HealthBanner() {
  const { data } = useQuery({ queryKey: ["health"], queryFn: api.ops.health, refetchInterval: 60_000 });
  if (!data) return null;
  if (data.ok && !data.problems.length) {
    const mins = data.scan.minutes_since_success;
    return (
      <div className="flex items-center gap-2 rounded-lg border border-success-border bg-success-bg px-3 py-2 text-xs text-success-soft-ink">
        <CheckCircle2 className="h-4 w-4" />
        System healthy{mins !== null ? ` · last good scan ${mins < 90 ? `${mins} min` : `${Math.round(mins / 60)} h`} ago` : ""} · Algerian prices {data.dz_lookups_24h.ok}/{data.dz_lookups_24h.total} OK (24 h)
      </div>
    );
  }
  return (
    <div className="space-y-1 rounded-lg border border-danger-border bg-danger-bg px-3 py-2 text-xs text-danger-ink">
      {data.problems.map((problem) => (
        <p key={problem.kind} className="flex items-start gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {problem.message}
        </p>
      ))}
      {data.problems.some((p) => p.kind.startsWith("key_")) ? (
        <p className="pl-6">
          <Link to="/settings" className="underline">Open Settings and press “Test key”</Link>
        </p>
      ) : null}
    </div>
  );
}

function ActNow() {
  const { data, isLoading } = useQuery({ queryKey: ["actNow"], queryFn: () => api.ops.actNow(6), refetchInterval: 30_000 });
  const { live, updatedAt } = useLive();
  const now = useTicker();
  const nextIn = remaining(live?.next?.due_in_s, updatedAt, now);

  return (
    <Card>
      <CardHeader
        title="Act now"
        subtitle={`Fresh (under ${data?.max_age_hours ?? 48} h), still online, profitable at the asking price. Best first.`}
        action={
          <Link to="/deals" className="flex items-center gap-1 text-xs text-ink-muted hover:text-ink">
            All deals <ArrowRight className="h-3 w-3" />
          </Link>
        }
      />
      {isLoading ? (
        <div className="grid gap-3 p-3 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-72" />
          ))}
        </div>
      ) : data?.items.length ? (
        <div className="grid gap-3 p-3 sm:grid-cols-2 xl:grid-cols-3">
          {data.items.map((item) => (
            <ListingCard key={item.id} card={item} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="Nothing worth buying right now"
          description={
            data && data.unpriced_fresh > 0 && live?.openrouter !== "ok"
              ? `${data.unpriced_fresh} fresh ads are waiting for an Algerian price, but the OpenRouter key is not working. Fix it in Settings and they will be priced on the next scan.`
              : data && data.unpriced_fresh > 0
                ? `${data.unpriced_fresh} fresh ads are still being priced. Check back after the next scan.`
                : live?.next
                  ? `New ads appear here as soon as a scan finds them. Next scan in ${formatDuration(nextIn)}.`
                  : "Create a search and turn on auto-check, and new ads will appear here."
          }
          action={
            live?.openrouter !== "ok" && data && data.unpriced_fresh > 0 ? (
              <Link to="/settings">
                <Button variant="primary" size="sm">Fix the key</Button>
              </Link>
            ) : undefined
          }
        />
      )}
    </Card>
  );
}

export default function Dashboard() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.dashboard,
    refetchInterval: 30_000,
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
          <p className="text-xs text-ink-muted">
            What to buy right now, and whether the machine finding it is healthy.
          </p>
        </div>
        <Link to="/searches/new">
          <Button variant="primary" size="sm">
            <Plus className="h-4 w-4" /> New search
          </Button>
        </Link>
      </div>

      <HealthBanner />

      <SetupChecklist />

      <ActNow />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Active searches" value={kpis.active_searches} icon={Search} hint="with a run or auto-check" />
        <Stat label="New today" value={kpis.new_today} icon={ListChecks} hint="first seen since midnight" />
        <Stat label="Total listings" value={kpis.total_listings} icon={Radar} hint="deduplicated inventory" />
        <Stat
          label="Best deal"
          value={best ? eur(best.price_eur) : "—"}
          icon={TrendingDown}
          hint={best ? `${best.subject}` : "none scored yet"}
        />
      </div>

      {alerts.length ? (
        <Card>
          <CardHeader title="Alerts" subtitle="Price drops and failed checks" action={<BellRing className="h-4 w-4 text-ink-faint" />} />
          <ul className="divide-y divide-border-subtle">
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
                  <p className="truncate text-xs text-ink-muted">{alert.message}</p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {alert.type === "price_drop" ? (
                    <Badge className="border-success-border bg-success-bg text-success-ink">
                      −{eur((alert.old_eur || 0) - (alert.new_eur || 0))}
                    </Badge>
                  ) : (
                    <Badge className="border-danger-border bg-danger-bg text-danger-ink">
                      {alert.status || "failed"}
                    </Badge>
                  )}
                  <span className="text-[11px] text-ink-faint">{timeAgo(alert.at)}</span>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Highest scored ads"
          subtitle="Ranked by market score across every search (not the same as profit: see Act now)"
          action={
            <Link to="/searches" className="flex items-center gap-1 text-xs text-ink-muted hover:text-ink">
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
            title="No scored ads yet"
            description="Ads get a score once a search has run and they have been priced."
          />
        )}
      </Card>

      <Card>
        <CardHeader title="Recent runs" subtitle="Manual and scheduled checks share the same pipeline" />
        {recent_runs.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-ink-muted">
                <tr className="border-b border-border">
                  <th className="px-4 py-2 font-medium">Search</th>
                  <th className="px-4 py-2 font-medium">Started by</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 text-right font-medium">New</th>
                  <th className="px-4 py-2 text-right font-medium">Ads seen</th>
                  <th className="px-4 py-2 text-right font-medium">When</th>
                </tr>
              </thead>
              <tbody>
                {recent_runs.map((run) => (
                  <tr key={run.id} className="border-b border-border-subtle last:border-0 dark:border-border-subtle/60">
                    <td className="max-w-52 truncate px-4 py-2">
                      {run.search_id ? (
                        <Link to={`/searches/${run.search_id}/results`} className="hover:underline">
                          {run.search_name || `Search #${run.search_id}`}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-2 text-ink-muted">{run.trigger === "manual" ? "You" : "Schedule"}</td>
                    <td className="px-4 py-2">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium capitalize",
                          run.status === "completed" || run.status === "success"
                            ? "bg-success-bg text-success-ink"
                            : run.status === "running"
                              ? "bg-info-bg text-info-ink"
                              : "bg-danger-bg text-danger-ink",
                        )}
                        title={run.error || undefined}
                      >
                        {run.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">{run.new_count}</td>
                    <td className="px-4 py-2 text-right">{run.results_total}</td>
                    <td className="px-4 py-2 text-right text-ink-muted">
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
