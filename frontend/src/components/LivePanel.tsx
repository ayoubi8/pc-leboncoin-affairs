import { Link } from "react-router-dom";
import { cn } from "../lib/utils";
import type { LiveRun, LiveStatus } from "../lib/api";
import { formatDuration, remaining, useLive, useTicker } from "../lib/useLive";

type Tone = "ok" | "run" | "bad" | "warn" | "idle";

const TONE_DOT: Record<Tone, string> = {
  ok: "bg-success-ink",
  run: "bg-info-ink animate-pulse",
  bad: "bg-danger-ink",
  warn: "bg-warning-ink",
  idle: "bg-ink-faint",
};

export function Dot({ tone, className }: { tone: Tone; className?: string }) {
  return <span aria-hidden="true" className={cn("inline-block h-2 w-2 shrink-0 rounded-full", TONE_DOT[tone], className)} />;
}

export function ProgressBar({ pct, tone = "primary", label }: { pct: number; tone?: "primary" | "danger"; label?: string }) {
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
      aria-label={label}
      className="h-1.5 w-full overflow-hidden rounded-full bg-surface-muted"
    >
      <div
        className={cn("h-full rounded-full transition-[width] duration-700 ease-out", tone === "danger" ? "bg-danger-ink" : "bg-primary")}
        style={{ width: `${Math.max(2, Math.min(100, pct))}%` }}
      />
    </div>
  );
}

/** One running scan: name, current stage and a bar. Used in the sidebar and on the Live page. */
export function RunningScan({ run, compact = false }: { run: LiveRun; compact?: boolean }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="truncate font-medium">{run.search_name}</span>
        <span className="tabular-nums text-ink-muted">{run.pct}%</span>
      </div>
      <ProgressBar pct={run.pct} label={`Scan progress: ${run.search_name}`} />
      <p className={cn("truncate text-ink-muted", compact ? "text-[11px]" : "text-xs")}>{run.stage_label}</p>
    </div>
  );
}

export function liveSummary(live: LiveStatus | undefined, offline: boolean): { tone: Tone; text: string } {
  if (offline) return { tone: "bad", text: "Backend not reachable" };
  if (!live) return { tone: "idle", text: "Connecting…" };
  if (live.running.length) return { tone: "run", text: `Scanning · ${live.running[0].pct}%` };
  if (!live.ok) return { tone: "bad", text: `${live.problems.length} problem${live.problems.length === 1 ? "" : "s"}` };
  return { tone: "ok", text: "All systems running" };
}

/** Desktop sidebar block. */
export default function LivePanel() {
  const { live, updatedAt, offline } = useLive();
  const now = useTicker();
  const summary = liveSummary(live, offline);
  const nextIn = remaining(live?.next?.due_in_s, updatedAt, now);
  const pollAge = live?.telegram.last_poll_s_ago;

  return (
    <Link
      to="/live"
      className="mt-4 block space-y-2.5 rounded-xl border border-border bg-surface-muted/60 p-3 transition-colors hover:bg-surface-muted"
      aria-label="Open live activity"
    >
      <div className="flex items-center gap-2 text-xs font-semibold">
        <Dot tone={summary.tone} />
        {summary.text}
      </div>

      {offline ? (
        <p className="text-[11px] text-ink-muted">Start the backend (python run.py). Scans only happen while it runs.</p>
      ) : null}

      {live?.running.length ? (
        <div className="space-y-2">
          {live.running.slice(0, 2).map((run) => (
            <RunningScan key={run.run_id} run={run} compact />
          ))}
        </div>
      ) : live ? (
        <div className="space-y-1 text-[11px] text-ink-muted">
          <p>
            {live.auto_enabled && live.next ? (
              <>
                Next scan in <b className="tabular-nums text-ink">{formatDuration(nextIn)}</b>
              </>
            ) : live.auto_enabled ? (
              "No auto searches yet"
            ) : (
              "Auto-checks are off"
            )}
          </p>
          {live.next ? <p className="truncate">{live.next.name}</p> : null}
        </div>
      ) : null}

      {live ? (
        <p className="flex items-center gap-1.5 text-[11px] text-ink-muted">
          <Dot tone={!live.telegram.enabled ? "idle" : live.telegram.last_poll_s_ago !== null && live.telegram.last_poll_s_ago < 30 ? "ok" : "warn"} />
          {!live.telegram.enabled
            ? "Telegram off"
            : pollAge === null || pollAge === undefined
              ? "Telegram starting"
              : `Telegram checked ${pollAge}s ago`}
        </p>
      ) : null}
    </Link>
  );
}

/** Slim status pill for the mobile header. */
export function LivePill() {
  const { live, offline } = useLive();
  const summary = liveSummary(live, offline);
  return (
    <Link to="/live" className="flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-[11px] font-medium text-ink-secondary">
      <Dot tone={summary.tone} />
      {summary.text}
    </Link>
  );
}
