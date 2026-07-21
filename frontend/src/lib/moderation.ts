export type ModerationStatus =
  | "published"
  | "pending_review"
  | "approved"
  | "rejected";

export interface ModerationFields {
  moderation_status: ModerationStatus | null;
  moderation_reason: string | null;
  moderation_review_note: string | null;
}

export const MODERATION_UPDATED_EVENT = "agora:moderation-updated";

export interface ModerationUpdateDetail {
  type: "moderation_pending" | "moderation_approved" | "moderation_rejected";
  link: string;
}

export function isModerationNotificationType(
  type: unknown,
): type is ModerationUpdateDetail["type"] {
  return type === "moderation_pending"
    || type === "moderation_approved"
    || type === "moderation_rejected";
}

export function dispatchModerationUpdate(detail: ModerationUpdateDetail): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(MODERATION_UPDATED_EVENT, { detail }));
}

export function onModerationUpdate(
  callback: (detail: ModerationUpdateDetail) => void,
): () => void {
  if (typeof window === "undefined") return () => {};
  const handler = (event: Event) => {
    const detail = (event as CustomEvent<ModerationUpdateDetail>).detail;
    if (detail?.link) callback(detail);
  };
  window.addEventListener(MODERATION_UPDATED_EVENT, handler);
  return () => window.removeEventListener(MODERATION_UPDATED_EVENT, handler);
}

export function onModerationUpdateForPath(
  path: string,
  callback: () => void,
): () => void {
  if (typeof window === "undefined") return () => {};
  const normalizedPath = path.replace(/\/+$/, "") || "/";
  return onModerationUpdate((detail) => {
    const eventPath = detail.link.split(/[?#]/, 1)[0].replace(/\/+$/, "") || "/";
    if (eventPath === normalizedPath) callback();
  });
}

export function isModerationRestricted(
  status: ModerationStatus | null | undefined,
): boolean {
  return status === "pending_review" || status === "rejected";
}

export function hasModerationNotice(
  status: ModerationStatus | null | undefined,
): boolean {
  return status === "pending_review" || status === "approved" || status === "rejected";
}
