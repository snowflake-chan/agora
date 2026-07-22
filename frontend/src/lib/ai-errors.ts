export interface AiModerationUpdate {
  contentId: string;
  status: "pending_review";
  reason: string | null;
  revisionNumber: number | null;
  targetHref: string | null;
}

export interface AiErrorDescriptor {
  code: string;
  moderationUpdate: AiModerationUpdate | null;
}

interface HeaderReader {
  get(name: string): string | null;
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function numberValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isInteger(value) && value > 0) return value;
  if (typeof value === "string" && /^\d+$/.test(value)) {
    const parsed = Number(value);
    return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
  }
  return null;
}

function safeTargetHref(value: unknown): string | null {
  const href = stringValue(value);
  return href?.startsWith("/") && !href.startsWith("//") ? href : null;
}

export function parseAiError(
  payload: unknown,
  headers: HeaderReader,
): AiErrorDescriptor {
  const body = record(payload);
  const detail = body?.detail;
  const detailObject = record(detail);
  const code = stringValue(body?.code)
    ?? stringValue(detailObject?.code)
    ?? stringValue(detail)
    ?? "AI_REQUEST_FAILED";

  const rawUpdate = record(body?.moderation_update)
    ?? record(detailObject?.moderation_update);
  const status = stringValue(rawUpdate?.status)
    ?? stringValue(headers.get("X-Agora-Moderation-Status"));
  const contentId = stringValue(rawUpdate?.content_id)
    ?? stringValue(headers.get("X-Agora-Content-Id"));

  const moderationUpdate = status === "pending_review" && contentId
    ? {
        contentId,
        status,
        reason: stringValue(rawUpdate?.reason)
          ?? stringValue(headers.get("X-Agora-Moderation-Reason")),
        revisionNumber: numberValue(rawUpdate?.revision_number)
          ?? numberValue(headers.get("X-Agora-Content-Revision"))
          ?? numberValue(headers.get("X-Agora-Revision-Number")),
        targetHref: safeTargetHref(rawUpdate?.target_href)
          ?? safeTargetHref(headers.get("X-Agora-Content-Href"))
          ?? safeTargetHref(headers.get("X-Agora-Target-Href")),
      } satisfies AiModerationUpdate
    : null;

  return { code, moderationUpdate };
}
