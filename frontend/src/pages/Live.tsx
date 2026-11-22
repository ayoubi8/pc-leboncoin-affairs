import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { api, type LiveRun } from "../lib/api";
import { cn, timeAgo } from "../lib/utils";
import { toast } from "../lib/toast";
import { formatDuration, remaining, useLive, useTicker } from "../lib/useLive";
import { Button, Card, CardHeader, EmptyState, Skeleton } from "../components/ui";
import { Dot, ProgressBar } from "../components/LivePanel";

const STEPS: { stage: string; label: string }[] = [
  { stage: "fetching", label: "Fetch pages" },
  { stage: "saving", label: "Save ads" },
  { stage: "pricing", label: "Price & judge" },
  { stage: "alerting", label: "Alert" },
];

function ScanCard({ run }: { run: LiveRun }) {
  const current = STEPS.findIndex((s) => s.stage === run.stage);
  return (
    <div className="space-y-3 rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold">{run.search_name}</p>
          <p className="text-xs text-ink-muted">
            {run.trigger === "manual" ? "Started by you" : "Scheduled"} · running for {formatDuration(run.elapsed_s)}
          </p>
        </div>
        <span className="text-lg font-semibold tabular-nums">{run.pct}%</span>
      </div>
      <ProgressBar pct={run.pct} label={`Scan progress: ${run.search_name}`} />
      <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {STEPS.map((step, index) => {
          const done = current > index;
          const active = current === index;
          return (
            <li
              key={step.stage}
              className={cn(
                "flex items-center gap-2 rounded-md border px-2 py-1.5 text-xs",
                active ? "border-info-border bg-info-bg text-info-ink" : done ? "border-success-border bg-success-bg text-success-soft-ink" : "border-border text-ink-muted",
              )}
            >
              {done ? <Check className="h-3.5 w-3.5" /> : <Dot tone={active ? "run" : "idle"} />}
              {step.label}
            </li>
          );
        })}
      </ol>
      <p className="text-xs text-ink-muted">
        {run.stage_label}
        {run.ads_found ? ` · ${run.ads_found} ads found so far` : ""}
      </p>
    </div>
  );
}

function CheckRow({ tone, title, detail, action }: { tone: "ok" | "bad" | "warn" | "idle"; title: string; detail: string; action?: React.ReactNode }) {
  return (
    <li className="flex items-start gap-3 px-4 py-3">
      <Dot tone={tone} className="mt-1.5" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-ink-muted">{detail}</p>
      </div>
      {action}
    </li>
  );
}

