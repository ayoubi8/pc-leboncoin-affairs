import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type PipelineRow } from "../lib/api";
import { dzd, eur } from "../lib/utils";
import { toast } from "../lib/toast";
import { Button, Card, CardHeader, EmptyState, Input, Skeleton } from "../components/ui";

const STAGES: { key: string; label: string }[] = [
  { key: "contacted", label: "Contacted" },
  { key: "bought", label: "Bought" },
  { key: "shipped", label: "Shipped" },
  { key: "sold", label: "Sold" },
  { key: "skipped", label: "Skipped" },
];

function Row({ row }: { row: PipelineRow }) {
  const queryClient = useQueryClient();
  const [paid, setPaid] = useState(row.bought_price_eur?.toString() ?? "");
  const [sold, setSold] = useState(row.sold_price_dzd?.toString() ?? "");
  const mutation = useMutation({
    mutationFn: (payload: { status: string; bought_price_eur?: number | null; sold_price_dzd?: number | null }) =>
      api.ops.setPipeline(row.id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pipeline"] });
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (error) => toast(error instanceof Error ? error.message : "Update failed", "error"),
  });
  const num = (value: string) => (value.trim() === "" ? null : Number(value));

  return (
    <li className="space-y-2 px-4 py-3 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <Link to={`/listings/${row.id}`} className="min-w-0 flex-1 truncate font-medium hover:underline">
          {row.subject}
        </Link>
        <span className="text-xs text-ink-muted">asked {eur(row.price_eur)}</span>
      </div>
      <div className="flex flex-wrap items-end gap-2 text-xs">
        <label className="w-28">
          <span className="text-ink-muted">Paid (€)</span>
          <Input type="number" value={paid} onChange={(e) => setPaid(e.target.value)} />
        </label>
        <label className="w-36">
          <span className="text-ink-muted">Sold for (DA)</span>
          <Input type="number" value={sold} onChange={(e) => setSold(e.target.value)} />
        </label>
        <Button
          size="sm"
          variant="secondary"
          disabled={mutation.isPending}
          onClick={() =>
            mutation.mutate({
              status: sold ? "sold" : paid ? "bought" : row.pipeline_status,
              bought_price_eur: num(paid),
              sold_price_dzd: num(sold),
            })
          }
        >
          Save
        </Button>
        {STAGES.filter((s) => s.key !== row.pipeline_status).map((s) => (
          <Button key={s.key} size="sm" variant="ghost" onClick={() => mutation.mutate({ status: s.key })}>
            → {s.label}
          </Button>
        ))}
      </div>
      {row.realised ? (
        <p className={row.realised.profit_eur >= 0 ? "text-xs text-success-soft-ink" : "text-xs text-danger-ink"}>
          Realised profit {row.realised.profit_eur >= 0 ? "+" : ""}
          {eur(row.realised.profit_eur)} ({row.realised.margin_pct}%) · cost {eur(row.realised.cost_eur)} · revenue{" "}
          {eur(row.realised.revenue_eur)} ({dzd(row.sold_price_dzd)})
        </p>
      ) : null}
    </li>
  );
}

export default function Pipeline() {
  const { data, isLoading } = useQuery({ queryKey: ["pipeline"], queryFn: api.ops.pipeline });
  if (isLoading || !data) return <Skeleton className="h-64" />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Deal pipeline</h1>
        <p className="text-xs text-ink-muted">
          Mark deals from the Telegram buttons or here. Outcomes teach the app how much sellers really discount and how
          far resale prices fall below asking prices.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-4">
        <Card className="p-4">
          <p className="text-xs text-ink-muted">Deals tracked</p>
          <p className="text-2xl font-semibold">{data.count}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-ink-muted">Sold</p>
          <p className="text-2xl font-semibold">{data.sold}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-ink-muted">Realised profit</p>
          <p className="text-2xl font-semibold">{eur(data.realised_profit_eur)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-ink-muted">Learned</p>
          <p className="text-sm">
            discount {data.learned.avg_discount_pct}% · haircut {data.learned.resale_haircut_pct}%
          </p>
        </Card>
      </div>
      {STAGES.map((stage) => {
        const rows = data.rows.filter((r) => r.pipeline_status === stage.key);
        if (!rows.length) return null;
        return (
          <Card key={stage.key}>
            <CardHeader title={`${stage.label} (${rows.length})`} />
            <ul className="divide-y divide-border-subtle">
              {rows.map((row) => (
                <Row key={row.id} row={row} />
              ))}
            </ul>
          </Card>
        );
      })}
      {!data.count ? (
        <EmptyState
          title="Nothing tracked yet"
          description="Press Contacted / Bought / Skip under a Telegram alert, or set a status on a listing page."
        />
      ) : null}
    </div>
  );
}
