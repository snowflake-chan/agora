<script lang="ts">
  import { FileTextIcon, LanguagesIcon, SparklesIcon } from "@lucide/svelte";
  import { onMount } from "svelte";
  import {
    AiRequestError,
    getAiStatus,
    summarizeText,
    translateFields,
    type TranslationContext,
  } from "../../lib/ai";
  import { ApiError } from "../../lib/auth";
  import { locale, translateError, translator, type Locale } from "../../lib/i18n";
  import { requestLogin } from "../../lib/login";
  import { dispatchModerationUpdate } from "../../lib/moderation";
  import { autoTranslate, initPreferences } from "../../lib/preferences";
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
  } = $props();

  type Tool = "summary" | "translation";
  type Notice = "political" | "outputBlocked" | "reviewPending" | "error" | null;
  type LocalizedOutput = { locale: Locale; text: string };
  type LocalizedTranslation = {
    locale: Locale;
    title: string | null;
    body: string;
    cached: boolean;
  };

  let enabled = $state(false);
  let loading = $state<Tool | null>(null);
  let active = $state<Tool | null>(null);
  let summary = $state<LocalizedOutput | null>(null);
  let translation = $state<LocalizedTranslation | null>(null);
  let notice = $state<Notice>(null);
  let errorMessage = $state<string | null>(null);
  let cachedLocale = $state<Locale>($locale);
  let visible = $state(false);
  let autoSignature = $state("");
  let sourceText = $derived(title?.trim() ? `${title.trim()}\n\n${text}` : text);
  let sourceReference = $derived(
    sourceContentId && sourceRevisionNumber && sourceRevisionNumber > 0
      ? { contentId: sourceContentId, revisionNumber: sourceRevisionNumber }
      : null,
  );

  $effect(() => {
    const nextLocale = $locale;
    if (nextLocale === cachedLocale) return;
    cachedLocale = nextLocale;
    summary = null;
    translation = null;
    active = null;
    notice = null;
    errorMessage = null;
  });

  $effect(() => {
    if (!enabled || !visible || !$autoTranslate || !$currentUser) return;
    const signature = `${$locale}:${context}:${title ?? ""}:${text}`;
    if (autoSignature === signature) return;
    autoSignature = signature;
    void runTranslation();
  });

  onMount(async () => {
    initPreferences();
    enabled = (await getAiStatus()).enabled;
  });

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
    if (!$currentUser) {
      requestLogin(undefined, () => void runTranslation());
      return;
    }
    if (active === "translation" && translation?.locale === $locale) {
      active = null;
      return;
    }
    notice = null;
    errorMessage = null;
    active = "translation";
    const targetLocale = $locale;
    if (translation?.locale === targetLocale) return;
    loading = "translation";
    try {
      const fields = [
        ...(title?.trim() ? [{ key: "title", text: title.trim() }] : []),
        { key: "body", text },
      ];
      const output = await translateFields(fields, targetLocale, context, sourceReference);
      const translatedTitle = output.fields.find((field) => field.key === "title")?.translation ?? null;
      const translatedBody = output.fields.find((field) => field.key === "body")?.translation;
      if (!translatedBody) throw new ApiError("AI_RESPONSE_INVALID");
      if ($locale === targetLocale) {
        translation = {
          locale: targetLocale,
          title: translatedTitle,
          body: translatedBody,
          cached: output.cached,
        };
      }
    } catch (error) {
      handleError(error);
    } finally {
      loading = null;
    }
  }
</script>

