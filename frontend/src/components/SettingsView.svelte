<script lang="ts">
  import { onMount } from "svelte";
  import {
    Activity,
    Check,
    Columns2Icon,
    Languages,
    MoonIcon,
    Palette,
    Rows3Icon,
    SunIcon,
  } from "@lucide/svelte";
  import {
    getLocaleLabel,
    initI18n,
    locale,
    setLocale,
    translator,
    type Locale,
  } from "../lib/i18n";
  import {
    AI_TRANSLATION_LANGUAGES,
    aiTranslationLanguage,
    colorMode,
    autoTranslate,
    homeLayout,
    initPreferences,
    motion,
    setAITranslationLanguage,
    setColorMode,
    setAutoTranslate,
    setHomeLayout,
    setMotion,
    setTheme,
    theme,
    type AITranslationPreference,
    type ColorMode,
    type HomeLayout,
    type Motion,
    type Theme,
  } from "../lib/preferences";

  const locales: Locale[] = ["en", "ja", "zh-TW"];
  const themes: Theme[] = ["default", "tiktok", "claude", "apple", "google"];
  const colorModes: ColorMode[] = ["light", "dark"];
  const homeLayouts: HomeLayout[] = ["split", "pages"];
  const motions: Motion[] = ["system", "comfortable", "reduced"];

  onMount(() => {
    initI18n();
    initPreferences();
  });

  function translationLanguageLabel(value: AITranslationPreference) {
    if (value === "interface") return $translator("settings.followInterfaceLanguage");
    try {
      return new Intl.DisplayNames([$locale], { type: "language" }).of(value) ?? value;
    } catch {
      return value;
    }
  }

  function themeTitle(value: Theme) {
    if (value === "tiktok") return $translator("settings.tiktokTheme");
    if (value === "claude") return $translator("settings.claudeTheme");
    if (value === "apple") return $translator("settings.appleTheme");
    if (value === "google") return $translator("settings.googleTheme");
    return $translator("settings.defaultTheme");
  }

  function themeDescription(value: Theme) {
    if (value === "tiktok") return $translator("settings.tiktokThemeDescription");
    if (value === "claude") return $translator("settings.claudeThemeDescription");
    if (value === "apple") return $translator("settings.appleThemeDescription");
    if (value === "google") return $translator("settings.googleThemeDescription");
    return $translator("settings.defaultThemeDescription");
  }

  function layoutTitle(value: HomeLayout) {
    return $translator(value === "split" ? "settings.splitLayout" : "settings.pageLayout");
  }

  function layoutDescription(value: HomeLayout) {
    return $translator(
      value === "split"
        ? "settings.splitLayoutDescription"
        : "settings.pageLayoutDescription",
    );
  }
</script>

