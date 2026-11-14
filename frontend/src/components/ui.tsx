import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { cn, DEAL_STYLES } from "../lib/utils";
import { useToasts } from "../lib/toast";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-primary text-on-primary hover:bg-primary-hover",
  secondary:
    "border border-border-control bg-surface text-ink-soft hover:bg-surface-hover",
  ghost: "text-ink-secondary hover:bg-surface-muted",
  danger: "bg-danger text-on-danger hover:bg-danger-hover",
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
};

export function Button({
  variant = "secondary",
  size = "md",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring disabled:cursor-not-allowed disabled:opacity-50",
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        className,
      )}
      {...props}
    />
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-surface shadow-sm",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
      <div>
        <h2 className="text-sm font-semibold">{title}</h2>
        {subtitle ? <p className="mt-0.5 text-xs text-ink-muted">{subtitle}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function Badge({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        "border-border-control bg-surface-muted text-ink-strong",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function DealBadge({ label, score }: { label?: string | null; score?: number | null }) {
  if (!label) return <Badge>Not rated</Badge>;
  return (
    <Badge className={cn("capitalize", DEAL_STYLES[label] || "")}>
      {label}
      {score !== null && score !== undefined ? ` · ${Math.round(score)}` : ""}
    </Badge>
  );
}

export function Label({ children, htmlFor, className }: { children: ReactNode; htmlFor?: string; className?: string }) {
  return (
    <label htmlFor={htmlFor} className={cn("mb-1 block text-xs font-medium text-ink-label", className)}>
      {children}
    </label>
  );
}

const FIELD_CLASS =
  "w-full rounded-lg border border-border-control bg-surface px-3 py-2 text-sm text-ink placeholder:text-placeholder focus:border-border-strong focus:outline-none focus:ring-2 focus:ring-field-ring";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(FIELD_CLASS, className)} {...props} />;
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(FIELD_CLASS, "min-h-20 resize-y", className)} {...props} />;
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(FIELD_CLASS, "pr-8", className)} {...props}>
      {children}
    </select>
  );
}

export function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="inline-flex items-center gap-2 text-sm text-ink-strong"
    >
      <span
        className={cn(
          "relative h-5 w-9 rounded-full transition-colors",
          checked ? "bg-toggle-on" : "bg-toggle-off",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-4 w-4 rounded-full bg-toggle-thumb shadow transition-transform",
            checked ? "translate-x-4" : "translate-x-0.5",
          )}
        />
      </span>
      {label}
    </button>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-skeleton", className)} />;
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <p className="text-sm font-medium">{title}</p>
      {description ? <p className="max-w-md text-xs text-ink-muted">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

export function ScoreRing({ value, size = 52 }: { value?: number | null; size?: number }) {
  const score = value ?? 0;
  const radius = (size - 6) / 2;
  const circumference = 2 * Math.PI * radius;
  const arcClass =
    value === null || value === undefined
      ? "stroke-ring-empty"
      : score >= 80
        ? "stroke-ring-high"
        : score >= 60
          ? "stroke-ring-good"
          : score >= 40
            ? "stroke-ring-fair"
            : "stroke-ring-low";
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" strokeWidth="4" className="stroke-ring-track" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth="4"
          strokeLinecap="round"
          className={arcClass}
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - score / 100)}
        />
      </svg>
      <span className="absolute text-[11px] font-semibold">{value === null || value === undefined ? "—" : Math.round(score)}</span>
    </div>
  );
}

export function Toaster() {
  const toasts = useToasts();
  return (
    <div className="pointer-events-none fixed bottom-20 left-1/2 z-50 flex w-full max-w-sm -translate-x-1/2 flex-col gap-2 px-3 sm:bottom-6 sm:left-auto sm:right-6 sm:translate-x-0">
      {toasts.map((item) => (
        <div
          key={item.id}
          className={cn(
            "animate-fade-in pointer-events-auto rounded-lg border px-3 py-2 text-sm shadow-lg",
            item.tone === "error"
              ? "border-danger-border bg-danger-soft text-danger-soft-ink"
              : item.tone === "success"
                ? "border-success-border bg-success-soft text-success-soft-ink"
                : "border-border-control bg-surface text-ink-soft",
          )}
        >
          {item.message}
        </div>
      ))}
    </div>
  );
}
