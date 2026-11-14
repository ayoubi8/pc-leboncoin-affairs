import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, Trash2 } from "lucide-react";
import { api, type Settings as SettingsType } from "../lib/api";
import { toast } from "../lib/toast";
import { Button, Card, CardHeader, Input, Label, Select, Skeleton, Switch } from "../components/ui";

function NumberField({
  label,
  value,
  onChange,
  step = 1,
  suffix,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  step?: number;
  suffix?: string;
}) {
  return (
    <div>
      <Label>
        {label}
        {suffix ? <span className="ml-1 font-normal text-zinc-400">({suffix})</span> : null}
      </Label>
      <Input type="number" step={step} value={Number.isFinite(value) ? value : 0} onChange={(event) => onChange(Number(event.target.value))} />
    </div>
  );
}

function DimsField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number[];
  onChange: (value: number[]) => void;
}) {
  return (
    <div>
      <Label>{label}</Label>
      <div className="grid grid-cols-3 gap-2">
        {[0, 1, 2].map((index) => (
          <Input
            key={index}
            type="number"
            value={value[index] ?? 0}
            onChange={(event) => {
              const next = [...value];
              next[index] = Number(event.target.value);
              onChange(next);
            }}
          />
        ))}
      </div>
    </div>
  );
}

export default function Settings() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({ queryKey: ["settings"], queryFn: api.settings.get });
  const [form, setForm] = useState<SettingsType | null>(null);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: (payload: SettingsType) => {
      const { id: _id, updated_at: _updatedAt, ...rest } = payload;
      void _id;
      void _updatedAt;
      return api.settings.update(rest);
    },
    onSuccess: (saved) => {
      setForm(saved);
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast("Settings saved", "success");
    },
    onError: (error) => toast(error instanceof Error ? error.message : "Save failed", "error"),
  });

  if (isLoading || !form) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-72" />
      </div>
    );
  }

  if (isError) return <Card><p className="p-6 text-sm">Could not load settings.</p></Card>;

  function set<K extends keyof SettingsType>(key: K, value: SettingsType[K]) {
    setForm((current) => (current ? { ...current, [key]: value } : current));
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (form) saveMutation.mutate(form);
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">Settings</h1>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">Rates, customs, Porsay tariff, and LLM access.</p>
        </div>
        <Button type="submit" variant="primary" size="sm" disabled={saveMutation.isPending}>
          <Save className="h-4 w-4" /> {saveMutation.isPending ? "Saving…" : "Save settings"}
        </Button>
      </div>

      <Card>
        <CardHeader title="Currency" subtitle="Official rate is used for customs valuation; parallel rate for your real cost" />
        <div className="grid gap-4 p-4 sm:grid-cols-3">
          <NumberField label="Official EUR → DZD" value={form.eur_dzd_official} step={0.1} onChange={(value) => set("eur_dzd_official", value)} />
          <NumberField label="Parallel EUR → DZD" value={form.eur_dzd_parallel} step={0.1} onChange={(value) => set("eur_dzd_parallel", value)} />
          <NumberField label="Bank transfer fee" value={form.transfer_fee_eur} step={1} suffix="EUR" onChange={(value) => set("transfer_fee_eur", value)} />
        </div>
      </Card>

      <Card>
        <CardHeader title="Customs" subtitle="Personal exemption and standard regime are both editable" />
        <div className="grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <Label>Default mode</Label>
            <Select value={form.customs_mode} onChange={(event) => set("customs_mode", event.target.value)}>
              <option value="personal">Personal (occasional)</option>
              <option value="standard">Standard (commercial)</option>
            </Select>
          </div>
          <NumberField label="Duty rate" value={form.duty_rate} step={0.01} onChange={(value) => set("duty_rate", value)} />
          <NumberField label="Solidarity rate" value={form.solidarity_rate} step={0.01} onChange={(value) => set("solidarity_rate", value)} />
          <NumberField label="VAT rate" value={form.vat_rate} step={0.01} onChange={(value) => set("vat_rate", value)} />
          <NumberField label="Personal exemption" value={form.personal_exemption_dzd} step={1000} suffix="DZD" onChange={(value) => set("personal_exemption_dzd", value)} />
          <NumberField label="Flat-rate ceiling" value={form.personal_flat_threshold_dzd} step={1000} suffix="DZD" onChange={(value) => set("personal_flat_threshold_dzd", value)} />
          <NumberField label="Flat rate" value={form.personal_flat_rate} step={0.01} onChange={(value) => set("personal_flat_rate", value)} />
          <NumberField label="Fixed customs fee" value={form.customs_fixed_fee_eur} step={1} suffix="EUR" onChange={(value) => set("customs_fixed_fee_eur", value)} />
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Porsay tariff"
          subtitle="Chargeable weight = max(actual, L×W×H / 5000)"
          action={
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => set("porsay_tariff", [...form.porsay_tariff, { up_to_kg: 0, price_eur: 0 }])}
            >
              <Plus className="h-3.5 w-3.5" /> Tier
            </Button>
          }
        />
        <div className="space-y-3 p-4">
          {form.porsay_tariff.map((tier, index) => (
            <div key={index} className="grid grid-cols-[1fr_1fr_auto] items-end gap-2">
              <NumberField
                label={`Up to (kg) #${index + 1}`}
                value={tier.up_to_kg}
                step={0.5}
                onChange={(value) => {
                  const next = [...form.porsay_tariff];
                  next[index] = { ...next[index], up_to_kg: value };
                  set("porsay_tariff", next);
                }}
              />
              <NumberField
                label="Price (EUR)"
                value={tier.price_eur}
                step={1}
                onChange={(value) => {
                  const next = [...form.porsay_tariff];
                  next[index] = { ...next[index], price_eur: value };
                  set("porsay_tariff", next);
                }}
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="mb-0.5 text-rose-600 dark:text-rose-400"
                onClick={() => set("porsay_tariff", form.porsay_tariff.filter((_, position) => position !== index))}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
          <div className="grid gap-4 border-t border-zinc-100 pt-3 dark:border-zinc-800 sm:grid-cols-3">
            <NumberField label="Price per kg over last tier" value={form.porsay_per_kg_over} step={0.5} suffix="EUR" onChange={(value) => set("porsay_per_kg_over", value)} />
            <NumberField label="Handling fee" value={form.porsay_handling_eur} step={1} suffix="EUR" onChange={(value) => set("porsay_handling_eur", value)} />
            <NumberField label="Packaging weight" value={form.default_packaging_kg} step={0.1} suffix="kg" onChange={(value) => set("default_packaging_kg", value)} />
          </div>
          <div>
            <Label>Porsay receiving address</Label>
            <Input value={form.porsay_address} onChange={(event) => set("porsay_address", event.target.value)} placeholder="Porsay warehouse address" />
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Shipping defaults" subtitle="Fallback weight and box dimensions per item type" />
        <div className="grid gap-4 p-4 sm:grid-cols-2">
          <NumberField label="Laptop weight" value={form.laptop_weight_kg} step={0.1} suffix="kg" onChange={(value) => set("laptop_weight_kg", value)} />
          <NumberField label="GPU weight" value={form.gpu_weight_kg} step={0.1} suffix="kg" onChange={(value) => set("gpu_weight_kg", value)} />
          <DimsField label="Laptop box L/W/H (cm)" value={form.laptop_box_cm} onChange={(value) => set("laptop_box_cm", value)} />
          <DimsField label="GPU box L/W/H (cm)" value={form.gpu_box_cm} onChange={(value) => set("gpu_box_cm", value)} />
        </div>
      </Card>

      <Card>
        <CardHeader title="LLM (optional)" subtitle="Only used for ambiguous extraction and negotiation wording" />
        <div className="grid gap-4 p-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Switch checked={form.llm_enabled} onChange={(value) => set("llm_enabled", value)} label="Enable LLM features" />
          </div>
          <div>
            <Label>Model</Label>
            <Input value={form.llm_model} onChange={(event) => set("llm_model", event.target.value)} placeholder="openai/gpt-4o-mini" />
          </div>
          <div>
            <Label>API key</Label>
            <Input
              type="password"
              value={form.llm_api_key}
              onChange={(event) => set("llm_api_key", event.target.value)}
              placeholder="sk-or-v1-…"
            />
            <p className="mt-1 text-[11px] text-zinc-400">Stored in backend/.env / database; leave the masked value to keep it.</p>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Automation" />
        <div className="p-4">
          <Switch checked={form.auto_check_enabled} onChange={(value) => set("auto_check_enabled", value)} label="Allow scheduled auto-checks" />
        </div>
      </Card>

      <div className="flex justify-end">
        <Button type="submit" variant="primary" disabled={saveMutation.isPending}>
          <Save className="h-4 w-4" /> Save settings
        </Button>
      </div>
    </form>
  );
}
