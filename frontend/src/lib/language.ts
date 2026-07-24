import type { Locale } from "./i18n";

type LanguageField = { text: string };

const JAPANESE_KANA = /[\u3040-\u30ff\u31f0-\u31ff]/u;
const CJK_IDEOGRAPH = /[\u3400-\u9fff\uf900-\ufaff]/u;
const LATIN_LETTER = /[A-Za-z]/u;

// Keep this deliberately conservative: uncertain Han-only text must still reach AI.
const TRADITIONAL_CHINESE = /[臺灣與為這個們從國學會說點發現時對來後過還華體關議場區標實內繁篇]/u;

export function detectSupportedLocale(text: string): Locale | null {
  const normalized = text.trim();
  if (!normalized) return null;
  if (JAPANESE_KANA.test(normalized)) return "ja";
  if (TRADITIONAL_CHINESE.test(normalized)) return "zh-TW";
  if (CJK_IDEOGRAPH.test(normalized)) return null;
  if (LATIN_LETTER.test(normalized)) return "en";
  return null;
}

export function detectFieldsLocale(fields: LanguageField[]): Locale | null {
  const detected = fields
    .map((field) => field.text.trim())
    .filter(Boolean)
    .map(detectSupportedLocale);
  if (detected.length === 0 || detected.some((item) => item === null)) return null;
  const first = detected[0];
  return first && detected.every((item) => item === first) ? first : null;
}

export function shouldRequestTranslation(
  fields: LanguageField[],
  targetLocale: Locale,
): boolean {
  return detectFieldsLocale(fields) !== targetLocale;
}
