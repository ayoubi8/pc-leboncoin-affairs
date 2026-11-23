import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { BookOpen, Plus, Save, Trash2 } from "lucide-react";
import { api, type ConnectionTest, type Settings as SettingsType } from "../lib/api";
import { toast } from "../lib/toast";
import { Button, Card, CardHeader, Input, Label, Select, Skeleton, Switch } from "../components/ui";
import { Dot } from "../components/LivePanel";

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
        {suffix ? <span className="ml-1 font-normal text-ink-faint">({suffix})</span> : null}
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


type TestState = { pending: boolean; result?: ConnectionTest };

function ConnectionRow({
  title,
  help,
  state,
  onTest,
  button,
}: {
  title: string;
  help: string;
  state: TestState;
  onTest: () => void;
  button: string;
}) {
  const result = state.result;
  return (
    <li className="space-y-2 px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <Dot tone={state.pending ? "run" : result ? (result.ok ? "ok" : "bad") : "idle"} />
        <div className="min-w-0 flex-1 basis-60">
          <p className="text-sm font-medium">{title}</p>
          <p className="text-xs text-ink-muted">{state.pending ? "Testing…" : result ? result.message : help}</p>
        </div>
        <Button type="button" size="sm" variant="secondary" disabled={state.pending} onClick={onTest}>
          {button}
        </Button>
      </div>
      {result?.steps?.length ? (
        <ul className="ml-5 space-y-0.5 text-xs">
          {result.steps.map((step) => (
            <li key={step.name} className={step.ok ? "text-success-soft-ink" : "text-danger-ink"}>
              {step.ok ? "✓" : "✗"} {step.name}: <span className="text-ink-muted">{step.detail}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function ConnectionsCard({ unsaved }: { unsaved: boolean }) {
  const [openrouter, setOpenrouter] = useState<TestState>({ pending: false });
  const [telegram, setTelegram] = useState<TestState>({ pending: false });
  const [leboncoin, setLeboncoin] = useState<TestState>({ pending: false });

  async function run(set: (s: TestState) => void, call: () => Promise<ConnectionTest>) {
    set({ pending: true });
    try {
      set({ pending: false, result: await call() });
    } catch (error) {
      set({ pending: false, result: { ok: false, message: error instanceof Error ? error.message : "Test failed" } });
    }
  }

  return (
    <Card>
      <CardHeader
        title="Connections"
        subtitle={unsaved ? "You have unsaved changes: press Save first, tests use the saved values" : "Tested live with the saved values. A red dot means it is not working right now"}
      />
      <ul className="divide-y divide-border-subtle">
        <ConnectionRow
          title="OpenRouter · Algerian prices, verdicts, messages"
          help="Runs the same model calls the app makes."
          state={openrouter}
          button="Test key"
          onTest={() => run(setOpenrouter, api.settings.testOpenrouter)}
        />
        <ConnectionRow
          title="Telegram · deal alerts and buttons"
          help="Sends a test message to your chat."
          state={telegram}
          button="Send test"
          onTest={() => run(setTelegram, async () => {
            await api.settings.telegramTest();
            return { ok: true, message: "Test message sent. Check Telegram." };
          })}
        />
        <ConnectionRow
          title="Leboncoin · scanning"
          help="Fetches one real results page."
          state={leboncoin}
          button="Test fetch"
          onTest={() => run(setLeboncoin, api.settings.testLeboncoin)}
        />
      </ul>
    </Card>
  );
}

export default function Settings() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({ queryKey: ["settings"], queryFn: api.settings.get });
  const [form, setForm] = useState<SettingsType | null>(null);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const ready = form !== null;
  useEffect(() => {
    if (ready && window.location.hash === "#customs") {
      document.getElementById("customs")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [ready]);

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
          <p className="text-xs text-ink-muted">Connections first, then how profit is calculated. Press Save after changing anything.</p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/price-book">
            <Button type="button" size="sm" variant="secondary">
              <BookOpen className="h-4 w-4" /> Price book
            </Button>
          </Link>
          <Button type="submit" variant="primary" size="sm" disabled={saveMutation.isPending}>
            <Save className="h-4 w-4" /> {saveMutation.isPending ? "Saving…" : "Save settings"}
          </Button>
        </div>
      </div>

      <ConnectionsCard unsaved={JSON.stringify(form) !== JSON.stringify(data)} />

      <Card>
        <CardHeader title="Currency" subtitle="Official rate is used for customs valuation; parallel rate for your real cost" />
        <div className="grid gap-4 p-4 sm:grid-cols-3">
          <NumberField label="Official EUR → DZD" value={form.eur_dzd_official} step={0.1} onChange={(value) => set("eur_dzd_official", value)} />
          <NumberField label="Parallel EUR → DZD" value={form.eur_dzd_parallel} step={0.1} onChange={(value) => set("eur_dzd_parallel", value)} />
          <NumberField label="Bank transfer fee" value={form.transfer_fee_eur} step={1} suffix="EUR" onChange={(value) => set("transfer_fee_eur", value)} />
        </div>
      </Card>

      <div id="customs" className="scroll-mt-4">
      <Card>
        <CardHeader title="Customs" subtitle="Every profit figure depends on this. Confirm which regime really applies to your resale imports" />
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
      </div>

      <Card>
        <CardHeader
          title="Porsay tariff"
          subtitle="Chargeable weight = max(actual, L×W×H / 5000)"
          action={
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => set("porsay_tariff", [...form.porsay_tariff, { max_kg: 0, price_eur: 0 }])}
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
                value={tier.max_kg}
                step={0.5}
                onChange={(value) => {
                  const next = [...form.porsay_tariff];
                  next[index] = { ...next[index], max_kg: value };
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
                className="mb-0.5 text-danger-text"
                onClick={() => set("porsay_tariff", form.porsay_tariff.filter((_, position) => position !== index))}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
          <div className="grid gap-4 border-t border-border-subtle pt-3 sm:grid-cols-3">
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
        <CardHeader title="OpenRouter key and models" subtitle="One key powers Algerian prices, verdicts and negotiation messages. Without it, ads cannot be priced" />
        <div className="grid gap-4 p-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Switch checked={form.llm_enabled} onChange={(value) => set("llm_enabled", value)} label="Enable LLM features" />
          </div>
          <div>
            <Label>French message model</Label>
            <Input value={form.llm_model} onChange={(event) => set("llm_model", event.target.value)} placeholder="anthropic/claude-haiku-5.5" />
            <p className="mt-1 text-[11px] text-ink-faint">Only used when you press “Generate French message”.</p>
          </div>
          <div>
            <Label>API key</Label>
            <Input
              type="password"
              value={form.llm_api_key}
              onChange={(event) => set("llm_api_key", event.target.value)}
              placeholder="sk-or-v1-…"
            />
            <p className="mt-1 text-[11px] text-ink-faint">Create a normal key at openrouter.ai/keys (not a “Management key”: those cannot run models). Leave the masked value to keep the saved one.</p>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Which model does what"
          subtitle="AI never runs during scans. It runs when you open Hot deals or Fresh ads, on the first 5 ads that still need it"
        />
        <div className="grid gap-4 p-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Switch checked={form.dz_price_enabled} onChange={(value) => set("dz_price_enabled", value)} label="Look up Algerian prices" />
          </div>
          <div>
            <Label>1. Fill specs + write the product description</Label>
            <Input value={form.spec_model} onChange={(event) => set("spec_model", event.target.value)} placeholder="inclusionai/ling-3.2-flash:free" />
            <p className="mt-1 text-[11px] text-ink-faint">A free model is fine. It also says why it set each spec.</p>
          </div>
          <div>
            <Label>2. Algerian price (web search)</Label>
            <Input value={form.gemini_model} onChange={(event) => set("gemini_model", event.target.value)} placeholder="nvidia/nemotron-3-ultra-550b-a55b:free" />
            <p className="mt-1 text-[11px] text-ink-faint">The model can be free, but OpenRouter charges about $0.007 per lookup for the web search itself.</p>
          </div>
          <div>
            <Label>3. Verdict</Label>
            <Input value={form.verdict_model} onChange={(event) => set("verdict_model", event.target.value)} placeholder="anthropic/claude-haiku-5.5" />
            <p className="mt-1 text-[11px] text-ink-faint">Writes the opinion from the computed numbers.</p>
          </div>
          <p className="text-[11px] text-ink-faint sm:self-end">Uses the OpenRouter key above. Free models are rate limited; a failed step shows its reason on the results page.</p>
        </div>
      </Card>

      <Card>
        <CardHeader title="Telegram alerts" subtitle="Get the best new deals (with Algerian price estimate) on your phone" />
        <div className="grid gap-4 p-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Switch checked={form.telegram_enabled} onChange={(value) => set("telegram_enabled", value)} label="Enable Telegram alerts" />
            <p className="mt-1 text-[11px] text-ink-faint">
              1) In Telegram open @BotFather → /newbot → copy the token. 2) Paste it below and Save. 3) Open your bot, press Start, send “hi”.
              4) Click Detect chat, then Send test. Finally turn on “Send best new deals to Telegram” inside a search.
            </p>
          </div>
          <div>
            <Label>Bot token</Label>
            <Input
              type="password"
              value={form.telegram_bot_token}
              onChange={(event) => set("telegram_bot_token", event.target.value)}
              placeholder="123456:ABC-DEF…"
            />
          </div>
          <div>
            <Label>Chat id</Label>
            <Input value={form.telegram_chat_id} onChange={(event) => set("telegram_chat_id", event.target.value)} placeholder="auto-detected" />
          </div>
          <div>
            <Label>Alert threshold</Label>
            <Select value={form.notify_min_verdict} onChange={(event) => set("notify_min_verdict", event.target.value)}>
              <option value="good">Good or better (margin ≥ 15%)</option>
              <option value="great">Great only (margin ≥ 30%)</option>
            </Select>
          </div>
          <div>
            <Label>Max alerts per run</Label>
            <Input
              type="number"
              min={1}
              max={20}
              value={form.notify_max_per_run}
              onChange={(event) => set("notify_max_per_run", Number(event.target.value) || 5)}
            />
          </div>
          <NumberField
            label="Ads count as fresh under (336 h = 14 days)"
            suffix="hours"
            value={form.max_ad_age_hours}
            onChange={(value) => set("max_ad_age_hours", Math.max(1, Math.round(value)))}
          />
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label>Quiet from (Algeria hour)</Label>
              <Input
                type="number"
                min={0}
                max={23}
                placeholder="off"
                value={form.quiet_start_hour ?? ""}
                onChange={(event) => set("quiet_start_hour", event.target.value === "" ? null : Number(event.target.value))}
              />
            </div>
            <div>
              <Label>Quiet until</Label>
              <Input
                type="number"
                min={0}
                max={24}
                placeholder="off"
                value={form.quiet_end_hour ?? ""}
                onChange={(event) => set("quiet_end_hour", event.target.value === "" ? null : Number(event.target.value))}
              />
            </div>
          </div>
          <div className="sm:col-span-2">
            <Switch
              checked={form.alert_pickup_only}
              onChange={(value) => set("alert_pickup_only", value)}
              label="Also alert on ads that cannot be shipped (pickup only)"
            />
          </div>
          <div className="flex flex-wrap gap-2 sm:col-span-2">
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() =>
                api.settings
                  .telegramDetect()
                  .then((r) => {
                    set("telegram_chat_id", r.chat_id);
                    toast(`Chat detected${r.title ? `: ${r.title}` : ""}`, "success");
                  })
                  .catch((err: Error) => toast(err.message, "error"))
              }
            >
              Detect chat
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() =>
                api.settings
                  .telegramTest()
                  .then(() => toast("Test message sent", "success"))
                  .catch((err: Error) => toast(err.message, "error"))
              }
            >
              Send test
            </Button>
            <span className="self-center text-[11px] text-ink-faint">Save settings before Detect / Test.</span>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Resale model"
          subtitle="Keeps profit estimates honest. Both values are re-learned automatically from the deals you mark Bought / Sold."
        />
        <div className="grid gap-4 p-4 sm:grid-cols-2">
          <NumberField
            label="Resale haircut"
            suffix="% below the Algerian asking price"
            step={0.5}
            value={form.resale_haircut_pct}
            onChange={(value) => set("resale_haircut_pct", value)}
          />
          <NumberField
            label="Discount sellers accept"
            suffix="% off the Leboncoin price"
            step={0.5}
            value={form.avg_discount_pct}
            onChange={(value) => set("avg_discount_pct", value)}
          />
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
