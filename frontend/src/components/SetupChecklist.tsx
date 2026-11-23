import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { api } from "../lib/api";
import { cn } from "../lib/utils";
import { useLive } from "../lib/useLive";
import { Button, Card, CardHeader } from "./ui";

/** The three things that must be true before the system can find and judge deals.
 *  Disappears by itself once everything is done. */
export default function SetupChecklist() {
  const { live } = useLive();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings.get });
  const searches = useQuery({ queryKey: ["searches"], queryFn: api.searches.list });

  if (!live || !settings.data || !searches.data) return null;

  const steps = [
    {
      done: live.openrouter === "ok",
      title: "Add a working OpenRouter key",
      why: live.openrouter === "rejected" ? "The saved key is rejected. Without it nothing gets an Algerian price." : "Needed to price ads in Algeria and judge them.",
      to: "/settings",
      action: "Open Settings",
    },
    {
      done: settings.data.telegram_enabled && live.telegram.linked,
      title: "Connect Telegram",
      why: "Alerts and the copy-paste message reach your phone.",
      to: "/settings",
      action: "Open Settings",
    },
    {
      done: searches.data.length > 0,
      title: "Create a search",
      why: "Tell it what to hunt: laptops or graphics cards, and your budget.",
      to: "/searches/new",
      action: "New search",
    },
  ];

  if (steps.every((s) => s.done)) return null;
  const doneCount = steps.filter((s) => s.done).length;

  return (
    <Card>
      <CardHeader title="Finish setting up" subtitle={`${doneCount} of ${steps.length} done. Deals are only found and judged once these are done.`} />
      <ol className="divide-y divide-border-subtle">
        {steps.map((step, index) => (
          <li key={step.title} className="flex flex-wrap items-center gap-3 px-4 py-3">
            <span
              className={cn(
                "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
                step.done ? "border-success-border bg-success-bg text-success-ink" : "border-border text-ink-muted",
              )}
            >
              {step.done ? <Check className="h-3.5 w-3.5" /> : index + 1}
            </span>
            <div className="min-w-0 flex-1 basis-56">
              <p className={cn("text-sm font-medium", step.done && "text-ink-muted line-through")}>{step.title}</p>
              {!step.done ? <p className="text-xs text-ink-muted">{step.why}</p> : null}
            </div>
            {!step.done ? (
              <div className="flex items-center gap-2">
                <Link to={step.to}>
                  <Button size="sm" variant="secondary">
                    {step.action}
                  </Button>
                </Link>
              </div>
            ) : null}
          </li>
        ))}
      </ol>
    </Card>
  );
}
