import { ApiError } from "./auth";
import { parseAiError, type AiModerationUpdate } from "./ai-errors";
import { API_BASE } from "./config";
import type { Locale } from "./i18n";
import { shouldRequestTranslation } from "./language";
import { createRetryableCache, withAbortTimeout } from "./retryable-cache";

export interface AiStatus {
  enabled: boolean;
}

export interface GeneratedPoll {
  question: string;
  options: string[];
}

export type TranslationContext = "post" | "comment" | "patch" | "guild" | "composer" | "poll";
export type WritingAction = "polish" | "shorten" | "clarify";

export interface TranslationField {
  key: string;
  text: string;
}

export interface TranslationBundle {
  fields: Array<{ key: string; translation: string }>;
  cached: boolean;
  skipped: boolean;
}

export interface DisplayTranslation {
  locale: Locale;
  title: string | null;
  body: string;
  cached: boolean;
}

export interface AiContentSource {
  contentId: string;
  revisionNumber: number;
}

export class AiRequestError extends ApiError {
  moderationUpdate: AiModerationUpdate | null;

  constructor(code: string, moderationUpdate: AiModerationUpdate | null = null) {
    super(code);
    this.name = "AiRequestError";
    this.moderationUpdate = moderationUpdate;
  }
}

const AI_STATUS_TTL_MS = 30_000;
const AI_STATUS_TIMEOUT_MS = 5_000;
const aiStatusCache = createRetryableCache(async () => {
  const response = await withAbortTimeout(
    (signal) => fetch(`${API_BASE}/ai/status`, { credentials: "include", signal }),
    AI_STATUS_TIMEOUT_MS,
  );
  if (!response.ok) throw new ApiError("AI_FEATURE_UNAVAILABLE");
  const payload = await response.json();
  return { enabled: payload?.enabled === true };
}, AI_STATUS_TTL_MS);

async function requestError(response: Response): Promise<AiRequestError> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    // Keep a stable client-side fallback when a proxy returns a non-JSON error.
  }
  const descriptor = parseAiError(payload, response.headers);
  return new AiRequestError(descriptor.code, descriptor.moderationUpdate);
}

async function request<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "include",
  });
  if (!response.ok) throw await requestError(response);
  return response.json() as Promise<T>;
}

export function getAiStatus(forceRefresh = false): Promise<AiStatus> {
  return aiStatusCache.get(forceRefresh);
}

export function refreshAiStatus(): Promise<AiStatus> {
  return getAiStatus(true);
}

export async function summarizeText(text: string, targetLocale: Locale): Promise<string> {
  const result = await request<{ summary?: unknown }>("/ai/summarize", {
    text,
    target_locale: targetLocale,
  });
  if (typeof result.summary !== "string" || !result.summary.trim()) {
    throw new ApiError("AI_RESPONSE_INVALID");
  }
  return result.summary.trim();
}

export async function translateText(text: string, targetLocale: Locale): Promise<string> {
  const result = await request<{ translation?: unknown }>("/ai/translate", {
    text,
    target_locale: targetLocale,
  });
  if (typeof result.translation !== "string" || !result.translation.trim()) {
    throw new ApiError("AI_RESPONSE_INVALID");
  }
  return result.translation.trim();
}

export async function translateFields(
  fields: TranslationField[],
  targetLocale: Locale,
  context: TranslationContext,
  source: AiContentSource | null = null,
): Promise<TranslationBundle> {
  if (!shouldRequestTranslation(fields, targetLocale)) {
    return {
      fields: fields.map((field) => ({ key: field.key, translation: field.text.trim() })),
      cached: true,
      skipped: true,
    };
  }
  const result = await request<{ fields?: unknown; cached?: unknown }>("/ai/translate/fields", {
    fields,
    target_locale: targetLocale,
    context,
    ...(source
      ? {
          source_content_id: source.contentId,
          source_revision_number: source.revisionNumber,
        }
      : {}),
  });
  if (!Array.isArray(result.fields) || result.fields.length !== fields.length) {
    throw new ApiError("AI_RESPONSE_INVALID");
  }
  const translated = result.fields.map((field, index) => {
    const item = field as { key?: unknown; translation?: unknown };
    if (
      typeof item.key !== "string"
      || item.key !== fields[index]?.key
      || typeof item.translation !== "string"
      || !item.translation.trim()
    ) {
      throw new ApiError("AI_RESPONSE_INVALID");
    }
    return { key: item.key, translation: item.translation.trim() };
  });
  return { fields: translated, cached: result.cached === true, skipped: false };
}

export async function assistWriting(
  fields: TranslationField[],
  targetLocale: Locale,
  context: TranslationContext,
  action: WritingAction,
): Promise<Array<{ key: string; text: string }>> {
  const result = await request<{ fields?: unknown }>("/ai/writing/assist", {
    fields,
    target_locale: targetLocale,
    context,
    action,
  });
  if (!Array.isArray(result.fields) || result.fields.length !== fields.length) {
    throw new ApiError("AI_RESPONSE_INVALID");
  }
  return result.fields.map((field, index) => {
    const item = field as { key?: unknown; translation?: unknown };
    if (
      typeof item.key !== "string"
      || item.key !== fields[index]?.key
      || typeof item.translation !== "string"
      || !item.translation.trim()
    ) {
      throw new ApiError("AI_RESPONSE_INVALID");
    }
    return { key: item.key, text: item.translation.trim() };
  });
}

export async function generatePoll(
  text: string,
  targetLocale: Locale,
  excludeQuestions: string[],
): Promise<GeneratedPoll> {
  const result = await request<{ question?: unknown; options?: unknown }>("/ai/polls/generate", {
    text,
    target_locale: targetLocale,
    exclude_questions: excludeQuestions,
  });
  const question = typeof result.question === "string" ? result.question.trim() : "";
  const options = Array.isArray(result.options)
    ? result.options.filter((option): option is string => typeof option === "string")
      .map((option) => option.trim())
      .filter(Boolean)
    : [];
  if (!question || options.length < 2 || options.length > 6) {
    throw new ApiError("AI_RESPONSE_INVALID");
  }
  return { question, options };
}
