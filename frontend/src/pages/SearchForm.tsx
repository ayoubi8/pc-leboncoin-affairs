import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Eye, Save } from "lucide-react";
import { api, type SearchInput } from "../lib/api";
import { toast } from "../lib/toast";
import { Button, Card, CardHeader, Input, Label, Select, Skeleton, Switch } from "../components/ui";

const EMPTY: SearchInput = {
  name: "",
  keyword: "pc portable",
  cpu: "",
  cpu_family: "",
  ram_min: null,
  storage_min: null,
  gpu: "",
  screen_min: null,
  screen_max: null,
  price_min: null,
  price_max: null,
  brand: "",
  condition: "",
  location: "",
  shipping_available: false,
  include_missing_specs: true,
  category: "informatique/ordinateurs",
  auto_check_enabled: false,
  interval: "daily",
  notify_telegram: true,
};

function toNumber(value: string): number | null {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export default function SearchForm() {
  const { id } = useParams();
  const editing = Boolean(id);
  const searchId = id ? Number(id) : null;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<SearchInput>(EMPTY);
  const [showPreview, setShowPreview] = useState(false);

  const existing = useQuery({
    queryKey: ["search", searchId],
    queryFn: () => api.searches.get(searchId as number),
    enabled: editing,
  });

  useEffect(() => {
    if (existing.data) {
      const { id: _id, created_at, updated_at, last_run_at, last_run_status, result_count, ...rest } = existing.data;
      void _id;
      void created_at;
      void updated_at;
      void last_run_at;
      void last_run_status;
      void result_count;
      const interval = ["1h", "6h", "12h", "daily"].includes(rest.interval) ? rest.interval : "daily";
      setForm({ ...rest, interval, category: "informatique/ordinateurs", keyword: "pc portable", location: "" });
    }
  }, [existing.data]);

  const preview = useQuery({
    queryKey: ["preview", searchId],
    queryFn: () => api.searches.preview(searchId as number),
    enabled: Boolean(searchId) && showPreview,
  });

  const saveMutation = useMutation({
    mutationFn: (payload: SearchInput) =>
      searchId ? api.searches.update(searchId, payload) : api.searches.create(payload),
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ["searches"] });
      queryClient.invalidateQueries({ queryKey: ["search", saved.id] });
      toast(editing ? "Search updated" : "Search created", "success");
      navigate(editing ? `/searches/${saved.id}/results` : "/searches");
    },
    onError: (error) => toast(error instanceof Error ? error.message : "Save failed", "error"),
  });

  function set<K extends keyof SearchInput>(key: K, value: SearchInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!form.name.trim()) {
      toast("Give the search a name", "error");
      return;
    }
    saveMutation.mutate(form);
  }

  if (editing && existing.isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-96" />
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Link to="/searches">
            <Button type="button" size="sm" variant="ghost">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-semibold">{editing ? "Edit search" : "New search"}</h1>
            <p className="text-xs text-ink-muted">Every field except the name is optional.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {searchId ? (
            <Button type="button" size="sm" variant="secondary" onClick={() => setShowPreview((value) => !value)}>
              <Eye className="h-4 w-4" /> {showPreview ? "Hide queries" : "Preview queries"}
            </Button>
          ) : null}
          <Button type="submit" size="sm" variant="primary" disabled={saveMutation.isPending}>
            <Save className="h-4 w-4" /> {saveMutation.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>

      {showPreview && searchId ? (
        <Card>
          <CardHeader title="Generated queries" subtitle="Exact French text sent to Leboncoin" />
          {preview.isLoading ? (
            <Skeleton className="m-4 h-16" />
          ) : (
            <ul className="divide-y divide-border-subtle">
              {(preview.data?.queries || []).map((query, index) => (
                <li key={index} className="flex items-center justify-between gap-3 px-4 py-2 text-xs">
                  <code className="break-all">{query}</code>
                  <a
                    className="shrink-0 text-link hover:underline"
                    href={preview.data?.leboncoin_urls[index]}
                    target="_blank"
                    rel="noreferrer"
                  >
                    open
                  </a>
                </li>
              ))}
            </ul>
          )}
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Basics" />
        <div className="grid gap-4 p-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="name">Name *</Label>
            <Input id="name" value={form.name} onChange={(event) => set("name", event.target.value)} placeholder="i5 16GB under 500 €" />
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Hardware" subtitle="Matched against extracted specs" />
        <div className="grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <Label htmlFor="cpu">CPU (exact)</Label>
            <Input id="cpu" value={form.cpu} onChange={(event) => set("cpu", event.target.value)} placeholder="i7-11800h" />
          </div>
          <div>
            <Label htmlFor="cpu_family">CPU brand</Label>
            <Select id="cpu_family" value={form.cpu_family} onChange={(event) => set("cpu_family", event.target.value)}>
              <option value="">Any</option>
              <option value="intel">Intel</option>
              <option value="ryzen">Ryzen (AMD)</option>
              <option value="apple">Apple (M chips)</option>
              <option value="snapdragon">Snapdragon (ARM)</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="gpu">GPU</Label>
            <Input id="gpu" value={form.gpu} onChange={(event) => set("gpu", event.target.value)} placeholder="RTX 3060" />
          </div>
          <div>
            <Label htmlFor="ram_min">RAM min (GB)</Label>
            <Input id="ram_min" type="number" min={0} value={form.ram_min ?? ""} onChange={(event) => set("ram_min", toNumber(event.target.value))} />
          </div>
          <div>
            <Label htmlFor="storage_min">Storage min (GB)</Label>
            <Input id="storage_min" type="number" min={0} step={128} value={form.storage_min ?? ""} onChange={(event) => set("storage_min", toNumber(event.target.value))} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label htmlFor="screen_min">Screen min (").</Label>
              <Input id="screen_min" type="number" step={0.1} value={form.screen_min ?? ""} onChange={(event) => set("screen_min", toNumber(event.target.value))} />
            </div>
            <div>
              <Label htmlFor="screen_max">Screen max (")</Label>
              <Input id="screen_max" type="number" step={0.1} value={form.screen_max ?? ""} onChange={(event) => set("screen_max", toNumber(event.target.value))} />
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Price & market" />
        <div className="grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <Label htmlFor="price_min">Price min (€)</Label>
            <Input id="price_min" type="number" min={0} value={form.price_min ?? ""} onChange={(event) => set("price_min", toNumber(event.target.value))} />
          </div>
          <div>
            <Label htmlFor="price_max">Price max (€)</Label>
            <Input id="price_max" type="number" min={0} value={form.price_max ?? ""} onChange={(event) => set("price_max", toNumber(event.target.value))} />
          </div>
          <div>
            <Label htmlFor="brand">Brand</Label>
            <Input id="brand" value={form.brand} onChange={(event) => set("brand", event.target.value)} placeholder="Lenovo" />
          </div>
          <div>
            <Label htmlFor="condition">Condition</Label>
            <Select id="condition" value={form.condition} onChange={(event) => set("condition", event.target.value)}>
              <option value="">Any</option>
              <option value="new">New</option>
              <option value="like_new">Like new</option>
              <option value="very_good">Very good</option>
              <option value="good">Good</option>
              <option value="fair">Fair</option>
              <option value="parts">For parts</option>
            </Select>
          </div>
          <div className="sm:col-span-2 lg:col-span-4 flex flex-wrap gap-6 pt-1">
            <Switch checked={form.shipping_available} onChange={(value) => set("shipping_available", value)} label="Seller ships" />
            <Switch checked={form.include_missing_specs} onChange={(value) => set("include_missing_specs", value)} label="Include listings with missing specs" />
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Automation" subtitle="Runs this search again on the chosen schedule (checked every 5 minutes)" />
        <div className="flex flex-wrap items-center gap-6 p-4">
          <Switch checked={form.auto_check_enabled} onChange={(value) => set("auto_check_enabled", value)} label="Auto-check enabled" />
          <Switch checked={form.notify_telegram} onChange={(value) => set("notify_telegram", value)} label="Send best new deals to Telegram" />
          <div className="w-40">
            <Label htmlFor="interval">Interval</Label>
            <Select id="interval" value={form.interval} onChange={(event) => set("interval", event.target.value)}>
              <option value="1h">Every hour</option>
              <option value="6h">Every 6 hours</option>
              <option value="12h">Every 12 hours</option>
              <option value="daily">Once a day</option>
            </Select>
          </div>
        </div>
      </Card>

      <div className="flex justify-end gap-2">
        <Link to="/searches">
          <Button type="button" variant="secondary">Cancel</Button>
        </Link>
        <Button type="submit" variant="primary" disabled={saveMutation.isPending}>
          <Save className="h-4 w-4" /> {editing ? "Save changes" : "Create search"}
        </Button>
      </div>
    </form>
  );
}
