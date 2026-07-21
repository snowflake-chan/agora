import { writable } from "svelte/store";

export type Theme = "default" | "tiktok" | "claude" | "apple" | "google";
export type Motion = "system" | "comfortable" | "reduced";
export type ColorMode = "light" | "dark";
export type HomeLayout = "split" | "pages";

export const theme = writable<Theme>("default");
export const motion = writable<Motion>("system");
export const colorMode = writable<ColorMode>("dark");
export const homeLayout = writable<HomeLayout>("split");
export const autoTranslate = writable(false);

const THEME_KEY = "agora:theme";
const MOTION_KEY = "agora:motion";
const COLOR_MODE_KEY = "agora:colorMode";
const HOME_LAYOUT_KEY = "agora:homeLayout";
const AUTO_TRANSLATE_KEY = "agora:autoTranslate";

export function normalizeTheme(value: string | null): Theme {
  return value === "tiktok" ||
    value === "claude" ||
    value === "apple" ||
    value === "google"
    ? value
    : "default";
}

export function normalizeMotion(value: string | null): Motion {
  return value === "comfortable" || value === "reduced" ? value : "system";
}

export function normalizeColorMode(value: string | null): ColorMode {
  return value === "light" ? "light" : "dark";
}

export function normalizeHomeLayout(value: string | null): HomeLayout {
  return value === "pages" ? "pages" : "split";
}

function applyTheme(value: Theme) {
  document.documentElement.dataset.theme = value;
}

function applyMotion(value: Motion) {
  document.documentElement.dataset.motion = value;
}

function applyColorMode(value: ColorMode) {
  document.documentElement.dataset.colorMode = value;
}

function applyHomeLayout(value: HomeLayout) {
  document.documentElement.dataset.homeLayout = value;
}

function persistPreference(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {}
}

function updateWithTransition(update: () => void) {
  const transitionDocument = document as Document & {
    startViewTransition?: (callback: () => void) => unknown;
  };
  if (
    document.documentElement.dataset.motion !== "reduced" &&
    transitionDocument.startViewTransition
  ) {
    transitionDocument.startViewTransition(update);
    return;
  }
  update();
}

export function initPreferences() {
  if (typeof window === "undefined") return;
  let savedTheme: string | null = null;
  let savedMotion: string | null = null;
  let savedColorMode: string | null = null;
  let savedHomeLayout: string | null = null;
  let savedAutoTranslate: string | null = null;
  try {
    savedTheme = window.localStorage.getItem(THEME_KEY);
    savedMotion = window.localStorage.getItem(MOTION_KEY);
    savedColorMode = window.localStorage.getItem(COLOR_MODE_KEY);
    savedHomeLayout = window.localStorage.getItem(HOME_LAYOUT_KEY);
    savedAutoTranslate = window.localStorage.getItem(AUTO_TRANSLATE_KEY);
  } catch {}
  const nextTheme = normalizeTheme(savedTheme);
  const nextMotion = normalizeMotion(savedMotion);
  const nextColorMode = normalizeColorMode(savedColorMode);
  const nextHomeLayout = normalizeHomeLayout(savedHomeLayout);
  theme.set(nextTheme);
  motion.set(nextMotion);
  colorMode.set(nextColorMode);
  homeLayout.set(nextHomeLayout);
  autoTranslate.set(savedAutoTranslate === "true");
  applyTheme(nextTheme);
  applyMotion(nextMotion);
  applyColorMode(nextColorMode);
  applyHomeLayout(nextHomeLayout);
}

export function setTheme(next: Theme) {
  if (typeof window === "undefined") {
    theme.set(next);
    return;
  }
  updateWithTransition(() => {
    theme.set(next);
    persistPreference(THEME_KEY, next);
    applyTheme(next);
  });
}

export function setMotion(next: Motion) {
  motion.set(next);
  if (typeof window !== "undefined") {
    persistPreference(MOTION_KEY, next);
    applyMotion(next);
  }
}

export function setColorMode(next: ColorMode) {
  if (typeof window === "undefined") {
    colorMode.set(next);
    return;
  }
  updateWithTransition(() => {
    colorMode.set(next);
    persistPreference(COLOR_MODE_KEY, next);
    applyColorMode(next);
  });
}

export function setHomeLayout(next: HomeLayout) {
  homeLayout.set(next);
  if (typeof window !== "undefined") {
    persistPreference(HOME_LAYOUT_KEY, next);
    applyHomeLayout(next);
  }
}

export function setAutoTranslate(next: boolean) {
  autoTranslate.set(next);
  if (typeof window !== "undefined") {
    persistPreference(AUTO_TRANSLATE_KEY, String(next));
  }
}
