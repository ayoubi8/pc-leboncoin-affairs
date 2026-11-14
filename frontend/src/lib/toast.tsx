import { useEffect, useState } from "react";

export type ToastTone = "success" | "error" | "info";

interface ToastItem {
  id: number;
  message: string;
  tone: ToastTone;
}

type Listener = (items: ToastItem[]) => void;

let items: ToastItem[] = [];
const listeners = new Set<Listener>();
let counter = 0;

function emit() {
  listeners.forEach((listener) => listener([...items]));
}

export function toast(message: string, tone: ToastTone = "info") {
  const item = { id: ++counter, message, tone };
  items = [...items, item];
  emit();
  window.setTimeout(() => {
    items = items.filter((entry) => entry.id !== item.id);
    emit();
  }, 4200);
}

export function useToasts(): ToastItem[] {
  const [snapshot, setSnapshot] = useState(items);
  useEffect(() => {
    const listener: Listener = (next) => setSnapshot(next);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);
  return snapshot;
}
