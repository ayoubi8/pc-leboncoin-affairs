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
    "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-300 dark:border-emerald-500/30",
  good: "bg-sky-100 text-sky-800 border-sky-200 dark:bg-sky-500/15 dark:text-sky-300 dark:border-sky-500/30",
  fair: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-500/15 dark:text-amber-300 dark:border-amber-500/30",
  overpriced:
    "bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-500/15 dark:text-rose-300 dark:border-rose-500/30",
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
  if (value === null || value === undefined) return "text-zinc-400";
  if (value >= 80) return "text-emerald-600 dark:text-emerald-400";
  if (value >= 60) return "text-sky-600 dark:text-sky-400";
  if (value >= 40) return "text-amber-600 dark:text-amber-400";
  return "text-rose-600 dark:text-rose-400";
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