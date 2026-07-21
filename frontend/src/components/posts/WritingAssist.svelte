<script lang="ts">
  import { CheckIcon, SparklesIcon, XIcon } from "@lucide/svelte";
  import { assistWriting, getAiStatus, type TranslationContext, type WritingAction } from "../../lib/ai";
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

  let enabled = $state(false);
  let action = $state<WritingAction>("polish");
  let loading = $state(false);
  let suggestedTitle = $state("");
  let suggestedBody = $state("");
  let error = $state<string | null>(null);
  let canRun = $derived(body.trim().length >= 12 && !loading);
  let hasSuggestion = $derived(Boolean(suggestedBody));

  $effect(() => {
    getAiStatus().then((status) => enabled = status.enabled);
  });

  async function run() {
    if (!canRun) return;
    loading = true;
    error = null;
    suggestedTitle = "";
    suggestedBody = "";
    try {
      const fields = [
        ...(title.trim() ? [{ key: "title", text: title.trim() }] : []),
        { key: "body", text: body.trim() },
      ];
      const result = await assistWriting(fields, $locale, context, action);
      suggestedTitle = result.find((field) => field.key === "title")?.text ?? title;
      suggestedBody = result.find((field) => field.key === "body")?.text ?? "";
      if (!suggestedBody) throw new ApiError("AI_RESPONSE_INVALID");
    } catch (caught) {
      const code = caught instanceof ApiError ? caught.code : "AI_REQUEST_FAILED";
      error = code === "POLITICAL_CONTENT_UNAVAILABLE"
        ? $translator("ai.politicalUnavailable")
        : translateError(caught, $translator, "ai.failed");
    } finally {
      loading = false;
    }
  }

  function apply() {
    if (!suggestedBody) return;
    onApply({ title: suggestedTitle || title, body: suggestedBody });
    dismiss();
  }

  function dismiss() {
    suggestedTitle = "";
    suggestedBody = "";
    error = null;
  }
</script>

{#if enabled}
  <div class="writing-assist">
    <div class="writing-controls">
      <SparklesIcon size={15} strokeWidth={1.8} aria-hidden="true" />
      <select bind:value={action} aria-label={$translator("ai.writingAction")} title={$translator("ai.writingAction")}>
        <option value="polish">{$translator("ai.polish")}</option>
        <option value="shorten">{$translator("ai.shorten")}</option>
        <option value="clarify">{$translator("ai.clarify")}</option>
      </select>
      <button type="button" disabled={!canRun} onclick={() => void run()}>
        {loading ? $translator("common.processing") : $translator("ai.improveDraft")}
      </button>
    </div>

    {#if error}
      <p class="writing-error" role="status">{error}</p>
    {/if}

    {#if hasSuggestion}
      <section class="writing-preview" aria-label={$translator("ai.suggestion")}>
        <div class="writing-preview-copy">
          <strong>{$translator("ai.suggestion")}</strong>
          {#if suggestedTitle}<h4>{suggestedTitle}</h4>{/if}
          <p>{suggestedBody}</p>
        </div>
        <div class="writing-preview-actions">
          <button type="button" class="apply" onclick={apply}>
            <CheckIcon size={14} strokeWidth={1.9} aria-hidden="true" />
            {$translator("ai.applySuggestion")}
          </button>
          <button type="button" class="dismiss" onclick={dismiss} title={$translator("ai.discardSuggestion")} aria-label={$translator("ai.discardSuggestion")}>
            <XIcon size={15} strokeWidth={1.9} aria-hidden="true" />
          </button>
        </div>
      </section>
    {/if}
  </div>
{/if}

<style>
  .writing-assist { position: relative; min-width: 0; }
  .writing-controls { display: flex; min-width: 0; align-items: center; gap: .35rem; color: var(--vercel-text-secondary); }
  .writing-controls select,
  .writing-controls button { min-height: 2rem; border: 1px solid var(--vercel-border); border-radius: var(--vercel-radius-sm); color: var(--vercel-text-secondary); background: var(--vercel-surface); font: inherit; font-size: .72rem; }
  .writing-controls select { max-width: 8rem; padding: .3rem 1.65rem .3rem .5rem; }
  .writing-controls button { padding: .3rem .6rem; font-weight: 600; }
  .writing-controls button:not(:disabled):hover { color: var(--vercel-text); background: var(--vercel-hover); }
  .writing-controls button:disabled { cursor: not-allowed; opacity: .5; }
  .writing-error { margin: .45rem 0 0; color: var(--vercel-warning); font-size: .7rem; line-height: 1.45; }
  .writing-preview { position: absolute; z-index: 30; top: calc(100% + .5rem); left: 0; display: grid; width: min(32rem, calc(100vw - 2rem)); max-height: 22rem; grid-template-columns: minmax(0, 1fr) auto; gap: .75rem; overflow: auto; padding: .8rem; border: 1px solid var(--vercel-border-hover); border-radius: var(--vercel-radius); background: var(--vercel-surface-raised); box-shadow: 0 12px 32px var(--vercel-shadow); }
  .writing-preview-copy { min-width: 0; }
  .writing-preview-copy > strong { color: var(--vercel-text-tertiary); font-size: .65rem; letter-spacing: 0; }
  .writing-preview h4 { margin: .35rem 0 0; color: var(--vercel-text); font-size: .82rem; font-weight: 650; }
  .writing-preview p { margin: .4rem 0 0; color: var(--vercel-text-secondary); font-size: .76rem; line-height: 1.5; white-space: pre-wrap; }
  .writing-preview-actions { display: flex; align-items: flex-start; gap: .3rem; }
  .writing-preview-actions button { display: inline-flex; min-height: 2rem; align-items: center; justify-content: center; gap: .3rem; border-radius: var(--vercel-radius-sm); font-size: .7rem; font-weight: 600; }
  .writing-preview-actions .apply { padding: .35rem .55rem; color: var(--vercel-bg); background: var(--vercel-text); }
  .writing-preview-actions .dismiss { width: 2rem; color: var(--vercel-text-secondary); background: var(--vercel-hover); }
  @media (max-width: 36rem) {
    .writing-controls { flex-wrap: wrap; }
    .writing-preview { position: fixed; right: .75rem; bottom: 5rem; left: .75rem; top: auto; width: auto; max-height: 45dvh; grid-template-columns: 1fr; }
    .writing-preview-actions { justify-content: flex-end; }
  }
</style>
