import { writable } from "svelte/store";

import type { DisplayTranslation, TranslationContext } from "./ai";
import type { Locale } from "./i18n";

export const sharedTranslations = writable<Record<string, DisplayTranslation>>({});

export function translationStateKey(
  context: TranslationContext,
  contentId: string,
  revisionNumber: number,
  targetLocale: Locale,
): string {
  return `${context}:${contentId}:${revisionNumber}:${targetLocale}`;
}

export function publishTranslation(key: string, translation: DisplayTranslation): void {
  sharedTranslations.update((translations) => ({ ...translations, [key]: translation }));
}
