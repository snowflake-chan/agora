<script lang="ts">
  import {
    CheckIcon,
    ChevronDownIcon,
    LoaderCircleIcon,
    SparklesIcon,
    XIcon,
  } from "@lucide/svelte";
  import { onMount } from "svelte";
  import {
    assistWriting,
    getAiStatus,
    refreshAiStatus,
    type TranslationContext,
    type WritingAction,
  } from "../../lib/ai";
  import {
    createAiInputSignature,
    getWritingAssistReadiness,
    isCurrentAiResult,
    WRITING_ASSIST_MIN_BODY_LENGTH,
  } from "../../lib/ai-ui";
  import { ApiError } from "../../lib/auth";
  import { locale, translateError, translator } from "../../lib/i18n";

  let {
    title = "",
    body,
    context = "composer",
    onApply,
  }: {
    title?: string;
    body: string;
    context?: TranslationContext;
    onApply: (value: { title: string; body: string }) => void;
  } = $props();

  const instanceId = $props.id();
  const panelId = `${instanceId}-panel`;
  const requirementId = `${instanceId}-requirement`;

  type Availability = "checking" | "enabled" | "unavailable";

  let availability = $state<Availability>("checking");
  let open = $state(false);
  let triggerElement = $state<HTMLButtonElement | null>(null);
  let action = $state<WritingAction>("polish");
  let loading = $state(false);
  let suggestedTitle = $state("");
  let suggestedBody = $state("");
  let suggestionSignature = $state("");
  let staleResult = $state(false);
  let error = $state<string | null>(null);
  let availabilitySequence = 0;
  let requestSequence = 0;
  let readiness = $derived(getWritingAssistReadiness(body));
  let inputSignature = $derived(createAiInputSignature([
    title.trim(),
    body.trim(),
    $locale,
    action,
  ]));
  let canRun = $derived(availability === "enabled" && readiness.ready && !loading);
  let hasSuggestion = $derived(Boolean(suggestedBody));

  onMount(() => {
    void loadAvailability();
  });

  $effect(() => {
    const currentSignature = inputSignature;
    if (!suggestedBody || !suggestionSignature || suggestionSignature === currentSignature) return;
    suggestedTitle = "";
    suggestedBody = "";
    suggestionSignature = "";
    staleResult = true;
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

  function toggleOpen() {
    if (open) {
      closePanel(false);
      return;
    }
    open = true;
  }

  function closePanel(restoreFocus = true) {
    open = false;
    if (restoreFocus) queueMicrotask(() => triggerElement?.focus());
  }

  function selectAction(nextAction: WritingAction) {
    action = nextAction;
    error = null;
  }

  async function run() {
    if (!canRun) return;
    const sequence = ++requestSequence;
    const requestedSignature = inputSignature;
    loading = true;
    staleResult = false;
    error = null;
    suggestedTitle = "";
    suggestedBody = "";
    suggestionSignature = "";
    try {
      const fields = [
        ...(title.trim() ? [{ key: "title", text: title.trim() }] : []),
        { key: "body", text: body.trim() },
      ];
      const result = await assistWriting(fields, $locale, context, action);
      if (!isCurrentAiResult(sequence, requestSequence, requestedSignature, inputSignature)) {
        staleResult = true;
        return;
      }
      suggestedTitle = result.find((field) => field.key === "title")?.text ?? title;
      suggestedBody = result.find((field) => field.key === "body")?.text ?? "";
      if (!suggestedBody) throw new ApiError("AI_RESPONSE_INVALID");
      suggestionSignature = requestedSignature;
    } catch (caught) {
      if (!isCurrentAiResult(sequence, requestSequence, requestedSignature, inputSignature)) {
        staleResult = true;
        return;
      }
      const code = caught instanceof ApiError ? caught.code : "AI_REQUEST_FAILED";
      error = code === "POLITICAL_CONTENT_UNAVAILABLE"
        ? $translator("ai.politicalUnavailable")
        : translateError(caught, $translator, "ai.failed");
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  function apply() {
    if (!suggestedBody || suggestionSignature !== inputSignature) {
      dismissSuggestion();
      staleResult = true;
      return;
    }
    onApply({ title: suggestedTitle || title, body: suggestedBody });
    dismissSuggestion();
    closePanel();
  }

  function dismissSuggestion() {
    suggestedTitle = "";
    suggestedBody = "";
    suggestionSignature = "";
    staleResult = false;
    error = null;
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key !== "Escape" || !open) return;
    closePanel();
    event.stopPropagation();
  }

  function closeOnOutsidePointer(node: HTMLElement) {
    function handlePointer(event: PointerEvent) {
      if (!open || node.contains(event.target as Node)) return;
      closePanel(false);
    }
    document.addEventListener("pointerdown", handlePointer, true);
    return { destroy: () => document.removeEventListener("pointerdown", handlePointer, true) };
  }
</script>

<div class="writing-assist" use:closeOnOutsidePointer onkeydown={handleKeydown}>
  <button
    bind:this={triggerElement}
    type="button"
    class="writing-trigger"
    class:active={open}
    aria-expanded={open}
    aria-controls={panelId}
    aria-label={$translator(open ? "ai.closeWritingTools" : "ai.openWritingTools")}
    title={$translator(open ? "ai.closeWritingTools" : "ai.openWritingTools")}
    onclick={toggleOpen}
  >
    <SparklesIcon size={14} strokeWidth={1.8} aria-hidden="true" />
    <span>{$translator("ai.label")}</span>
    <span class="writing-trigger-chevron" class:rotated={open}>
      <ChevronDownIcon size={13} strokeWidth={1.8} aria-hidden="true" />
    </span>
  </button>

  {#if open}
    <section id={panelId} class="writing-panel" aria-label={$translator("ai.writingTools")}>
      <div class="writing-panel-header">
        <strong>{$translator("ai.writingTools")}</strong>
        <button
          type="button"
          class="icon-button"
          aria-label={$translator("common.close")}
          title={$translator("common.close")}
          onclick={() => closePanel()}
        >
          <XIcon size={15} strokeWidth={1.8} aria-hidden="true" />
        </button>
      </div>

      {#if availability === "checking"}
        <p class="writing-state" role="status">
          <LoaderCircleIcon class="loading-icon" size={14} strokeWidth={1.8} aria-hidden="true" />
          {$translator("common.processing")}
        </p>
      {:else if availability === "unavailable"}
        <div class="writing-unavailable" role="status">
          <p class="writing-state warning">{$translator("ai.unavailable")}</p>
          <button type="button" class="retry-status" onclick={() => void loadAvailability(true)}>
            {$translator("ai.retry")}
          </button>
        </div>
      {:else}
        <div class="writing-modes" role="group" aria-label={$translator("ai.writingAction")}>
          {#each ["polish", "shorten", "clarify"] as mode}
            <button
              type="button"
              class:active={action === mode}
              aria-pressed={action === mode}
              onclick={() => selectAction(mode as WritingAction)}
            >
              {$translator(`ai.${mode}`)}
            </button>
          {/each}
        </div>

        <button
          type="button"
          class="run-action"
          disabled={!canRun}
          aria-describedby={!readiness.ready ? requirementId : undefined}
          title={!readiness.ready
            ? $translator("ai.needsDraft", { count: WRITING_ASSIST_MIN_BODY_LENGTH })
            : $translator("ai.improveDraft")}
          onclick={() => void run()}
        >
          {#if loading}
            <LoaderCircleIcon class="loading-icon" size={14} strokeWidth={1.8} aria-hidden="true" />
          {:else}
            <SparklesIcon size={14} strokeWidth={1.8} aria-hidden="true" />
          {/if}
          {loading ? $translator("common.processing") : $translator("ai.improveDraft")}
        </button>

        {#if !readiness.ready}
          <p id={requirementId} class="writing-hint">
            {$translator("ai.needsDraft", { count: WRITING_ASSIST_MIN_BODY_LENGTH })}
          </p>
        {:else}
          <p class="writing-hint">{$translator("ai.externalProcessing")}</p>
        {/if}

        {#if error}
          <p class="writing-state warning" role="status">{error}</p>
        {/if}

        {#if staleResult}
          <p class="writing-state warning" role="status">{$translator("ai.resultOutdated")}</p>
        {/if}

        {#if hasSuggestion}
          <section class="writing-result" aria-label={$translator("ai.suggestion")} aria-live="polite">
            <div class="writing-result-heading">
              <strong>{$translator("ai.suggestion")}</strong>
              <button
                type="button"
                class="icon-button"
                onclick={dismissSuggestion}
                title={$translator("ai.discardSuggestion")}
                aria-label={$translator("ai.discardSuggestion")}
              >
                <XIcon size={15} strokeWidth={1.8} aria-hidden="true" />
              </button>
            </div>
            <div class="writing-result-copy">
              {#if suggestedTitle}<h4>{suggestedTitle}</h4>{/if}
              <p>{suggestedBody}</p>
            </div>
            <button type="button" class="apply-action" onclick={apply}>
              <CheckIcon size={14} strokeWidth={1.9} aria-hidden="true" />
              {$translator("ai.applySuggestion")}
            </button>
          </section>
        {/if}
      {/if}
    </section>
  {/if}
</div>

<style>
  .writing-assist {
    position: relative;
    min-width: 0;
  }

  .writing-trigger,
  .writing-panel-header,
  .writing-state,
  .writing-modes,
  .run-action,
  .writing-result-heading,
  .apply-action,
  .icon-button {
    display: flex;
    align-items: center;
  }

  .writing-trigger {
    min-height: 2rem;
    gap: 0.35rem;
    padding: 0.35rem 0.5rem;
    border-radius: var(--vercel-radius-sm);
    color: var(--vercel-text-secondary);
    background: transparent;
    font: inherit;
    font-size: 0.72rem;
    font-weight: 650;
    cursor: pointer;
  }

  .writing-trigger:hover,
  .writing-trigger.active {
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .writing-trigger-chevron {
    display: flex;
    transition: transform 140ms ease;
  }

  .writing-trigger-chevron.rotated {
    transform: rotate(180deg);
  }

  .writing-panel {
    position: absolute;
    z-index: 40;
    top: calc(100% + 0.45rem);
    right: 0;
    width: min(28rem, calc(100vw - 2rem));
    max-height: min(32rem, 70dvh);
    overflow: auto;
    overscroll-behavior: contain;
    padding: 0.65rem;
    border: 1px solid var(--vercel-border-hover);
    border-radius: var(--vercel-radius);
    color: var(--vercel-text-secondary);
    background: var(--vercel-surface-raised);
    box-shadow: 0 12px 32px var(--vercel-shadow);
  }

  .writing-panel-header,
  .writing-result-heading {
    justify-content: space-between;
    gap: 0.75rem;
  }

  .writing-panel-header > strong,
  .writing-result-heading > strong {
    color: var(--vercel-text);
    font-size: 0.75rem;
    font-weight: 650;
  }

  .icon-button {
    width: 1.8rem;
    min-height: 1.8rem;
    flex: 0 0 auto;
    justify-content: center;
    border-radius: var(--vercel-radius-sm);
    color: var(--vercel-text-tertiary);
    background: transparent;
  }

  .icon-button:hover {
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .writing-modes {
    gap: 0.2rem;
    margin-top: 0.65rem;
    padding: 0.2rem;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius-sm);
    background: var(--vercel-surface);
  }

  .writing-modes button {
    min-height: 1.9rem;
    flex: 1 1 0;
    padding: 0.3rem 0.45rem;
    border-radius: calc(var(--vercel-radius-sm) - 2px);
    color: var(--vercel-text-tertiary);
    font-size: 0.7rem;
    font-weight: 600;
  }

  .writing-modes button:hover,
  .writing-modes button.active {
    color: var(--vercel-text);
    background: var(--vercel-hover-strong);
  }

  .run-action,
  .apply-action {
    min-height: 2rem;
    justify-content: center;
    gap: 0.35rem;
    border-radius: var(--vercel-radius-sm);
    font-size: 0.72rem;
    font-weight: 650;
  }

  .run-action {
    width: 100%;
    margin-top: 0.55rem;
    color: var(--vercel-bg);
    background: var(--vercel-text);
  }

  .run-action:disabled {
    cursor: not-allowed;
    opacity: 0.46;
  }

  .writing-hint,
  .writing-state {
    margin: 0.45rem 0 0;
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
    line-height: 1.45;
  }

  .writing-state {
    gap: 0.4rem;
  }

  .writing-unavailable {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-top: 0.45rem;
  }

  .writing-unavailable .writing-state {
    margin: 0;
  }

  .retry-status {
    min-height: 1.8rem;
    flex: 0 0 auto;
    padding: 0.3rem 0.5rem;
    border-radius: var(--vercel-radius-sm);
    color: var(--vercel-text-secondary);
    background: var(--vercel-hover);
    font-size: 0.6875rem;
    font-weight: 650;
  }

  .retry-status:hover {
    color: var(--vercel-text);
    background: var(--vercel-hover-strong);
  }

  .writing-state.warning {
    color: var(--vercel-warning);
  }

  .writing-result {
    margin-top: 0.65rem;
    padding-top: 0.65rem;
    border-top: 1px solid var(--vercel-border);
  }

  .writing-result-copy {
    max-height: 13rem;
    margin-top: 0.4rem;
    overflow: auto;
    overscroll-behavior: contain;
  }

  .writing-result h4 {
    margin: 0;
    color: var(--vercel-text);
    font-size: 0.8125rem;
    font-weight: 650;
  }

  .writing-result p {
    margin: 0.35rem 0 0;
    color: var(--vercel-text-secondary);
    font-size: 0.75rem;
    line-height: 1.5;
    white-space: pre-wrap;
  }

  .apply-action {
    width: 100%;
    margin-top: 0.55rem;
    color: var(--vercel-bg);
    background: var(--vercel-text);
  }

  .writing-trigger:focus-visible,
  .writing-panel button:focus-visible {
    outline: 2px solid var(--vercel-ring);
    outline-offset: 2px;
  }

  .loading-icon {
    animation: ai-spin 800ms linear infinite;
  }

  @keyframes ai-spin {
    to { transform: rotate(360deg); }
  }

  @media (max-width: 36rem) {
    .writing-panel {
      position: fixed;
      right: 0.75rem;
      bottom: 4.75rem;
      left: 0.75rem;
      top: auto;
      width: auto;
      max-height: 60dvh;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .writing-trigger-chevron { transition: none; }
    .loading-icon { animation: none; }
  }

  :global(html[data-motion="reduced"]) .writing-trigger-chevron {
    transition: none;
  }

  :global(html[data-motion="reduced"]) .loading-icon {
    animation: none;
  }
</style>
