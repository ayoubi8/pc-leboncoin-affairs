import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Laptop, LayoutDashboard, Moon, Monitor, Plus, Search, Settings as SettingsIcon, Sun } from "lucide-react";
import { cn } from "../lib/utils";
import { applyTheme, getThemePreference, watchSystemTheme, type ThemePreference } from "../lib/theme";
import { Toaster } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/searches", label: "Searches", icon: Search, end: false },
  { to: "/searches/new", label: "New search", icon: Plus, end: true },
  { to: "/settings", label: "Settings", icon: SettingsIcon, end: true },
];

const THEME_ORDER: ThemePreference[] = ["light", "dark", "system"];
const THEME_LABEL: Record<ThemePreference, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
};

function ThemeToggle() {
  const [preference, setPreference] = useState<ThemePreference>(getThemePreference());

  useEffect(() => watchSystemTheme(), []);

  function cycle() {
    const index = THEME_ORDER.indexOf(preference);
    const next = THEME_ORDER[(index + 1) % THEME_ORDER.length];
    setPreference(next);
    applyTheme(next);
  }

  const Icon = preference === "light" ? Sun : preference === "dark" ? Moon : Monitor;

  return (
    <button
      type="button"
      onClick={cycle}
      className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-zinc-600 transition-colors hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
      title={`Theme: ${THEME_LABEL[preference]}`}
    >
      <Icon className="h-4 w-4" />
      {THEME_LABEL[preference]}
    </button>
  );
}

export default function Layout() {
  return (
    <div className="min-h-screen lg:flex">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-zinc-200 bg-white px-3 py-4 dark:border-zinc-800 dark:bg-zinc-900 lg:flex">
        <div className="mb-6 flex items-center gap-2 px-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900">
            <Laptop className="h-4 w-4" />
          </span>
          <div>
            <p className="text-sm font-semibold leading-tight">Deal Finder</p>
            <p className="text-[11px] text-zinc-500 dark:text-zinc-400">Leboncoin → Algeria</p>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-zinc-900 font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
                    : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800",
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-4 border-t border-zinc-200 pt-3 dark:border-zinc-800">
          <ThemeToggle />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-zinc-200 bg-white/85 px-4 py-3 backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/85 lg:hidden">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900">
              <Laptop className="h-4 w-4" />
            </span>
            <span className="text-sm font-semibold">Deal Finder</span>
          </div>
          <ThemeToggleInline />
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 px-3 py-4 pb-24 sm:px-5 lg:py-6 lg:pb-8">
          <Outlet />
        </main>

        <nav className="fixed bottom-0 left-0 right-0 z-30 grid grid-cols-4 border-t border-zinc-200 bg-white/95 backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/95 lg:hidden">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex flex-col items-center gap-1 py-2 text-[11px]",
                  isActive ? "font-semibold text-zinc-900 dark:text-zinc-100" : "text-zinc-500 dark:text-zinc-400",
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>

      <Toaster />
    </div>
  );
}

function ThemeToggleInline() {
  const [preference, setPreference] = useState<ThemePreference>(getThemePreference());
  const Icon = preference === "light" ? Sun : preference === "dark" ? Moon : Monitor;
  return (
    <button
      type="button"
      onClick={() => {
        const index = THEME_ORDER.indexOf(preference);
        const next = THEME_ORDER[(index + 1) % THEME_ORDER.length];
        setPreference(next);
        applyTheme(next);
      }}
      className="rounded-lg p-2 text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
      aria-label="Toggle theme"
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}
