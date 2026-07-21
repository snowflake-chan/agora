<script lang="ts">
  import { Clock3Icon, ShieldCheckIcon, ShieldXIcon } from "@lucide/svelte";
  import type { ModerationStatus } from "../../lib/moderation";
  import { translator } from "../../lib/i18n";

  let {
    status,
    reason = null,
    reviewNote = null,
    compact = false,
  }: {
    status: ModerationStatus | null | undefined;
    reason?: string | null;
    reviewNote?: string | null;
    compact?: boolean;
  } = $props();

  let pending = $derived(status === "pending_review");
  let approved = $derived(status === "approved");
  let rejected = $derived(status === "rejected");
  let classifierUnavailable = $derived(
    pending && reason === "classifier_unavailable",
  );
</script>

{#if pending || approved || rejected}
  {#if compact}
    <div class="moderation-compact-group">
      <span
        class:approved
        class:rejected
        class="moderation-compact"
        title={$translator(
          pending
            ? classifierUnavailable
              ? "moderation.ai.pendingUnavailableDescription"
              : "moderation.ai.pendingDescription"
            : approved
              ? "moderation.ai.approvedDescription"
              : "moderation.ai.rejectedDescription",
        )}
      >
        {#if pending}
          <Clock3Icon size={13} strokeWidth={1.9} aria-hidden="true" />
        {:else if approved}
          <ShieldCheckIcon size={13} strokeWidth={1.9} aria-hidden="true" />
        {:else}
          <ShieldXIcon size={13} strokeWidth={1.9} aria-hidden="true" />
        {/if}
        {$translator(
          pending
            ? "moderation.ai.compactPending"
            : approved
              ? "moderation.ai.compactApproved"
              : "moderation.ai.compactRejected",
        )}
      </span>
      {#if reviewNote}
        <span class="compact-review-note">
          {$translator("moderation.ai.reviewNote")}: {reviewNote}
        </span>
      {/if}
    </div>
  {:else}
    <aside class:approved class:rejected class="moderation-notice" role="status">
      <span class="moderation-icon" aria-hidden="true">
        {#if pending}
          <Clock3Icon size={18} strokeWidth={1.8} />
        {:else if approved}
          <ShieldCheckIcon size={18} strokeWidth={1.8} />
        {:else}
          <ShieldXIcon size={18} strokeWidth={1.8} />
        {/if}
      </span>
      <div class="moderation-copy">
        <strong>
          {$translator(
            pending
              ? "moderation.ai.pendingTitle"
              : approved
                ? "moderation.ai.approvedTitle"
                : "moderation.ai.rejectedTitle",
          )}
        </strong>
        <p>
          {$translator(
            pending
              ? classifierUnavailable
                ? "moderation.ai.pendingUnavailableDescription"
                : "moderation.ai.pendingDescription"
              : approved
                ? "moderation.ai.approvedDescription"
                : "moderation.ai.rejectedDescription",
          )}
        </p>
        {#if reviewNote}
          <p class="review-note">
            <span>{$translator("moderation.ai.reviewNote")}</span>
            {reviewNote}
          </p>
        {/if}
      </div>
    </aside>
  {/if}
{/if}

<style>
  .moderation-notice {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.75rem;
    margin-bottom: 0.9rem;
    padding: 0.75rem 0.875rem;
    color: var(--vercel-warning);
    background: var(--vercel-warning-bg);
    border-left: 3px solid var(--vercel-warning);
  }

  .moderation-notice.rejected {
    color: var(--vercel-danger);
    background: var(--vercel-danger-bg);
    border-left-color: var(--vercel-danger);
  }

  .moderation-notice.approved {
    color: var(--vercel-success);
    background: var(--vercel-success-bg);
    border-left-color: var(--vercel-success);
  }

  .moderation-icon {
    display: inline-flex;
    padding-top: 0.05rem;
  }

  .moderation-copy {
    min-width: 0;
  }

  .moderation-copy strong {
    display: block;
    color: currentColor;
    font-size: 0.8125rem;
    line-height: 1.35;
  }

  .moderation-copy p {
    margin: 0.2rem 0 0;
    color: var(--vercel-text-secondary);
    font-size: 0.75rem;
    line-height: 1.5;
  }

  .moderation-copy .review-note {
    margin-top: 0.55rem;
    padding-top: 0.5rem;
    border-top: 1px solid color-mix(in srgb, currentColor 20%, transparent);
    color: var(--vercel-text);
  }

  .review-note span {
    display: block;
    margin-bottom: 0.15rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
    font-weight: 650;
  }

  .moderation-compact {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    min-height: 1.5rem;
    padding: 0.15rem 0.45rem;
    color: var(--vercel-warning);
    background: var(--vercel-warning-bg);
    border: 1px solid color-mix(in srgb, var(--vercel-warning) 22%, transparent);
    border-radius: var(--vercel-radius-sm);
    font-size: 0.6875rem;
    font-weight: 650;
    line-height: 1.2;
    white-space: nowrap;
  }

  .moderation-compact-group {
    display: flex;
    min-width: 0;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .compact-review-note {
    overflow: hidden;
    max-width: min(100%, 42rem);
    color: var(--vercel-text-secondary);
    font-size: 0.6875rem;
    line-height: 1.4;
    overflow-wrap: anywhere;
  }

  .moderation-compact.rejected {
    color: var(--vercel-danger);
    background: var(--vercel-danger-bg);
    border-color: color-mix(in srgb, var(--vercel-danger) 22%, transparent);
  }

  .moderation-compact.approved {
    color: var(--vercel-success);
    background: var(--vercel-success-bg);
    border-color: color-mix(in srgb, var(--vercel-success) 22%, transparent);
  }
</style>
