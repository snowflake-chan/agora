export function safeReturnTo(value: string | null, origin: string): string {
  if (!value) return "/";

  try {
    const target = new URL(value, origin);
    if (target.origin !== origin) return "/";
    return `${target.pathname}${target.search}${target.hash}`;
  } catch {
    return "/";
  }
}