{#if enabled}
  <section use:trackVisibility class:compact class="ai-tools" aria-label={$translator("ai.tools")}>
    <div class="ai-toolbar">
      <span class="ai-toolbar-label" class:visually-compact={compact || translationOnly}>
        <SparklesIcon size={14} strokeWidth={1.8} aria-hidden="true" />
        {$translator("ai.tools")}
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
            onclick={runSummary}
          >
            <FileTextIcon size={14} strokeWidth={1.8} aria-hidden="true" />
            {$translator(active === "summary" && summary?.locale === $locale ? "ai.hideResult" : "ai.summarize")}
          </button>
        {/if}
        <button
          type="button"
          class:active={active === "translation"}
          class="ai-tool"
          disabled={loading !== null}
          aria-pressed={active === "translation"}
          aria-expanded={active === "translation" && translation?.locale === $locale}
          onclick={runTranslation}
        >
          <LanguagesIcon size={14} strokeWidth={1.8} aria-hidden="true" />
          {$translator(active === "translation" && translation?.locale === $locale ? "ai.hideResult" : "ai.translate")}
        </button>
      </div>
    </div>
    {#if !compact}
      <p class="ai-disclosure">{$translator("ai.externalProcessing")}</p>
    {/if}

    {#if loading}
      <p class="ai-status" aria-live="polite">{$translator("common.processing")}</p>
    {:else if notice === "political"}
      <p class="ai-notice" role="status">{$translator("ai.politicalUnavailable")}</p>
    {:else if notice === "outputBlocked"}
      <p class="ai-notice" role="status">{$translator("ai.outputBlocked")}</p>
    {:else if notice === "reviewPending"}
      <p class="ai-notice" role="status">{$translator("ai.reviewPendingDescription")}</p>
    {:else if notice === "error"}
      <p class="ai-notice" role="status">{errorMessage ?? $translator("ai.failed")}</p>
    {:else if active === "summary" && summary?.locale === $locale}
      <section class="ai-output" aria-label={$translator("ai.summary")} aria-live="polite">
        <p>{summary.text}</p>
        {#if !compact}<small>{$translator("ai.outputNote")}</small>{/if}
      </section>
    {:else if active === "translation" && translation?.locale === $locale}
      <section class="ai-output" aria-label={$translator("ai.translation")} aria-live="polite">
        {#if translation.title}<h4>{translation.title}</h4>{/if}
        <p>{translation.body}</p>
        {#if !compact}<small>{$translator("ai.outputNote")}</small>{/if}
      </section>
    {/if}
  </section>
{/if}

<style>
  .ai-tools {
    margin-top: 1rem;
    padding-top: 0.8rem;
    border-top: 1px solid var(--vercel-border);
  }

  .ai-tools.compact {
    margin-top: 0.7rem;
    padding-top: 0.55rem;
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
    justify-content: space-between;
    gap: 0.75rem;
  }

  .ai-toolbar-label {
    gap: 0.35rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0;
  }

  .ai-toolbar-actions {
    gap: 0.3rem;
  }

  .ai-tool {
    min-height: 2rem;
    gap: 0.35rem;
    padding: 0.35rem 0.55rem;
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
    opacity: 0.55;
  }

  .ai-status,
  .ai-notice,
  .ai-output {
    margin: 0.7rem 0 0;
    color: var(--vercel-text-secondary);
    font-size: 0.8125rem;
    line-height: 1.55;
  }

  .ai-disclosure {
    margin: 0.45rem 0 0;
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
    line-height: 1.45;
  }

  .ai-notice {
    color: var(--vercel-warning);
  }

  .ai-output {
    padding-left: 0.8rem;
    border-left: 2px solid var(--vercel-border-hover);
    animation: ai-output-in 180ms ease-out;
  }

  .ai-output p {
    margin: 0;
    white-space: pre-wrap;
  }

  .ai-output h4 {
    margin: 0 0 0.55rem;
    color: var(--vercel-text);
    font-size: 0.875rem;
    font-weight: 650;
  }

  .ai-output small {
    display: block;
    margin-top: 0.55rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
  }

  @keyframes ai-output-in {
    from { opacity: 0; transform: translateY(-0.2rem); }
    to { opacity: 1; transform: translateY(0); }
  }

  @media (max-width: 24rem) {
    .ai-toolbar {
      align-items: flex-start;
      flex-direction: column;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .ai-output { animation: none; }
  }

  :global(html[data-motion="reduced"]) .ai-output {
    animation: none;
  }
</style>
