import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type LiveStatus } from "./api";
import { toast } from "./toast";

function useLiveQuery() {
  return useQuery({
    queryKey: ["live"],
    queryFn: api.ops.live,
    refetchInterval: (q) => ((q.state.data?.running.length ?? 0) > 0 ? 2000 : 5000),
    refetchIntervalInBackground: false,
    retry: false,
  });
}

/** What the backend is doing right now. Fast polling (2 s) while a scan runs, 5 s otherwise.
 *  One shared query, so the sidebar panel, the Live page and the buttons read the same data. */
export function useLive() {
  const query = useLiveQuery();
  return {
    live: query.data,
    updatedAt: query.dataUpdatedAt,
    /** true when the page cannot reach the backend at all */
    offline: query.isError,
    loading: query.isLoading,
  };
}

/** Mount ONCE (in the layout). When a scan that was running disappears, the data behind
 *  every page changed: refresh those queries and tell the user. */
export function useLiveWatcher() {
  const queryClient = useQueryClient();
  const previous = useRef<LiveStatus | null>(null);
  const query = useLiveQuery();

  useEffect(() => {
    const now = query.data;
    const before = previous.current;
    if (now && before) {
      const finished = before.running.filter((r) => !now.running.some((n) => n.run_id === r.run_id));
      if (finished.length) {
        for (const key of ["dashboard", "searches", "results", "actNow", "health", "pipeline"]) {
          queryClient.invalidateQueries({ queryKey: [key] });
        }
        const last = now.last_run;
        if (last && last.status === "success") {
          toast(`Scan finished: ${last.results_total} ads checked, ${last.new_count} new`, "success");
        } else if (last) {
          toast(`Scan ${last.status}. See Live activity for details.`, "error");
        }
      }
    }
    if (now) previous.current = now;
  }, [query.data, queryClient]);
}

export function formatDuration(totalSeconds: number | null | undefined): string {
  if (totalSeconds === null || totalSeconds === undefined) return "—";
  const s = Math.max(0, Math.round(totalSeconds));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${String(s % 60).padStart(2, "0")}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${String(m % 60).padStart(2, "0")}m`;
}

/** Re-render every second so countdowns move between polls. */
export function useTicker(everyMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), everyMs);
    return () => window.clearInterval(id);
  }, [everyMs]);
  return now;
}

/** Seconds left until `dueInS` (measured when the data was fetched) elapses. */
export function remaining(dueInS: number | null | undefined, updatedAt: number, now: number): number | null {
  if (dueInS === null || dueInS === undefined) return null;
  return Math.max(0, dueInS - (now - updatedAt) / 1000);
}
