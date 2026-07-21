<script lang="ts">
  import type { Patch } from "../../lib/patches";
  import { translator } from "../../lib/i18n";
  import { stripMarkdown } from "../../lib/utils";
  import AuthorMeta from "../AuthorMeta.svelte";
  import VotingWindowMeta from "./VotingWindowMeta.svelte";

  let {
    patch,
    selected = false,
    onSelect = null,
  }: {
    patch: Patch;
    selected?: boolean;
    onSelect?: ((patch: Patch) => void) | null;
  } = $props();

  function openPatch(event: MouseEvent) {
    if (!onSelect || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onSelect(patch);
  }

  const STATUS_TYPES: Record<string, string> = {
    draft: "neutral",
    voting: "warning",
    passed: "info",
    merged: "success",
    rejected: "danger",
    failed: "danger",
  };

  let statusInfo = $derived({
    label: $translator(`status.${patch.status}`),
    type: STATUS_TYPES[patch.status] ?? "neutral",
  });
  let snippet = $derived(stripMarkdown(patch.content));
</script>

<article
  class="patch-card"
  class:selected
>
  <div class="flex items-start gap-3">
    <div class="min-w-0 flex-1">
      <div class="patch-topline">
        <span class="badge badge-{statusInfo.type}">
          {statusInfo.label}
        </span>
        <span class="text-xs" style="color: var(--vercel-text-tertiary);">#{patch.pr_number}</span>
      </div>
      <h2 class="mt-1 text-base font-semibold">
        <a class="card-link" href={`/patches/${patch.id}`} style="color: var(--vercel-text);" onclick={openPatch}>
          {patch.title}
        </a>
      </h2>
      <p class="mt-1 line-clamp-2 text-sm" style="color: var(--vercel-text-secondary);">{snippet}</p>
      <VotingWindowMeta
        status={patch.status}
        votingWindowKind={patch.voting_window_kind}
        votingPeriodHours={patch.voting_period_hours}
        votingStartedAt={patch.voting_started_at}
        votingEndsAt={patch.voting_ends_at}
      />
    </div>
  </div>

  <div class="patch-footer">
    <div class="patch-stats" style="color: var(--vercel-text-tertiary);">
      {#if patch.status !== "draft"}
        <span>{$translator("patch.for")} {patch.for_count} · {$translator("patch.against")} {patch.against_count}</span>
      {/if}
    </div>
    <AuthorMeta username={patch.author_username ?? $translator("common.anonymous")} userId={patch.author_id} createdAt={patch.created_at} />
  </div>
</article>

<style>
  .patch-card {
    position: relative;
    container-type: inline-size;
    padding: 1rem;
    border-bottom: 1px solid var(--vercel-border);
    transition: background 180ms ease, box-shadow 180ms ease;
  }

  .patch-card:last-child {
    border-bottom: 0;
  }

  .patch-card:hover {
    background: var(--vercel-hover);
    box-shadow: inset 2px 0 var(--vercel-border-hover);
  }

  .patch-card.selected {
    background: var(--vercel-hover-strong);
    box-shadow: inset 2px 0 var(--vercel-text-secondary);
  }

  .patch-topline {
    display: flex;
    min-width: 0;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.45rem;
  }

  .patch-card h2 {
    display: -webkit-box;
    overflow: hidden;
    overflow-wrap: anywhere;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }

  .patch-card :global(.voting-window-meta) {
    position: relative;
    z-index: 1;
    margin-top: 0.45rem;
  }

  .patch-footer {
    display: grid;
    min-width: 0;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.65rem;
    align-items: center;
    margin-top: 0.65rem;
  }

  .patch-stats {
    display: flex;
    min-width: 0;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.45rem;
    font-size: 0.72rem;
  }

  .card-link::after {
    content: "";
    position: absolute;
    inset: 0;
  }

  .patch-card:has(.card-link:focus-visible) {
    outline: 2px solid var(--vercel-text);
    outline-offset: -2px;
  }

  .card-link:focus-visible {
    outline: none;
  }

  @container (max-width: 23rem) {
    .patch-footer { grid-template-columns: minmax(0, 1fr); }
    .patch-stats { order: 2; }
  }
</style>
