<script lang="ts">
  import { BarChart3Icon, CheckIcon, Clock3Icon, LanguagesIcon } from "@lucide/svelte";
  import { onMount } from "svelte";
  import { AiRequestError, getAiStatus, translateFields } from "../../lib/ai";
  import { ApiError } from "../../lib/auth";
  import { locale, translateError, translator } from "../../lib/i18n";
  import { requestLogin } from "../../lib/login";
  import { dispatchModerationUpdate } from "../../lib/moderation";
  import { autoTranslate, initPreferences } from "../../lib/preferences";
  import { voteOnPoll, type Poll } from "../../lib/posts";
  import { currentUser } from "../../stores/auth";
  import { relativeTimeClock } from "../../stores/relativeTime";
  import { toaster } from "../../stores/toaster";

  let {
    postId,
    poll,
    compact = false,
    readOnly = false,
    onUpdate = null,
    sourceRevisionNumber = null,
    moderationTargetHref = null,
    onModerationQueued = null,
  }: {
    postId: string;
    poll: Poll;
    compact?: boolean;
    readOnly?: boolean;
    onUpdate?: ((poll: Poll) => void) | null;
    sourceRevisionNumber?: number | null;
    moderationTargetHref?: string | null;
    onModerationQueued?: (() => void) | null;
  } = $props();

  let currentPoll = $state<Poll>(poll);
  let selectedOptionId = $state<string | null>(poll.selected_option_id ?? null);
  let submitting = $state(false);
  let aiEnabled = $state(false);
  let translationLoading = $state(false);
  let translatedQuestion = $state("");
  let translatedOptions = $state<string[]>([]);
  let visible = $state(false);
  let autoSignature = $state("");
  let cachedLocale = $state($locale);
  let now = $derived($relativeTimeClock);
  let isClosed = $derived(
    currentPoll.is_closed || Date.parse(currentPoll.closes_at) <= now,
  );
  let showingResults = $derived(Boolean(currentPoll.selected_option_id) || isClosed);
  let canSubmit = $derived(
    !isClosed &&
      Boolean(selectedOptionId) &&
      selectedOptionId !== currentPoll.selected_option_id &&
      !submitting,
  );

  $effect(() => {
    currentPoll = poll;
    selectedOptionId = poll.selected_option_id ?? null;
  });

  $effect(() => {
    const nextLocale = $locale;
    if (nextLocale === cachedLocale) return;
    cachedLocale = nextLocale;
    translatedQuestion = "";
    translatedOptions = [];
  });

  $effect(() => {
    if (!aiEnabled || !visible || !$autoTranslate || !$currentUser) return;
    const signature = `${$locale}:${currentPoll.question}:${currentPoll.options.map((option) => option.text).join("\u0000")}`;
    if (autoSignature === signature) return;
    autoSignature = signature;
    void translatePoll();
  });

  onMount(async () => {
    initPreferences();
    aiEnabled = (await getAiStatus()).enabled;
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

  async function translatePoll() {
    if (translationLoading || readOnly) return;
    if (!$currentUser) {
      requestLogin(undefined, () => void translatePoll());
      return;
    }
    translationLoading = true;
    try {
      const fields = [
        { key: "question", text: currentPoll.question },
        ...currentPoll.options.map((option, index) => ({
          key: `option_${index + 1}`,
          text: option.text,
        })),
      ];
      const result = await translateFields(
        fields,
        $locale,
        "poll",
        sourceRevisionNumber
          ? { contentId: postId, revisionNumber: sourceRevisionNumber }
          : null,
      );
      translatedQuestion = result.fields[0]?.translation ?? "";
      translatedOptions = result.fields.slice(1).map((field) => field.translation);
    } catch (error) {
      const moderationUpdate = error instanceof AiRequestError
        ? error.moderationUpdate
        : null;
      if (moderationUpdate?.contentId === postId) {
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
      } else {
        const code = error instanceof ApiError ? error.code : "AI_REQUEST_FAILED";
        const isSafetyBlock = code === "POLITICAL_CONTENT_UNAVAILABLE"
          || code === "AI_OUTPUT_BLOCKED"
          || code === "AI_PROVIDER_FILTERED";
        const message = translateError(error, $translator, "ai.failed");
        if (isSafetyBlock) {
          toaster.info($translator("ai.tools"), message);
        } else {
          toaster.error($translator("common.operationFailed"), message);
        }
      }
    } finally {
      translationLoading = false;
    }
  }

  function percentage(voteCount: number): number {
    if (!currentPoll.total_votes) return 0;
    return Math.round((voteCount / currentPoll.total_votes) * 100);
  }

  function containInteraction(event: MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
  }

  function choose(optionId: string) {
    if (isClosed || readOnly) return;
    if (!$currentUser) {
      requestLogin(undefined, () => choose(optionId));
      return;
    }
    selectedOptionId = optionId;
  }

  async function submitVote() {
    if (isClosed || readOnly || !selectedOptionId) return;
    if (!$currentUser) {
      requestLogin(undefined, () => void submitVote());
      return;
    }
    submitting = true;
    try {
      const next = await voteOnPoll(postId, selectedOptionId);
      currentPoll = next;
      selectedOptionId = next.selected_option_id ?? selectedOptionId;
      onUpdate?.(next);
    } catch (error) {
      toaster.error(
        $translator("common.operationFailed"),
        translateError(error, $translator, "poll.voteFailed"),
      );
    } finally {
      submitting = false;
    }
  }
</script>

<section
  use:trackVisibility
  class:compact
  class="poll-card"
  aria-label={$translator("poll.label")}
  onclick={containInteraction}
>
  <div class="poll-heading">
    <span class="poll-kicker">
      <BarChart3Icon size={14} strokeWidth={1.8} aria-hidden="true" />
      {$translator("poll.label")}
    </span>
    <div class="poll-heading-actions">
      {#if aiEnabled && !readOnly}
        <button
          type="button"
          class="poll-translate"
          title={$translator("ai.translate")}
          aria-label={$translator("ai.translate")}
          disabled={translationLoading}
          onclick={(event) => { containInteraction(event); void translatePoll(); }}
        >
          <LanguagesIcon size={14} strokeWidth={1.8} aria-hidden="true" />
        </button>
      {/if}
      {#if isClosed}
        <span class="poll-state">{$translator("poll.closed")}</span>
      {:else}
        <span class="poll-state">
          <Clock3Icon size={13} strokeWidth={1.8} aria-hidden="true" />
          {$translator("poll.open")}
        </span>
      {/if}
    </div>
  </div>

  <h3 class="poll-question">
    {currentPoll.question}
    {#if translatedQuestion}<small lang={$locale}>{translatedQuestion}</small>{/if}
  </h3>

  <div class="poll-options" role="group" aria-label={currentPoll.question}>
    {#each currentPoll.options as option, index (option.id)}
      {@const selected = selectedOptionId === option.id}
      {@const resultPercent = percentage(option.vote_count)}
      <button
        type="button"
        class:selected
        class="poll-option"
        aria-pressed={selected}
        disabled={isClosed || readOnly || submitting}
        onclick={(event) => {
          containInteraction(event);
          choose(option.id);
        }}
      >
        {#if showingResults}
          <span class="poll-result-track" aria-hidden="true">
            <span class="poll-result-fill" style={`--poll-ratio:${resultPercent / 100}`}></span>
          </span>
        {/if}
        <span class="poll-option-marker" aria-hidden="true">
          {#if selected}<CheckIcon size={13} strokeWidth={2.3} />{/if}
        </span>
        <span class="poll-option-text">
          {option.text}
          {#if translatedOptions[index]}<small lang={$locale}>{translatedOptions[index]}</small>{/if}
        </span>
        {#if showingResults}
          <span class="poll-option-result">{option.vote_count} <span>{resultPercent}%</span></span>
        {/if}
      </button>
    {/each}
  </div>

  <div class="poll-footer">
    {#if readOnly}
      <span>{$translator("moderation.ai.interactionsPaused")}</span>
    {:else if showingResults}
      <span>{$translator("poll.totalVotes", { count: currentPoll.total_votes })}</span>
      {#if !isClosed}
        <span>{$translator("poll.changeHint")}</span>
      {/if}
    {:else}
      <span>{$translator("poll.pickOption")}</span>
    {/if}

    {#if !isClosed && !readOnly}
      <button
        type="button"
        class="btn btn-secondary btn-sm poll-submit"
        disabled={!canSubmit}
        onclick={(event) => {
          containInteraction(event);
          void submitVote();
        }}
      >
        {#if submitting}
          {$translator("common.processing")}
        {:else if currentPoll.selected_option_id}
          {$translator("poll.changeVote")}
        {:else}
          {$translator("poll.vote")}
        {/if}
      </button>
    {/if}
  </div>
</section>

<style>
  .poll-card {
    position: relative;
    z-index: 2;
    margin-top: 1rem;
    padding-top: 0.9rem;
    border-top: 1px solid var(--vercel-border);
  }

  .poll-heading,
  .poll-heading-actions,
  .poll-footer,
  .poll-kicker,
  .poll-state,
  .poll-option,
  .poll-option-result {
    display: flex;
    align-items: center;
  }

  .poll-heading {
    justify-content: space-between;
    gap: 0.75rem;
  }

  .poll-heading-actions {
    gap: 0.4rem;
  }

  .poll-translate {
    display: grid;
    width: 1.75rem;
    height: 1.75rem;
    place-items: center;
    border: 0;
    border-radius: var(--vercel-radius-sm);
    color: var(--vercel-text-tertiary);
    background: transparent;
    cursor: pointer;
  }

  .poll-translate:hover,
  .poll-translate:focus-visible {
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .poll-translate:disabled {
    cursor: wait;
    opacity: 0.5;
  }

  .poll-kicker {
    gap: 0.35rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0;
  }

  .poll-state {
    flex: 0 0 auto;
    gap: 0.25rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
    white-space: nowrap;
  }

  .poll-question {
    margin: 0.45rem 0 0.7rem;
    color: var(--vercel-text);
    font-size: 0.9375rem;
    font-weight: 650;
    line-height: 1.45;
  }

  .poll-question small,
  .poll-option-text small {
    display: block;
    margin-top: 0.18rem;
    color: var(--vercel-text-secondary);
    font-size: 0.72rem;
    font-weight: 500;
    line-height: 1.4;
  }

  .poll-option-text {
    min-width: 0;
    text-align: left;
  }

  .poll-options {
    display: grid;
    gap: 0.45rem;
  }

  .poll-option {
    position: relative;
    width: 100%;
    min-height: 2.75rem;
    overflow: hidden;
    gap: 0.625rem;
    padding: 0.55rem 0.7rem;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius-sm);
    color: var(--vercel-text-secondary);
    background: color-mix(in srgb, var(--vercel-card) 84%, transparent);
    cursor: pointer;
    font: inherit;
    font-size: 0.8125rem;
    line-height: 1.35;
    text-align: left;
    transition: border-color 160ms ease, background-color 160ms ease, color 160ms ease;
  }

  .poll-option:not(:disabled):hover {
    border-color: var(--vercel-border-hover);
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .poll-option:focus-visible {
    outline: 2px solid var(--vercel-ring);
    outline-offset: 2px;
  }

  .poll-option.selected {
    border-color: color-mix(in srgb, var(--vercel-accent) 52%, var(--vercel-border));
    color: var(--vercel-text);
    background: color-mix(in srgb, var(--vercel-accent) 8%, var(--vercel-card));
  }

  .poll-option:disabled {
    cursor: default;
  }

  .poll-result-track,
  .poll-result-fill {
    position: absolute;
    inset: 0;
  }

  .poll-result-track {
    z-index: 0;
    background: color-mix(in srgb, var(--vercel-hover-strong) 72%, transparent);
  }

  .poll-result-fill {
    transform: scaleX(var(--poll-ratio));
    transform-origin: left center;
    background: color-mix(in srgb, var(--vercel-accent) 13%, transparent);
    transition: transform 360ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  .poll-option > :not(.poll-result-track) {
    position: relative;
    z-index: 1;
  }

  .poll-option-marker {
    display: grid;
    width: 1rem;
    height: 1rem;
    flex: 0 0 auto;
    place-items: center;
    border: 1px solid var(--vercel-border-hover);
    border-radius: 50%;
    color: var(--vercel-accent-foreground);
    background: transparent;
  }

  .poll-option.selected .poll-option-marker {
    border-color: var(--vercel-accent);
    background: var(--vercel-accent);
  }

  .poll-option-text {
    min-width: 0;
    flex: 1;
    overflow-wrap: anywhere;
  }

  .poll-option-result {
    flex: 0 0 auto;
    gap: 0.35rem;
    color: var(--vercel-text-secondary);
    font-size: 0.75rem;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .poll-option-result span {
    color: var(--vercel-text-tertiary);
  }

  .poll-footer {
    min-height: 2.25rem;
    justify-content: space-between;
    gap: 0.75rem;
    margin-top: 0.65rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
    line-height: 1.35;
  }

  .poll-footer > span {
    min-width: 0;
  }

  .poll-submit {
    flex: 0 0 auto;
  }

  .poll-card.compact {
    margin-top: 0.75rem;
    padding-top: 0.75rem;
  }

  .poll-card.compact .poll-question {
    font-size: 0.875rem;
  }

  @media (max-width: 22.5rem) {
    .poll-footer {
      align-items: flex-start;
      flex-direction: column;
    }

    .poll-submit {
      width: 100%;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .poll-option,
    .poll-result-fill {
      transition: none;
    }
  }

  :global(html[data-motion="reduced"]) .poll-option,
  :global(html[data-motion="reduced"]) .poll-result-fill {
    transition: none;
  }
</style>
