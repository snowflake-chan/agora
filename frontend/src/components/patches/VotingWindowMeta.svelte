<script lang="ts">
  import { Clock3Icon } from "@lucide/svelte";
  import {
    formatVotingPeriod,
    isActiveCreatorWindow,
    resolveVotingPeriodHours,
    type VotingWindowKind,
  } from "../../lib/governance";
  import { locale, translator } from "../../lib/i18n";

  let {
    status,
    votingWindowKind,
    votingPeriodHours,
    votingStartedAt,
    votingEndsAt,
    showHistory = false,
  }: {
    status: string | null;
    votingWindowKind: VotingWindowKind | null;
    votingPeriodHours: number | null;
    votingStartedAt: string | null;
    votingEndsAt: string | null;
    showHistory?: boolean;
  } = $props();

  let resolvedHours = $derived(
    resolveVotingPeriodHours(votingPeriodHours, votingStartedAt, votingEndsAt),
  );
  let duration = $derived(formatVotingPeriod(resolvedHours, $locale));
  let visible = $derived(
    (status === "voting" || (showHistory && status !== "draft")) &&
      isActiveCreatorWindow(
        votingWindowKind,
        votingPeriodHours,
        votingStartedAt,
        votingEndsAt,
      ),
  );
</script>

{#if visible && duration}
  <span
    class="voting-window-meta"
    title={$translator("patch.activeCreatorWindowDescription")}
  >
    <Clock3Icon size={12} strokeWidth={1.8} aria-hidden="true" />
    {$translator("patch.activeCreatorWindow", { duration })}
  </span>
{/if}

<style>
  .voting-window-meta {
    display: inline-flex;
    min-width: 0;
    align-items: center;
    gap: 0.25rem;
    padding: 0.2rem 0.4rem;
    border: 1px solid var(--vercel-border);
    border-radius: 0.375rem;
    color: var(--vercel-text-secondary);
    background: var(--vercel-surface-muted);
    font-size: 0.6875rem;
    font-variant-numeric: tabular-nums;
    font-weight: 550;
    line-height: 1.2;
    white-space: nowrap;
  }
</style>
