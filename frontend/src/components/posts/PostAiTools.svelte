<script lang="ts">
  import { FileTextIcon, LanguagesIcon, SparklesIcon } from "@lucide/svelte";
  import { onMount } from "svelte";
  import { getAiStatus, summarizeText, translateText } from "../../lib/ai";
  import { ApiError } from "../../lib/auth";
  import { locale, translateError, translator, type Locale } from "../../lib/i18n";
  import { requestLogin } from "../../lib/login";
  import { currentUser } from "../../stores/auth";

  let { text }: { text: string } = $props();

  type Tool = "summary" | "translation";
  type Notice = "political" | "error" | null;
  type LocalizedOutput = { locale: Locale; text: string };

  let enabled = $state(false);
  let loading = $state<Tool | null>(null);
  let active = $state<Tool | null>(null);
  let summary = $state<LocalizedOutput | null>(null);
  let translation = $state<LocalizedOutput | null>(null);
  let notice = $state<Notice>(null);
  let errorMessage = $state<string | null>(null);
  let cachedLocale = $state<Locale>($locale);

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

  onMount(async () => {
    enabled = (await getAiStatus()).enabled;
  });

  function handleError(error: unknown) {
    const code = error instanceof ApiError ? error.code : "AI_REQUEST_FAILED";
    notice = code === "POLITICAL_CONTENT_UNAVAILABLE" ? "political" : "error";
    errorMessage = notice === "error" ? translateError(error, $translator, "ai.failed") : null;
    active = null;
  }

  async function runSummary() {
    if (!$currentUser) {
      requestLogin(undefined, () => void runSummary());
      return;
    }
    notice = null;
    errorMessage = null;
    active = "summary";
    const targetLocale = $locale;
    if (summary?.locale === targetLocale) return;
    loading = "summary";
    try {
      const output = await summarizeText(text, targetLocale);
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
    notice = null;
    errorMessage = null;
    active = "translation";
    const targetLocale = $locale;
    if (translation?.locale === targetLocale) return;
    loading = "translation";
    try {
      const output = await translateText(text, targetLocale);
      if ($locale === targetLocale) translation = { locale: targetLocale, text: output };
    } catch (error) {
      handleError(error);
    } finally {
      loading = null;
    }
  }
</script>

{#if enabled}
  <section class="ai-tools" aria-label={$translator("ai.tools")}>
    <div class="ai-toolbar">
      <span class="ai-toolbar-label">
        <SparklesIcon size={14} strokeWidth={1.8} aria-hidden="true" />
        {$translator("ai.tools")}
      </span>
      <div class="ai-toolbar-actions">
        <button
          type="button"
          class:active={active === "summary"}
          class="ai-tool"
          disabled={loading !== null}
          aria-pressed={active === "summary"}
          onclick={runSummary}
        >
          <FileTextIcon size={14} strokeWidth={1.8} aria-hidden="true" />
          {$translator("ai.summarize")}
        </button>
        <button
          type="button"
          class:active={active === "translation"}
          class="ai-tool"
          disabled={loading !== null}
          aria-pressed={active === "translation"}
          onclick={runTranslation}
        >
          <LanguagesIcon size={14} strokeWidth={1.8} aria-hidden="true" />
          {$translator("ai.translate")}
        </button>
      </div>
    </div>
    <p class="ai-disclosure">{$translator("ai.externalProcessing")}</p>

    {#if loading}
      <p class="ai-status" aria-live="polite">{$translator("common.processing")}</p>
    {:else if notice === "political"}
      <p class="ai-notice" role="status">{$translator("ai.politicalUnavailable")}</p>
    {:else if notice === "error"}
      <p class="ai-notice" role="status">{errorMessage ?? $translator("ai.failed")}</p>
    {:else if active === "summary" && summary?.locale === $locale}
      <details class="ai-output" open>
        <summary>{$translator("ai.summary")}</summary>
        <p>{summary.text}</p>
        <small>{$translator("ai.outputNote")}</small>
      </details>
    {:else if active === "translation" && translation?.locale === $locale}
      <details class="ai-output" open>
        <summary>{$translator("ai.translation")}</summary>
        <p>{translation.text}</p>
        <small>{$translator("ai.outputNote")}</small>
      </details>
    {/if}
  </section>
{/if}

<style>
  .ai-tools {
    margin-top: 1rem;
    padding-top: 0.8rem;
    border-top: 1px solid var(--vercel-border);
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
  }

  .ai-output summary {
    cursor: pointer;
    color: var(--vercel-text);
    font-weight: 600;
  }

  .ai-output p {
    margin: 0.55rem 0 0;
    white-space: pre-wrap;
  }

  .ai-output small {
    display: block;
    margin-top: 0.55rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
  }

  @media (max-width: 24rem) {
    .ai-toolbar {
      align-items: flex-start;
      flex-direction: column;
    }
  }
</style>
