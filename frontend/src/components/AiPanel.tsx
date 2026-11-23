import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CircleAlert, Loader2, Minus, Sparkles } from "lucide-react";
import { api, type EnrichItem, type EnrichStep } from "../lib/api";
import { cn } from "../lib/utils";
import { toast } from "../lib/toast";
import { Button, Card } from "./ui";

const STEP_LABEL: Record<EnrichStep, string> = { specs: "Specs", price: "Algeria price", verdict: "Verdict" };
const STEPS: EnrichStep[] = ["specs", "price", "verdict"];

const REASONS: Record<string, string> = {
  cooldown: "AI already ran for this search in the last 15 minutes.",
  nothing_to_do: "The freshest ads already have their specs, price and verdict.",
  no_key: "No OpenRouter key saved. Add one in Settings to use AI.",
  already_running: "",
};

/**
 * Runs the AI steps for the first 5 ads when a Hot deals / Fresh ads view is open, and follows the progress.
 * `auto` runs once per visit (the server also limits it to one batch per search every 15 minutes).
 */
export function useEnrich(searchId: number, auto: boolean) {
  const queryClient = useQueryClient();
  const status = useQuery({
    queryKey: ["enrich", searchId],
    queryFn: () => api.searches.enrichStatus(searchId),
    enabled: Number.isFinite(searchId),
    refetchInterval: (query) => (query.state.data?.running ? 1500 : false),
  });
  const reason = useRef("");
  const start = useMutation({
    mutationFn: (isAuto: boolean) => api.searches.enrich(searchId, isAuto),
    onSuccess: (result, isAuto) => {
      reason.current = result.reason;
      queryClient.setQueryData(["enrich", searchId], result);
      if (!isAuto && !result.started) toast(REASONS[result.reason] || "Nothing to run", "info");
    },
    onError: (error) => toast(error instanceof Error ? error.message : "Could not start the AI run", "error"),
  });

  const fired = useRef<number | null>(null);
  useEffect(() => {
    if (auto && Number.isFinite(searchId) && fired.current !== searchId) {
      fired.current = searchId;
      start.mutate(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auto, searchId]);

  const running = status.data?.running ?? false;
  const wasRunning = useRef(false);
  useEffect(() => {
    if (wasRunning.current && !running) {
      queryClient.invalidateQueries({ queryKey: ["results"] });
      queryClient.invalidateQueries({ queryKey: ["listing"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
    wasRunning.current = running;
  }, [running, queryClient]);

  return { status: status.data, running, start, lastReason: reason };
}

function StepChip({ name, state, note }: { name: EnrichStep; state: EnrichItem["steps"][EnrichStep]; note?: string }) {
  const tone =
    state === "done"
      ? "text-success-ink"
      : state === "error"
        ? "text-danger-ink"
        : state === "running"
          ? "text-info-ink"
          : "text-ink-faint";
  const Icon = state === "done" ? Check : state === "error" ? CircleAlert : state === "running" ? Loader2 : Minus;
  return (
    <span className={cn("inline-flex items-center gap-1 text-[11px]", tone)} title={note || state}>
      <Icon className={cn("h-3 w-3", state === "running" && "animate-spin")} aria-hidden="true" />
      {STEP_LABEL[name]}
      <span className="sr-only"> {state}</span>
    </span>
  );
}

export default function AiPanel({ enrich }: { enrich: ReturnType<typeof useEnrich> }) {
  const { status, running, start } = enrich;
  const items = status?.items ?? [];
  const reason = enrich.lastReason.current;
  if (!running && items.length === 0) {
    return reason && REASONS[reason] ? (
      <p className="flex items-center gap-2 text-xs text-ink-muted">
        <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> {REASONS[reason]}
        {reason !== "no_key" ? (
          <Button size="sm" variant="ghost" onClick={() => start.mutate(false)} disabled={start.isPending}>
            Run AI now
          </Button>
        ) : null}
      </p>
    ) : null;
  }

  const done = items.filter((item) => item.finished).length;
  const errors = items.flatMap((item) => STEPS.filter((s) => item.steps[s] === "error").map((s) => ({ item, step: s, note: item.notes[s] || "failed" })));

  return (
    <Card>
      <div className="space-y-3 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Sparkles className="h-4 w-4 text-primary" aria-hidden="true" />
            {running ? `Pricing ${items.length} products (${done}/${items.length})` : `Finished ${done}/${items.length}`}
          </div>
          {!running ? (
            <Button size="sm" variant="secondary" onClick={() => start.mutate(false)} disabled={start.isPending}>
              Run full AI on the next ads
            </Button>
          ) : null}
        </div>
        {status?.models ? (
          <p className="text-[11px] text-ink-faint">
            Specs: {status.models.specs} · Price: {status.models.price} · Verdict: {status.models.verdict}
          </p>
        ) : null}
        <ul className="space-y-1.5">
          {items.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
              <span className="min-w-0 flex-1 truncate text-xs">{item.subject}</span>
              <span className="flex items-center gap-3">
                {STEPS.map((step) => (
                  <StepChip key={step} name={step} state={item.steps[step]} note={item.notes[step]} />
                ))}
              </span>
            </li>
          ))}
        </ul>
        {errors.length ? (
          <ul className="space-y-1 rounded-md bg-danger-bg p-2 text-[11px] text-danger-ink">
            {errors.slice(0, 4).map(({ item, step, note }) => (
              <li key={`${item.id}-${step}`}>
                <b>{STEP_LABEL[step]}</b> ({item.subject.slice(0, 30)}…): {note}
              </li>
            ))}
          </ul>
        ) : null}
        {status?.error ? <p className="text-[11px] text-danger-ink">{status.error}</p> : null}
      </div>
    </Card>
  );
}
