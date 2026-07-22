import { readable } from "svelte/store";

export const relativeTimeClock = readable(Date.now(), (set) => {
  if (typeof window === "undefined") return;
  const interval = window.setInterval(() => set(Date.now()), 30_000);
  return () => window.clearInterval(interval);
});
