import type { Locale } from "./i18n";

function activeLocale(): Locale {
  if (typeof document === "undefined") return "en";
  if (document.documentElement.lang.startsWith("ja")) return "ja";
  if (document.documentElement.lang.startsWith("zh")) return "zh-TW";
  return "en";
}

export function timeAgo(dateStr: string, requestedLocale = activeLocale()): string {
  const elapsedSeconds = Math.round((new Date(dateStr).getTime() - Date.now()) / 1000);
  const format = new Intl.RelativeTimeFormat(requestedLocale, { numeric: "auto" });
  if (Math.abs(elapsedSeconds) < 60) return format.format(elapsedSeconds, "second");
  const minutes = Math.round(elapsedSeconds / 60);
  if (Math.abs(minutes) < 60) return format.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return format.format(hours, "hour");
  const days = Math.round(hours / 24);
  if (Math.abs(days) < 30) return format.format(days, "day");
  return new Date(dateStr).toLocaleDateString(requestedLocale);
}

export function stripMarkdown(md: string): string {
  return md
    .replace(/^#{1,6}\s+(.+)$/gm, "$1")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/\*(.+?)\*/g, "$1")
    .replace(/`{1,3}.+?`{1,3}/g, (value) => value.replace(/`/g, ""))
    .replace(/\[(.+?)\]\(.+?\)/g, "$1")
    .replace(/!\[.*?\]\(.+?\)/g, "[Image]")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/^\d+\.\s+/gm, "")
    .replace(/^>\s+/gm, "")
    .replace(/---+/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
