import { ApiError } from "./auth";
import { API_BASE } from "./config";
import type { Locale } from "./i18n";

export interface AiStatus {
  enabled: boolean;
}

export interface GeneratedPoll {
  question: string;
  options: string[];
}

let statusRequest: Promise<AiStatus> | null = null;

async function errorDetail(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    if (typeof payload?.detail === "string") return payload.detail;
    if (typeof payload?.code === "string") return payload.code;
  } catch {
    // Keep a stable client-side fallback when a proxy returns a non-JSON error.
  }
  return "AI_REQUEST_FAILED";
}

async function request<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "include",
  });
  if (!response.ok) throw new ApiError(await errorDetail(response));
  return response.json() as Promise<T>;
}

export function getAiStatus(): Promise<AiStatus> {
  statusRequest ??= fetch(`${API_BASE}/ai/status`, { credentials: "include" })
    .then(async (response) => {
      if (!response.ok) return { enabled: false };
      const payload = await response.json();
      return { enabled: payload?.enabled === true };
    })
    .catch(() => ({ enabled: false }));
  return statusRequest;
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
