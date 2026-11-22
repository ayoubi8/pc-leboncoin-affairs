import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ChevronDown,
  ChevronUp,
  Download,
  ListFilter,
  Pencil,
  Play,
  Plus,
  Trash2,
  Upload,
} from "lucide-react";
import { api, type Search } from "../lib/api";
import { dateShort, timeAgo } from "../lib/utils";
import { toast } from "../lib/toast";
import { Badge, Button, Card, EmptyState, Skeleton } from "../components/ui";
import { RunningScan } from "../components/LivePanel";
import { useLive } from "../lib/useLive";

function IntervalBadge({ search }: { search: Search }) {
  if (!search.auto_check_enabled) return <Badge>manual</Badge>;
  return (
    <Badge className="border-success-border bg-success-bg text-success-ink">
      auto · {search.interval}
    </Badge>
  );
}

function QueryPreview({ searchId }: { searchId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["preview", searchId],
    queryFn: () => api.searches.preview(searchId),
  });

  if (isLoading) return <Skeleton className="mx-4 mb-4 h-20" />;
  if (!data) return null;

  return (
    <div className="mx-4 mb-4 rounded-lg border border-border bg-surface-inset p-3 text-xs">
      <p className="mb-2 font-medium">Queries ({data.queries.length})</p>
      <ul className="space-y-1">
        {data.queries.map((query, index) => (
          <li key={`${query}-${index}`} className="flex items-start justify-between gap-3">
            <code className="break-all text-[11px] text-ink-strong">{query}</code>
            <a
              href={data.leboncoin_urls[index]}
              target="_blank"
              rel="noreferrer"
              className="shrink-0 text-[11px] text-link hover:underline"
            >
              open
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Searches() {
  const queryClient = useQueryClient();
  const [previewId, setPreviewId] = useState<number | null>(null);
  const fileInputs = useRef<Record<number, HTMLInputElement | null>>({});

  const searches = useQuery({ queryKey: ["searches"], queryFn: api.searches.list });

  const { live } = useLive();
  const runMutation = useMutation({
    mutationFn: (id: number) => api.searches.runAsync(id),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["live"] });
      if (result.already_running) toast("That search is already scanning", "info");
      else toast("Scan started. Progress shows below and in the sidebar.", "info");
    },
    onError: (error) => toast(error instanceof Error ? error.message : "Could not start the scan", "error"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.searches.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["searches"] });
      toast("Search deleted", "success");
    },
    onError: (error) => toast(error instanceof Error ? error.message : "Delete failed", "error"),
  });

  const importMutation = useMutation({
    mutationFn: ({ id, file }: { id: number; file: File }) => api.searches.importCsv(id, file),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["searches"] });
      queryClient.invalidateQueries({ queryKey: ["results"] });
      toast(`Imported ${result.rows_imported}/${result.rows_total} rows (${result.rows_skipped} skipped)`, "success");
    },
    onError: (error) => toast(error instanceof Error ? error.message : "Import failed", "error"),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">Searches</h1>
          <p className="text-xs text-ink-muted">What to hunt. Each search scans Leboncoin on its own schedule and can alert you on Telegram.</p>
        </div>
        <Link to="/searches/new">
          <Button variant="primary" size="sm">
            <Plus className="h-4 w-4" /> New search
          </Button>
        </Link>
      </div>

      {searches.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-28" />
          ))}
        </div>
      ) : searches.isError ? (
        <EmptyState title="Could not load searches" description={searches.error instanceof Error ? searches.error.message : undefined} />
      ) : !searches.data?.length ? (
        <Card>
          <EmptyState
            title="No searches yet"
            description="Create your first search: keyword, CPU family, RAM, price range, and optional auto-check."
            action={
              <Link to="/searches/new">
                <Button variant="primary" size="sm">
                  <Plus className="h-4 w-4" /> Create search
                </Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {searches.data.map((search) => (
            <Card key={search.id}>
              {live?.running.find((r) => r.search_id === search.id) ? (
                <div className="border-b border-border px-4 py-3">
                  <RunningScan run={live.running.find((r) => r.search_id === search.id)!} />
                </div>
              ) : null}
              <div className="flex flex-wrap items-start justify-between gap-3 p-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-sm font-semibold">{search.name}</h2>
                    <IntervalBadge search={search} />
                    {search.last_run_status ? (
                      <Badge className="capitalize">last: {search.last_run_status}</Badge>
                    ) : null}
                    <Badge>{search.result_count} listings</Badge>
                  </div>
                  <p className="mt-1 text-xs text-ink-muted">
                    {[
                      search.keyword,
                      search.cpu || search.cpu_family,
                      search.ram_min ? `${search.ram_min} GB+` : "",
                      search.price_min || search.price_max
                        ? `${search.price_min ?? 0}–${search.price_max ?? "∞"} €`
                        : "",
                      search.location,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "No filters"}
                  </p>
                  <p className="mt-1 text-[11px] text-ink-faint">
                    Last run {timeAgo(search.last_run_at)}
                    {search.created_at ? ` · created ${dateShort(search.created_at)}` : ""}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-1.5">
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => runMutation.mutate(search.id)}
                    disabled={runMutation.isPending || live?.running.some((r) => r.search_id === search.id)}
                  >
                    <Play className="h-3.5 w-3.5" />
                    {live?.running.some((r) => r.search_id === search.id) ? "Scanning…" : "Run now"}
                  </Button>
                  <Link to={`/searches/${search.id}/results`}>
                    <Button size="sm" variant="secondary">
                      <ListFilter className="h-3.5 w-3.5" /> Results
                    </Button>
                  </Link>
                  <Link to={`/searches/${search.id}/edit`}>
                    <Button size="sm" variant="ghost" title="Edit">
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                  </Link>
                  <Button
                    size="sm"
                    variant="ghost"
                    title="Preview queries"
                    onClick={() => setPreviewId(previewId === search.id ? null : search.id)}
                  >
                    {previewId === search.id ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  </Button>
                  <a href={api.searches.exportUrl(search.id)}>
                    <Button size="sm" variant="ghost" title="Export CSV">
                      <Download className="h-3.5 w-3.5" />
                    </Button>
                  </a>
                  <Button
                    size="sm"
                    variant="ghost"
                    title="Import CSV"
                    onClick={() => fileInputs.current[search.id]?.click()}
                    disabled={importMutation.isPending}
                  >
                    <Upload className="h-3.5 w-3.5" />
                  </Button>
                  <input
                    ref={(element) => {
                      fileInputs.current[search.id] = element;
                    }}
                    type="file"
                    accept=".csv,text/csv"
                    className="hidden"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) importMutation.mutate({ id: search.id, file });
                      event.target.value = "";
                    }}
                  />
                  <Button
                    size="sm"
                    variant="ghost"
                    title="Delete"
                    className="text-danger-text hover:bg-danger-ghost-hover"
                    onClick={() => {
                      if (window.confirm(`Delete “${search.name}” and its links? Shared listings are kept.`)) {
                        deleteMutation.mutate(search.id);
                      }
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
              {previewId === search.id ? <QueryPreview searchId={search.id} /> : null}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
