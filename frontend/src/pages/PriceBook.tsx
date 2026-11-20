import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type PriceBookRow } from "../lib/api";
import { dzd } from "../lib/utils";
import { toast } from "../lib/toast";
import { Badge, Button, Card, CardHeader, EmptyState, Input, Skeleton } from "../components/ui";

function Row({ row }: { row: PriceBookRow }) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(row.median_dzd?.toString() ?? "");
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["price-book"] });
  const save = useMutation({
    mutationFn: () => api.ops.editPrice(row.id, Number(value)),
    onSuccess: () => {
      toast("Saved: this price now overrides Gemini", "success");
      refresh();
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Failed", "error"),
  });
  const remove = useMutation({ mutationFn: () => api.ops.deletePrice(row.id), onSuccess: refresh });

  return (
    <li className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm">
      <div className="min-w-0 flex-1">
        <p className="truncate">{row.query || row.key}</p>
        <p className="truncate text-[11px] text-ink-muted">
          {row.key} · {row.ok ? `${dzd(row.low_dzd)} – ${dzd(row.high_dzd)}` : row.note}
        </p>
      </div>
      {row.manual ? (
        <Badge className="border-success-border bg-success-bg text-success-soft-ink">Mine</Badge>
      ) : (
        <Badge>{row.confidence}</Badge>
      )}
      <div className="flex items-center gap-1">
        <Input
          className="h-8 w-28"
          type="number"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="median DA"
        />
        <Button size="sm" variant="secondary" disabled={!value || save.isPending} onClick={() => save.mutate()}>
          Set
        </Button>
        <Button size="sm" variant="ghost" onClick={() => remove.mutate()}>
          Delete
        </Button>
      </div>
    </li>
  );
}

export default function PriceBook() {
  const { data, isLoading } = useQuery({ queryKey: ["price-book"], queryFn: api.ops.priceBook });
  if (isLoading || !data) return <Skeleton className="h-64" />;
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Algerian price book</h1>
        <p className="text-xs text-ink-muted">
          One price per product type (CPU generation · RAM · storage · GPU). You know the Algerian market better than a
          web search: set your own median and it is used for every similar ad and never overwritten.
        </p>
      </div>
      <Card>
        <CardHeader title={`${data.length} product types`} />
        {data.length ? (
          <ul className="divide-y divide-border-subtle">
            {data.map((row) => (
              <Row key={row.id} row={row} />
            ))}
          </ul>
        ) : (
          <EmptyState title="Empty" description="Prices appear here as ads are analysed." />
        )}
      </Card>
    </div>
  );
}
