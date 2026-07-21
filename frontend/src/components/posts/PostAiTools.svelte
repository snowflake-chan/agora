<script lang="ts">
  import { FileTextIcon, LanguagesIcon, LoaderCircleIcon, SparklesIcon } from "@lucide/svelte";
  import { onMount } from "svelte";
  import {
    AiRequestError,
    getAiStatus,
    refreshAiStatus,
    summarizeText,
    translateFields,
    type DisplayTranslation,
    type TranslationContext,
  } from "../../lib/ai";
  import { ApiError } from "../../lib/auth";
  import { locale, translateError, translator, type Locale } from "../../lib/i18n";
  import { shouldRequestTranslation } from "../../lib/language";
  import { requestLogin } from "../../lib/login";
  import { dispatchModerationUpdate } from "../../lib/moderation";
  import {
    aiTranslationLanguage,
    autoTranslate,
    initPreferences,
    resolveAITranslationLanguage,
  } from "../../lib/preferences";
  import { currentUser } from "../../stores/auth";
  import { toaster } from "../../stores/toaster";

  let {
    text,
    title = null,
    context = "post",
    compact = false,
    translationOnly = false,
    sourceContentId = null,
    sourceRevisionNumber = null,
    moderationTargetHref = null,
    onModerationQueued = null,
    onTranslationChange = null,
  }: {
    text: string;
    title?: string | null;
    context?: TranslationContext;
    compact?: boolean;
    translationOnly?: boolean;
    sourceContentId?: string | null;
    sourceRevisionNumber?: number | null;
    moderationTargetHref?: string | null;
    onModerationQueued?: (() => void) | null;
    onTranslationChange?: ((translation: DisplayTranslation | null) => void) | null;
  } = $props();

  type Tool = "summary" | "translation";
  type Availability = "checking" | "enabled" | "unavailable";
  type Notice = "political" | "outputBlocked" | "reviewPending" | "error" | null;
  type LocalizedOutput = { locale: Locale; text: string };
  let availability = $state<Availability>("checking");
  let availabilitySequence = 0;
  let loading = $state<Tool | null>(null);
  let active = $state<Tool | null>(null);
  let summary = $state<LocalizedOutput | null>(null);
  let translation = $state<DisplayTranslation | null>(null);
  let translationVisible = $state(false);
  let notice = $state<Notice>(null);
  let errorMessage = $state<string | null>(null);
  let cachedLocale = $state<Locale>($locale);
  let cachedTranslationLocale = $state(resolveAITranslationLanguage($aiTranslationLanguage, $locale));
  let visible = $state(false);
  let autoSignature = $state("");
  let sourceText = $derived(title?.trim() ? `${title.trim()}\n\n${text}` : text);
  let translationFields = $derived([
    ...(title?.trim() ? [{ key: "title", text: title.trim() }] : []),
    { key: "body", text },
  ]);
  let translationTarget = $derived(resolveAITranslationLanguage($aiTranslationLanguage, $locale));
  let translationNeeded = $derived(shouldRequestTranslation(translationFields, translationTarget));
  let sourceReference = $derived(
    sourceContentId && sourceRevisionNumber && sourceRevisionNumber > 0
      ? { contentId: sourceContentId, revisionNumber: sourceRevisionNumber }
      : null,
  );

  $effect(() => {
    const nextLocale = $locale;
    const nextTranslationLocale = translationTarget;
    if (nextLocale !== cachedLocale) {
      cachedLocale = nextLocale;
      summary = null;
      if (active === "summary") active = null;
    }
    if (nextTranslationLocale !== cachedTranslationLocale) {
      cachedTranslationLocale = nextTranslationLocale;
      translation = null;
      translationVisible = false;
      if (active === "translation") active = null;
      onTranslationChange?.(null);
    }
    notice = null;
    errorMessage = null;
  });

  $effect(() => {
    if (
      availability !== "enabled"
      || !visible
      || !$autoTranslate
      || !$currentUser
      || !translationNeeded
    ) return;
    const signature = `${translationTarget}:${context}:${title ?? ""}:${text}`;
    if (autoSignature === signature) return;
    autoSignature = signature;
    void runTranslation();
  });

  onMount(async () => {
    initPreferences();
    await loadAvailability();
    if (availability === "enabled" && $currentUser && translationNeeded && remembersTranslation()) {
      void runTranslation();
    }
  });

  async function loadAvailability(forceRefresh = false) {
    const sequence = ++availabilitySequence;
    availability = "checking";
    try {
      const status = await (forceRefresh ? refreshAiStatus() : getAiStatus());
      if (sequence === availabilitySequence) {
        availability = status.enabled ? "enabled" : "unavailable";
      }
    } catch {
      if (sequence === availabilitySequence) availability = "unavailable";
    }
  }

  function trackVisibility(node: HTMLElement) {
    if (typeof IntersectionObserver === "undefined") {
      visible = true;
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => visible = Boolean(entry?.isIntersecting),
      { rootMargin: "64px" },
    );
    observer.observe(node);
    return { destroy: () => observer.disconnect() };
  }

  function translationMemoryKey() {
    if (!sourceReference) return null;
    return ["agora:translation", context, sourceReference.contentId, sourceReference.revisionNumber, translationTarget].join(":");
  }

  function remembersTranslation() {
    const key = translationMemoryKey();
    if (!key) return false;
    try { return localStorage.getItem(key) === "visible"; } catch { return false; }
  }

  function rememberTranslation(visible: boolean) {
    const key = translationMemoryKey();
    if (!key) return;
    try {
      if (visible) localStorage.setItem(key, "visible");
      else localStorage.removeItem(key);
    } catch {}
  }

  function handleError(error: unknown) {
    const code = error instanceof ApiError ? error.code : "AI_REQUEST_FAILED";
    const moderationUpdate = error instanceof AiRequestError
      ? error.moderationUpdate
      : null;
    if (
      moderationUpdate
      && sourceContentId
      && moderationUpdate.contentId === sourceContentId
    ) {
      notice = "reviewPending";
      errorMessage = null;
      toaster.info(
        $translator("ai.reviewPendingTitle"),
        $translator("ai.reviewPendingDescription"),
      );
      onModerationQueued?.();
      const targetHref = moderationUpdate.targetHref ?? moderationTargetHref;
      if (targetHref) {
        dispatchModerationUpdate({
          type: "moderation_pending",
          link: targetHref,
          contentId: moderationUpdate.contentId,
        });
      }
    } else if (code === "POLITICAL_CONTENT_UNAVAILABLE") {
      notice = "political";
      errorMessage = null;
    } else if (code === "AI_OUTPUT_BLOCKED" || code === "AI_PROVIDER_FILTERED") {
      notice = "outputBlocked";
      errorMessage = null;
    } else {
      notice = "error";
      errorMessage = translateError(error, $translator, "ai.failed");
    }
    active = null;
  }

  async function runSummary() {
    if (!$currentUser) {
      requestLogin(undefined, () => void runSummary());
      return;
    }
    if (active === "summary" && summary?.locale === $locale) {
      active = null;
      return;
    }
    notice = null;
    errorMessage = null;
    active = "summary";
    const targetLocale = $locale;
    if (summary?.locale === targetLocale) return;
    loading = "summary";
    try {
      const output = await summarizeText(sourceText, targetLocale);
      if ($locale === targetLocale) summary = { locale: targetLocale, text: output };
    } catch (error) {
      handleError(error);
    } finally {
      loading = null;
    }
  }

  async function runTranslation() {
    if (!translationNeeded) return;
    if (!$currentUser) {
      requestLogin(undefined, () => void runTranslation());
      return;
    }
    if (translation?.locale === translationTarget) {
      translationVisible = true;
      onTranslationChange?.(translation);
      return;
    }
    notice = null;
    errorMessage = null;
    active = "translation";
    const targetLocale = translationTarget;
    if (translation?.locale === targetLocale) return;
    loading = "translation";
    try {
      const streamed = new Map<string, string>();
      const output = await translateFields(
        translationFields,
        targetLocale,
        context,
        sourceReference,
        (field) => {
          streamed.set(field.key, field.translation);
          const streamedBody = streamed.get("body");
          if (!streamedBody || translationTarget !== targetLocale) return;
          const nextTranslation: DisplayTranslation = {
            locale: targetLocale,
            title: streamed.get("title") ?? null,
            body: streamedBody,
            cached: false,
          };
          translation = nextTranslation;
          translationVisible = true;
          onTranslationChange?.(nextTranslation);
        },
      );
      if (output.skipped) {
        active = null;
        return;
      }
      const translatedTitle = output.fields.find((field) => field.key === "title")?.translation ?? null;
      const translatedBody = output.fields.find((field) => field.key === "body")?.translation;
      if (!translatedBody) throw new ApiError("AI_RESPONSE_INVALID");
      if (translationTarget === targetLocale) {
        const nextTranslation: DisplayTranslation = {
          locale: targetLocale,
          title: translatedTitle,
          body: translatedBody,
          cached: output.cached,
        };
        translation = nextTranslation;
        translationVisible = true;
        onTranslationChange?.(nextTranslation);
      }
    } catch (error) {
      handleError(error);
    } finally {
      loading = null;
    }
  }

  function toggleTranslation() {
    if (!translation) return;
    translationVisible = !translationVisible;
    onTranslationChange?.(translationVisible ? translation : null);
    rememberTranslation(translationVisible);
  }
