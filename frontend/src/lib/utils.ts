import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const eurFormatter = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

const eurFormatter2 = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 2,
});

export function eur(value?: number | null, decimals = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return (decimals ? eurFormatter2 : eurFormatter).format(value);
}

export function num(value?: number | null): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-GB").format(Math.round(value));
}

export function dzd(value?: number | null): string {
  if (value === null || value === undefined) return "—";
  return `${new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 }).format(value)} DA`;
}

export function dateShort(iso?: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function timeAgo(iso?: string | null): string {
  if (!iso) return "never";
  const date = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  if (Number.isNaN(date.getTime())) return "never";
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31536000],
    ["month", 2592000],
    ["week", 604800],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return formatter.format(-Math.round(seconds / size), unit);
  }
  return "just now";
}

export const DEAL_STYLES: Record<string, string> = {
  excellent:
    "bg-success-bg text-success-ink border-success-border",
  great: "bg-success-bg text-success-ink border-success-border",
  skip: "bg-danger-bg text-danger-ink border-danger-border",
  good: "bg-info-bg text-info-ink border-info-border",
  fair: "bg-warning-bg text-warning-ink border-warning-border",
  overpriced:
    "bg-danger-bg text-danger-ink border-danger-border",
};

export const CONDITION_LABELS: Record<string, string> = {
  new: "New",
  like_new: "Like new",
  very_good: "Very good",
  good: "Good",
  fair: "Fair",
  parts: "For parts",
};

export function conditionLabel(value?: string | null): string {
  if (!value) return "—";
  return CONDITION_LABELS[value] || value;
}

export function scoreColor(value?: number | null): string {
  if (value === null || value === undefined) return "text-ink-faint";
  if (value >= 80) return "text-score-high";
  if (value >= 60) return "text-score-good";
  if (value >= 40) return "text-score-fair";
  return "text-score-low";
}

export function imageUrl(image: any): string | null {
  if (!image) return null;
  const raw = typeof image === "string" ? image : image.url || image.src || image.link || "";
  if (!raw) return null;
  if (raw.startsWith("//")) return `https:${raw}`;
  if (raw.startsWith("http://")) return raw.replace("http://", "https://");
  if (raw.startsWith("/")) return `https://www.leboncoin.fr${raw}`;
  return raw.startsWith("https://") ? raw : null;
}

export function specsSummary(specs: Record<string, any>): string {
  const parts: string[] = [];
  if (specs.cpu) parts.push(String(specs.cpu).toUpperCase());
  if (specs.ram_gb) parts.push(`${specs.ram_gb} GB`);
  if (specs.storage_gb) parts.push(`${specs.storage_gb >= 1000 ? `${specs.storage_gb / 1000} TB` : `${specs.storage_gb} GB`}`);
  if (specs.gpu) parts.push(specs.gpu);
  if (specs.screen_inches) parts.push(`${specs.screen_inches}"`);
  return parts.join(" \u00b7 ");
}