<div class="settings-shell">
  <header class="settings-header">
    <div>
      <p>{$translator("settings.eyebrow")}</p>
      <h1>{$translator("settings.title")}</h1>
    </div>
    <p class="settings-lede">{$translator("settings.description")}</p>
  </header>

  <div class="settings-layout">
    <div class="settings-groups">
      <section class="settings-section" aria-labelledby="language-title">
        <div class="section-icon"><Languages size={18} /></div>
        <div class="section-copy">
          <h2 id="language-title">{$translator("common.language")}</h2>
          <p>{$translator("settings.languageDescription")}</p>
        </div>
        <div class="segmented-control locale-control" aria-label={$translator("common.language")}>
          {#each locales as item}
            <button
              type="button"
              class:active={$locale === item}
              aria-pressed={$locale === item}
              onclick={() => setLocale(item)}
            >
              {getLocaleLabel(item)}
            </button>
          {/each}
        </div>
      </section>

      <section class="settings-section" aria-labelledby="auto-translate-title">
        <div class="section-icon"><Languages size={18} /></div>
        <div class="section-copy">
          <h2 id="auto-translate-title">{$translator("settings.autoTranslate")}</h2>
          <p>{$translator("settings.autoTranslateDescription")}</p>
        </div>
        <label class="toggle-control">
          <input
            type="checkbox"
            checked={$autoTranslate}
            onchange={(event) => setAutoTranslate((event.currentTarget as HTMLInputElement).checked)}
          />
          <span aria-hidden="true"></span>
          <b>{$translator($autoTranslate ? "common.enabled" : "common.disabled")}</b>
        </label>
      </section>

      <section class="settings-section" aria-labelledby="ai-translation-language-title">
        <div class="section-icon"><Languages size={18} /></div>
        <div class="section-copy">
          <h2 id="ai-translation-language-title">{$translator("settings.aiTranslationLanguage")}</h2>
          <p>{$translator("settings.aiTranslationLanguageDescription")}</p>
        </div>
        <select
          class="language-select"
          value={$aiTranslationLanguage}
          aria-label={$translator("settings.aiTranslationLanguage")}
          onchange={(event) => setAITranslationLanguage(
            (event.currentTarget as HTMLSelectElement).value as AITranslationPreference,
          )}
        >
          <option value="interface">{translationLanguageLabel("interface")}</option>
          {#each AI_TRANSLATION_LANGUAGES as item}
            <option value={item}>{translationLanguageLabel(item)}</option>
          {/each}
        </select>
      </section>

      <section class="settings-section theme-section" aria-labelledby="theme-title">
        <div class="section-icon"><Palette size={18} /></div>
        <div class="section-copy">
          <h2 id="theme-title">{$translator("common.theme")}</h2>
          <p>{$translator("settings.appearanceDescription")}</p>
        </div>
        <div class="theme-grid">
          {#each themes as item}
            <button
              type="button"
              class="theme-option theme-{item}"
              class:active={$theme === item}
              aria-pressed={$theme === item}
              onclick={() => setTheme(item)}
            >
              <span class="theme-swatch" aria-hidden="true">
                <span></span><span></span><span></span>
              </span>
              <span class="theme-option-copy">
                <strong>{themeTitle(item)}</strong>
                <small>{themeDescription(item)}</small>
              </span>
              <span class="theme-check"><Check size={14} /></span>
            </button>
          {/each}
        </div>
      </section>

      <section class="settings-section" aria-labelledby="color-mode-title">
        <div class="section-icon">
          {#if $colorMode === "light"}<SunIcon size={18} />{:else}<MoonIcon size={18} />{/if}
        </div>
        <div class="section-copy">
          <h2 id="color-mode-title">{$translator("common.colorMode")}</h2>
          <p>{$translator("settings.colorModeDescription")}</p>
        </div>
        <div class="segmented-control" aria-label={$translator("common.colorMode")}>
          {#each colorModes as item}
            <button
              type="button"
              class:active={$colorMode === item}
              aria-pressed={$colorMode === item}
              onclick={() => setColorMode(item)}
            >
              {#if item === "light"}<SunIcon size={14} />{:else}<MoonIcon size={14} />{/if}
              {$translator(`common.${item}`)}
            </button>
          {/each}
        </div>
      </section>

      <section class="settings-section layout-section" aria-labelledby="home-layout-title">
        <div class="section-icon">
          {#if $homeLayout === "split"}<Columns2Icon size={18} />{:else}<Rows3Icon size={18} />{/if}
        </div>
        <div class="section-copy">
          <h2 id="home-layout-title">{$translator("common.homeLayout")}</h2>
          <p>{$translator("settings.layoutDescription")}</p>
        </div>
        <div class="browse-grid">
          {#each homeLayouts as item}
            <button
              type="button"
              class="browse-option"
              class:active={$homeLayout === item}
              aria-pressed={$homeLayout === item}
              onclick={() => setHomeLayout(item)}
            >
              <span class="browse-diagram browse-{item}" aria-hidden="true">
                <i></i><i></i><i></i>
              </span>
              <span>
                <strong>{layoutTitle(item)}</strong>
                <small>{layoutDescription(item)}</small>
              </span>
              <span class="theme-check"><Check size={14} /></span>
            </button>
          {/each}
        </div>
        <p class="layout-note">{$translator("settings.largeScreenOnly")}</p>
      </section>

      <section class="settings-section" aria-labelledby="motion-title">
        <div class="section-icon"><Activity size={18} /></div>
        <div class="section-copy">
          <h2 id="motion-title">{$translator("common.motion")}</h2>
          <p>{$translator("settings.motionDescription")}</p>
        </div>
        <div class="segmented-control" aria-label={$translator("common.motion")}>
          {#each motions as item}
            <button
              type="button"
              class:active={$motion === item}
              aria-pressed={$motion === item}
              onclick={() => setMotion(item)}
            >
              {$translator(`common.${item}`)}
            </button>
          {/each}
        </div>
      </section>
    </div>

    <aside class="settings-preview">
      <span>{$translator("settings.preview")}</span>
      <div class="preview-window">
        <div class="preview-topbar">
          <i></i><i></i><i></i>
        </div>
        <div class="preview-content">
          <div class="preview-mark">A</div>
          <div>
            <h2>{$translator("settings.previewTitle")}</h2>
            <p>{$translator("settings.previewDescription")}</p>
          </div>
          <div class="preview-lines"><i></i><i></i><i></i></div>
        </div>
      </div>
    </aside>
  </div>
</div>

<style>
  .settings-shell { width:100%; }
  .settings-header { display:flex; align-items:end; justify-content:space-between; gap:2rem; padding:2.25rem 0 1.5rem; border-bottom:1px solid var(--vercel-border); }
  .settings-header > div > p, .settings-preview > span { color:var(--vercel-text-tertiary); font-size:.65rem; font-weight:650; text-transform:uppercase; }
  .settings-header h1 { margin-top:.25rem; font-size:clamp(2rem,5vw,3.5rem); line-height:1; letter-spacing:0; }
  .settings-lede { max-width:30rem; color:var(--vercel-text-secondary); font-size:.875rem; line-height:1.65; text-align:right; }
  .settings-layout { display:grid; grid-template-columns:minmax(0,1fr) minmax(17rem,23rem); gap:clamp(2rem,6vw,5rem); padding-top:1.75rem; }
  .settings-groups { display:grid; gap:0; }
  .settings-section { display:grid; grid-template-columns:2.5rem minmax(12rem,1fr) auto; gap:1rem; align-items:center; padding:1.35rem 0; border-bottom:1px solid var(--vercel-border); }
  .settings-section:first-child { border-top:1px solid var(--vercel-border); }
  .theme-section, .layout-section { grid-template-columns:2.5rem 1fr; align-items:start; }
  .section-icon { display:grid; width:2.25rem; height:2.25rem; place-items:center; border:1px solid var(--vercel-border); border-radius:var(--vercel-radius-sm); color:var(--vercel-text-secondary); }
  .section-copy h2 { font-size:.95rem; font-weight:600; letter-spacing:0; }
  .section-copy p { max-width:34rem; margin-top:.25rem; color:var(--vercel-text-tertiary); font-size:.75rem; line-height:1.55; }
  .segmented-control { display:flex; gap:.2rem; padding:.2rem; border:1px solid var(--vercel-border); border-radius:var(--vercel-radius-sm); background:var(--vercel-surface); }
  .segmented-control button { display:inline-flex; min-height:2rem; padding:0 .7rem; align-items:center; justify-content:center; gap:.35rem; border-radius:calc(var(--vercel-radius-sm) - 3px); color:var(--vercel-text-tertiary); font-size:.72rem; font-weight:600; white-space:nowrap; transition:background 160ms ease,color 160ms ease; }
  .segmented-control button.active { color:var(--vercel-text); background:var(--vercel-hover-strong); }
  .toggle-control { display:flex; align-items:center; gap:.55rem; color:var(--vercel-text-secondary); cursor:pointer; }
  .toggle-control input { position:absolute; width:1px; height:1px; overflow:hidden; opacity:0; }
  .toggle-control span { position:relative; display:block; width:2.25rem; height:1.25rem; border:1px solid var(--vercel-border-hover); border-radius:9999px; background:var(--vercel-surface); transition:background 150ms ease,border-color 150ms ease; }
  .toggle-control span::after { content:""; position:absolute; top:2px; left:2px; width:.875rem; height:.875rem; border-radius:50%; background:var(--vercel-text-tertiary); transition:transform 150ms ease,background 150ms ease; }
  .toggle-control input:checked + span { border-color:var(--vercel-text-secondary); background:var(--vercel-hover-strong); }
  .toggle-control input:checked + span::after { transform:translateX(1rem); background:var(--vercel-text); }
  .toggle-control input:focus-visible + span { outline:2px solid var(--vercel-ring); outline-offset:2px; }
  .toggle-control b { font-size:.7rem; font-weight:600; }
  .language-select {
    min-width: min(100%, 15rem);
    padding: 0.65rem 2.2rem 0.65rem 0.75rem;
    color: var(--vercel-text);
    background: var(--vercel-card);
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius-sm);
    font: inherit;
  }

  .theme-grid { grid-column:2; display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.6rem; margin-top:.2rem; }
  .theme-option { position:relative; display:grid; min-height:9.5rem; align-content:start; gap:.75rem; padding:.75rem; overflow:hidden; border:1px solid var(--vercel-border); border-radius:var(--vercel-radius); color:var(--vercel-text); text-align:left; transition:border-color 180ms ease,transform 180ms ease,background 180ms ease; }
  .theme-option:hover { transform:translateY(-1px); border-color:var(--vercel-border-hover); }
  .theme-option.active { border-color:var(--vercel-text-secondary); background:var(--vercel-hover); }
  .theme-swatch { display:flex; height:3.2rem; align-items:end; gap:.25rem; padding:.55rem; border-radius:calc(var(--vercel-radius) - 4px); }
  .theme-swatch span { display:block; width:.65rem; border-radius:2px; }
  .theme-swatch span:nth-child(1) { height:55%; }
  .theme-swatch span:nth-child(2) { height:80%; }
  .theme-swatch span:nth-child(3) { height:35%; }
  .theme-default .theme-swatch { background:#0c0c0e; border:1px solid rgba(255,255,255,.09); }
  .theme-default .theme-swatch span { background:#f5f5f5; }
  .theme-tiktok .theme-swatch { background:#0b0b10; border:1px solid #262838; }
  .theme-tiktok .theme-swatch span:nth-child(1) { background:#fe2c55; }
  .theme-tiktok .theme-swatch span:nth-child(2) { background:#f5f5f5; }
  .theme-tiktok .theme-swatch span:nth-child(3) { background:#25f4ee; }
  .theme-claude .theme-swatch { background:#faf9f5; border:1px solid #dad9d4; }
  .theme-claude .theme-swatch span:nth-child(1) { background:#c96442; }
  .theme-claude .theme-swatch span:nth-child(2) { background:#3d3929; }
  .theme-claude .theme-swatch span:nth-child(3) { background:#dad9d4; }
  .theme-apple .theme-swatch { background:#f5f5f7; border:1px solid #d1d1d6; }
  .theme-apple .theme-swatch span:nth-child(1) { background:#007aff; }
  .theme-apple .theme-swatch span:nth-child(2) { background:#1d1d1f; }
  .theme-apple .theme-swatch span:nth-child(3) { background:#aeaeb2; }
  .theme-google .theme-swatch { background:#ffffff; border:1px solid #ebebeb; }
  .theme-google .theme-swatch span:nth-child(1) { background:#4285f4; }
  .theme-google .theme-swatch span:nth-child(2) { background:#ea4335; }
  .theme-google .theme-swatch span:nth-child(3) { background:#34a853; }
  .theme-option-copy { display:grid; gap:.25rem; }
  .theme-option-copy strong { font-size:.78rem; font-weight:650; }
  .theme-option-copy small { color:var(--vercel-text-tertiary); font-size:.66rem; line-height:1.45; }
  .theme-check { position:absolute; top:.5rem; right:.5rem; display:grid; width:1.25rem; height:1.25rem; place-items:center; border-radius:50%; color:var(--vercel-bg); background:var(--vercel-text); opacity:0; transform:scale(.7); transition:opacity 150ms ease,transform 150ms ease; }
  .theme-option.active .theme-check { opacity:1; transform:scale(1); }
  .browse-grid { grid-column:2; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.6rem; margin-top:.2rem; }
  .browse-option { position:relative; display:grid; grid-template-columns:5.5rem minmax(0,1fr); gap:.8rem; align-items:center; min-height:6.5rem; padding:.75rem; overflow:hidden; border:1px solid var(--vercel-border); border-radius:var(--vercel-radius); color:var(--vercel-text); text-align:left; transition:border-color 180ms ease,transform 180ms ease,background 180ms ease; }
  .browse-option:hover { transform:translateY(-1px); border-color:var(--vercel-border-hover); }
  .browse-option.active { border-color:var(--vercel-text-secondary); background:var(--vercel-hover); }
  .browse-option.active .theme-check { opacity:1; transform:scale(1); }
  .browse-option strong { display:block; font-size:.78rem; font-weight:650; }
  .browse-option small { display:block; margin-top:.25rem; color:var(--vercel-text-tertiary); font-size:.66rem; line-height:1.45; }
  .browse-diagram { display:grid; width:5.5rem; height:3.75rem; gap:.25rem; padding:.4rem; border:1px solid var(--vercel-border); border-radius:calc(var(--vercel-radius) - 4px); background:var(--vercel-surface); }
  .browse-diagram i { display:block; border-radius:2px; background:var(--vercel-border-hover); }
  .browse-split { grid-template-columns:1fr 1.6fr; grid-template-rows:1fr 1fr; }
  .browse-split i:first-child { grid-row:1 / 3; }
  .browse-pages { grid-template-columns:1fr; grid-template-rows:repeat(3,1fr); }
  .layout-note { grid-column:2; margin-top:.1rem; color:var(--vercel-text-tertiary); font-size:.67rem; line-height:1.5; }
  .settings-preview { position:sticky; top:5rem; align-self:start; }
  .preview-window { margin-top:.6rem; overflow:hidden; border:1px solid var(--vercel-border); border-radius:var(--vercel-radius-lg); background:var(--vercel-card); box-shadow:0 18px 50px rgba(0,0,0,.12); }
  .preview-topbar { display:flex; gap:.3rem; padding:.65rem .75rem; border-bottom:1px solid var(--vercel-border); }
  .preview-topbar i { width:.38rem; height:.38rem; border-radius:50%; background:var(--vercel-text-tertiary); opacity:.45; }
  .preview-content { display:grid; gap:1rem; padding:1.5rem; }
  .preview-mark { display:grid; width:2.5rem; height:2.5rem; place-items:center; border-radius:var(--vercel-radius-sm); color:var(--vercel-bg); background:var(--vercel-accent); font-size:1rem; font-weight:700; }
  .preview-content h2 { font-size:1.2rem; letter-spacing:0; }
  .preview-content p { margin-top:.4rem; color:var(--vercel-text-tertiary); font-size:.72rem; line-height:1.55; }
  .preview-lines { display:grid; gap:.45rem; padding-top:.5rem; }
  .preview-lines i { display:block; height:.45rem; border-radius:3px; background:var(--vercel-border); }
  .preview-lines i:nth-child(1) { width:92%; }
  .preview-lines i:nth-child(2) { width:78%; }
  .preview-lines i:nth-child(3) { width:58%; }
  @media (max-width:56rem) {
    .settings-layout { grid-template-columns:1fr; }
    .settings-preview { position:static; }
  }
  @media (max-width:42rem) {
    .settings-header { align-items:start; flex-direction:column; gap:.75rem; }
    .settings-lede { text-align:left; }
    .settings-section { grid-template-columns:2.5rem 1fr; }
    .segmented-control { grid-column:1 / -1; width:100%; overflow-x:auto; }
    .segmented-control button { flex:1; }
    .theme-grid { grid-column:1 / -1; grid-template-columns:1fr; }
    .theme-option { min-height:0; grid-template-columns:5rem 1fr; align-items:center; }
    .browse-grid { grid-column:1 / -1; grid-template-columns:1fr; }
    .layout-note { grid-column:1 / -1; }
  }
</style>