</script>

{#if availability === "enabled" && (!translationOnly || translationNeeded || translation)}
  <section use:trackVisibility class:compact class="ai-tools" aria-label={$translator("ai.tools")}>
    {#if !translationOnly || (translationNeeded && !translation)}
      <div class="ai-toolbar">
        <span class="ai-toolbar-label" class:visually-compact={compact || translationOnly}>
          <SparklesIcon size={14} strokeWidth={1.8} aria-hidden="true" />
          {$translator("ai.label")}
        </span>
        <div class="ai-toolbar-actions">
          {#if !translationOnly}
            <button
              type="button"
              class:active={active === "summary"}
              class="ai-tool"
              disabled={loading !== null}
              aria-pressed={active === "summary"}
              aria-expanded={active === "summary" && summary?.locale === $locale}
              aria-busy={loading === "summary"}
              title={$translator("ai.summarize")}
              onclick={runSummary}
            >
              {#if loading === "summary"}
                <LoaderCircleIcon class="loading-icon" size={14} strokeWidth={1.8} aria-hidden="true" />
              {:else}
                <FileTextIcon size={14} strokeWidth={1.8} aria-hidden="true" />
              {/if}
              {$translator(
                loading === "summary"
                  ? "common.processing"
                  : active === "summary" && summary?.locale === $locale
                    ? "ai.hideResult"
                    : "ai.summarize",
              )}
            </button>
          {/if}
          {#if translationNeeded && !translation}
            <button
              type="button"
              class="ai-tool"
              disabled={loading !== null}
              aria-busy={loading === "translation"}
              title={$translator("ai.translate")}
              onclick={runTranslation}
            >
              {#if loading === "translation"}
                <LoaderCircleIcon class="loading-icon" size={14} strokeWidth={1.8} aria-hidden="true" />
              {:else}
                <LanguagesIcon size={14} strokeWidth={1.8} aria-hidden="true" />
              {/if}
              {$translator(loading === "translation" ? "common.processing" : "ai.translate")}
            </button>
          {/if}
        </div>
      </div>
    {/if}

    {#if notice === "political"}
      <p class="ai-feedback warning" role="status">{$translator("ai.politicalUnavailable")}</p>
    {:else if notice === "outputBlocked"}
      <p class="ai-feedback warning" role="status">{$translator("ai.outputBlocked")}</p>
    {:else if notice === "reviewPending"}
      <p class="ai-feedback warning" role="status">{$translator("ai.reviewPendingDescription")}</p>
    {:else if notice === "error"}
      <p class="ai-feedback warning" role="status">{errorMessage ?? $translator("ai.failed")}</p>
    {/if}

    {#if active === "summary" && summary?.locale === $locale}
      <section class="ai-result" aria-label={$translator("ai.summary")} aria-live="polite">
        <div class="ai-result-heading">
          <FileTextIcon size={13} strokeWidth={1.8} aria-hidden="true" />
          <span>{$translator("ai.summary")}</span>
        </div>
        <div class="ai-result-copy"><p>{summary.text}</p></div>
        {#if !compact}<small>{$translator("ai.outputNote")}</small>{/if}
      </section>
    {/if}

    {#if translation?.locale === translationTarget}
      <div class="translation-status" aria-live="polite">
        <span>
          <LanguagesIcon size={12} strokeWidth={1.8} aria-hidden="true" />
          {$translator("ai.translatedByAi")}
        </span>
        <button
          type="button"
          class="translation-toggle"
          aria-pressed={!translationVisible}
          onclick={toggleTranslation}
        >
          {$translator(translationVisible ? "ai.viewOriginal" : "ai.viewTranslation")}
        </button>
      </div>
    {/if}
  </section>
{:else if availability === "unavailable" && !compact && (!translationOnly || translationNeeded)}
  <div class="ai-retry-row">
    <button type="button" class="ai-retry" onclick={() => void loadAvailability(true)}>
      <SparklesIcon size={14} strokeWidth={1.8} aria-hidden="true" />
      {$translator("ai.retry")}
    </button>
  </div>
{/if}

<style>
  .ai-tools {
    min-width: 0;
    margin-top: 0.65rem;
  }

  .ai-tools.compact {
    margin-top: 0.45rem;
  }

  .ai-toolbar-label.visually-compact {
    width: 1px;
    height: 1px;
    overflow: hidden;
    position: absolute;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
  }

  .ai-toolbar,
  .ai-toolbar-actions,
  .ai-toolbar-label,
  .ai-tool {
    display: flex;
    align-items: center;
  }

  .ai-toolbar {
    min-height: 2rem;
    gap: 0.35rem;
  }

  .ai-toolbar-label {
    gap: 0.35rem;
    padding-right: 0.35rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
    font-weight: 650;
    letter-spacing: 0;
  }

  .ai-toolbar-actions {
    gap: 0.3rem;
  }

  .ai-tool {
    min-height: 1.9rem;
    gap: 0.35rem;
    padding: 0.3rem 0.48rem;
    border-radius: var(--vercel-radius-sm);
    color: var(--vercel-text-secondary);
    background: transparent;
    cursor: pointer;
    font: inherit;
    font-size: 0.75rem;
    font-weight: 600;
    transition: color 150ms ease, background-color 150ms ease;
  }

  .ai-tool:not(:disabled):hover,
  .ai-tool.active {
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .ai-tool:focus-visible {
    outline: 2px solid var(--vercel-ring);
    outline-offset: 2px;
  }

  .ai-tool:disabled {
    cursor: wait;
    opacity: 0.6;
  }

  .ai-feedback {
    max-width: 46rem;
    margin: 0.4rem 0 0;
    color: var(--vercel-text-tertiary);
    font-size: 0.72rem;
    line-height: 1.5;
  }

  .ai-feedback.warning {
    color: var(--vercel-warning);
  }

  .ai-result {
    max-width: 46rem;
    margin-top: 0.45rem;
    padding-left: 0.65rem;
    border-left: 1px solid var(--vercel-border-hover);
  }

  .ai-result-heading {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.65rem;
    font-weight: 600;
  }

  .ai-result-copy {
    margin-top: 0.3rem;
    color: var(--vercel-text-secondary);
    font-size: 0.775rem;
    line-height: 1.55;
  }

  .ai-result-copy p {
    margin: 0;
    white-space: pre-wrap;
  }

  .ai-result-copy h4 {
    margin: 0 0 0.4rem;
    color: var(--vercel-text);
    font-size: 0.8125rem;
    font-weight: 650;
  }

  .ai-result small {
    display: block;
    margin-top: 0.35rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.65rem;
    line-height: 1.4;
  }

  .translation-status,
  .translation-status > span,
  .translation-toggle {
    display: inline-flex;
    align-items: center;
  }

  .translation-status {
    min-height: 1.75rem;
    gap: 0.45rem;
    margin-top: 0.3rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
  }

  .translation-status > span {
    gap: 0.3rem;
  }

  .translation-toggle {
    min-height: 1.75rem;
    padding: 0 0.25rem;
    border-radius: var(--vercel-radius-sm);
    color: var(--vercel-text-secondary);
    background: transparent;
    font: inherit;
    font-weight: 600;
    cursor: pointer;
  }

  .translation-toggle:hover {
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .translation-toggle:focus-visible {
    outline: 2px solid var(--vercel-ring);
    outline-offset: 1px;
  }

  .loading-icon {
    animation: ai-spin 800ms linear infinite;
  }

  .ai-retry-row {
    margin-top: 0.65rem;
  }

  .ai-retry {
    display: inline-flex;
    min-height: 1.9rem;
    align-items: center;
    gap: 0.35rem;
    padding: 0.3rem 0.48rem;
    border-radius: var(--vercel-radius-sm);
    color: var(--vercel-text-tertiary);
    background: transparent;
    font-size: 0.72rem;
    font-weight: 600;
  }

  .ai-retry:hover,
  .ai-retry:focus-visible {
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .ai-retry:focus-visible {
    outline: 2px solid var(--vercel-ring);
    outline-offset: 2px;
  }

  @keyframes ai-spin {
    to { transform: rotate(360deg); }
  }

  @media (max-width: 24rem) {
    .ai-toolbar-actions { min-width: 0; flex-wrap: wrap; }
  }

  @media (prefers-reduced-motion: reduce) {
    .loading-icon { animation: none; }
  }

  :global(html[data-motion="reduced"]) .loading-icon {
    animation: none;
  }
</style>