export default function Live() {
  const queryClient = useQueryClient();
  const { live, updatedAt, offline, loading } = useLive();
  const now = useTicker();

  const run = useMutation({
    mutationFn: (id: number) => api.searches.runAsync(id),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["live"] });
      if (result.already_running) toast("That search is already scanning", "info");
    },
    onError: (error) => toast(error instanceof Error ? error.message : "Could not start the scan", "error"),
  });

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24" />
        <Skeleton className="h-48" />
      </div>
    );
  }

  const key = live?.openrouter;
  const tick = live?.last_tick_s_ago;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Live activity</h1>
        <p className="text-xs text-ink-muted">What the backend is doing right now. This page updates by itself every few seconds.</p>
      </div>

      {offline || !live ? (
        <EmptyState
          title="The backend is not reachable"
          description="Nothing is being scanned. Start it with python run.py in the backend folder (or docker compose up). Scans only happen while it is running."
        />
      ) : (
        <>
          <Card>
            <CardHeader title="Scans" subtitle={live.running.length ? `${live.running.length} running now` : "Nothing running right now"} />
            <div className="space-y-3 p-4">
              {live.running.length ? (
                live.running.map((r) => <ScanCard key={r.run_id} run={r} />)
              ) : (
                <p className="text-sm text-ink-muted">
                  {live.auto_enabled && live.next ? (
                    <>
                      Next scan: <b className="text-ink">{live.next.name}</b> in{" "}
                      <b className="tabular-nums text-ink">{formatDuration(remaining(live.next.due_in_s, updatedAt, now))}</b>
                    </>
                  ) : live.auto_enabled ? (
                    "No search has auto-check turned on."
                  ) : (
                    "Auto-checks are off in Settings, so only manual runs happen."
                  )}
                </p>
              )}
            </div>
            {live.upcoming.length ? (
              <ul className="divide-y divide-border-subtle border-t border-border">
                {live.upcoming.map((u) => {
                  const busy = live.running.some((r) => r.search_id === u.search_id);
                  const left = remaining(u.due_in_s, updatedAt, now);
                  return (
                    <li key={u.search_id} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
                      <Link to={`/searches/${u.search_id}/results`} className="min-w-0 truncate hover:underline">
                        {u.name}
                      </Link>
                      <div className="flex shrink-0 items-center gap-3">
                        <span className="text-xs tabular-nums text-ink-muted">{busy ? "scanning…" : left && left > 0 ? `in ${formatDuration(left)}` : "due now"}</span>
                        <Button size="sm" variant="secondary" disabled={busy || run.isPending} onClick={() => run.mutate(u.search_id)}>
                          Scan now
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : null}
          </Card>

          <Card>
            <CardHeader title="System checks" subtitle="A red dot means something is not working right now" />
            <ul className="divide-y divide-border-subtle">
              <CheckRow tone="ok" title="Backend" detail={`Reachable · up for ${formatDuration(live.uptime_s)}`} />
              <CheckRow
                tone={live.scheduler === "cron" ? "idle" : live.scheduler === "running" && (tick ?? 999) < live.tick_every_s * 2 ? "ok" : "warn"}
                title="Scheduler"
                detail={
                  live.scheduler === "cron"
                    ? "Driven by the external cron on this host"
                    : tick === null || tick === undefined
                      ? "Starting: first check within two minutes"
                      : `Looked for due searches ${formatDuration(tick)} ago (every ${formatDuration(live.tick_every_s)})`
                }
              />
              <CheckRow
                tone={live.problems.some((p) => p.kind.startsWith("scan")) ? "bad" : live.last_run ? "ok" : "idle"}
                title="Leboncoin scanner"
                detail={
                  live.last_run
                    ? `Last scan ${live.last_run.status}: ${live.last_run.results_total} ads, ${live.last_run.new_count} new${live.last_run.finished_at ? ` · ${timeAgo(live.last_run.finished_at + "Z")}` : ""}`
                    : "No scan has run yet"
                }
              />
              <CheckRow
                tone={!live.telegram.enabled ? "idle" : !live.telegram.linked ? "warn" : (live.telegram.last_poll_s_ago ?? 999) < 30 ? "ok" : "warn"}
                title="Telegram"
                detail={
                  !live.telegram.enabled
                    ? "Alerts are off"
                    : !live.telegram.linked
                      ? "Enabled but no chat linked yet"
                      : live.telegram.last_poll_s_ago === null
                        ? "Starting"
                        : `Button taps checked ${live.telegram.last_poll_s_ago}s ago`
                }
                action={!live.telegram.linked && live.telegram.enabled ? <Link to="/settings" className="text-xs underline">Link chat</Link> : undefined}
              />
              <CheckRow
                tone={key === "ok" ? "ok" : key === "unknown" ? "idle" : "bad"}
                title="OpenRouter (Algerian prices and verdicts)"
                detail={
                  key === "ok"
                    ? "Key works"
                    : key === "missing"
                      ? "No key saved: ads cannot be priced"
                      : key === "rejected"
                        ? "Key rejected: ads cannot be priced. Open Settings and press Test key."
                        : "Not tested yet: no price lookup has run"
                }
                action={key === "missing" || key === "rejected" ? <Link to="/settings" className="text-xs underline">Fix in Settings</Link> : undefined}
              />
            </ul>
          </Card>

          <Card>
            <CardHeader title="Recent events" subtitle="Newest first. Cleared when the backend restarts." />
            {live.events.length ? (
              <ul className="divide-y divide-border-subtle">
                {live.events.map((event, index) => (
                  <li key={`${event.at}-${index}`} className="flex items-start gap-3 px-4 py-2 text-sm">
                    <Dot tone={event.level === "error" ? "bad" : event.level === "success" ? "ok" : "idle"} className="mt-1.5" />
                    <span className="min-w-0 flex-1">{event.message}</span>
                    <span className="shrink-0 text-xs text-ink-faint">{timeAgo(event.at)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-4 py-6 text-sm text-ink-muted">No events since the backend started. Scans and alerts will appear here as they happen.</p>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
