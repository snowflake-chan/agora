<script lang="ts">
  import { Clock3Icon, HeartIcon, MessageCircleIcon } from "@lucide/svelte";
  import { onMount } from "svelte";
  import { getVotingCountdown, type VotingCountdown } from "../lib/governance";
  import type { FeedItem } from "../lib/posts";
  import { translator } from "../lib/i18n";
  import { stripMarkdown } from "../lib/utils";
  import AuthorMeta from "./AuthorMeta.svelte";
  import VotingWindowMeta from "./patches/VotingWindowMeta.svelte";
  import PollCard from "./posts/PollCard.svelte";

  let {
    item,
    selected = false,
    onSelect = null,
  }: {
    item: FeedItem;
    selected?: boolean;
    onSelect?: ((item: FeedItem) => void) | null;
  } = $props();

  const STATUS_CLASSES: Record<string, string> = {
    draft: "badge-neutral",
    voting: "badge-warning",
    passed: "badge-info",
    merged: "badge-success",
    rejected: "badge-danger",
    failed: "badge-danger",
  };

  let snippet = $derived(stripMarkdown(item.content));
  let href = $derived(item.type === "post" ? `/posts/${item.id}` : `/patches/${item.id}`);
  let statusInfo = $derived(
    item.type === "patch" && item.status
      ? {
          label: $translator(`status.${item.status}`),
          cls: STATUS_CLASSES[item.status] ?? "badge-neutral",
        }
      : null
  );
  let rankingReason = $derived(formatRankingReason(item.ranking_reason));
  let now = $state(Date.now());
  let countdownState = $derived(getVotingCountdown(item.voting_ends_at, now));
  let countdown = $derived(formatCountdown(countdownState));
  let countdownUrgent = $derived(
    Boolean(item.voting_ends_at) &&
      new Date(item.voting_ends_at as string).getTime() - now < 2 * 60 * 60 * 1000,
  );

  onMount(() => {
    if (item.type !== "patch" || item.status !== "voting" || !item.voting_ends_at) {
      return;
    }
    const timer = window.setInterval(() => (now = Date.now()), 30_000);
    return () => window.clearInterval(timer);
  });

  function formatCountdown(value: VotingCountdown | null): string | null {
    if (item.type !== "patch" || item.status !== "voting" || !value) return null;
    if (value.state === "closed") return $translator("patch.closed");
    if (value.state === "days") {
      return $translator("patch.remainingDaysHours", {
        days: value.days,
        hours: value.hours,
      });
    }
    if (value.state === "hours") {
      return $translator("patch.remainingHours", { hours: value.hours });
    }
    return $translator("patch.remainingMinutes", { minutes: value.minutes });
  }

  function formatRankingReason(reason: string | null): string | null {
    if (!reason) return null;
    const [code, detail] = reason.split(":", 2);
    if (code === "followed_author") return $translator("feed.reasonFollowed");
    if (code === "topic") {
      return $translator("feed.reasonTopic").replace("{topic}", detail ?? "");
    }
    if (code === "community_voting") return $translator("feed.reasonVoting");
    if (code === "rising") return $translator("feed.reasonRising");
    if (code === "latest") return $translator("feed.reasonLatest");
    if (code === "trending") {
      return $translator("feed.reasonTrending").replace("{count}", detail ?? "0");
    }
    return $translator("feed.reasonRecent");
  }

  function handleOpen(event: MouseEvent) {
    if (window.matchMedia("(min-width: 64rem)").matches && onSelect) {
      event.preventDefault();
      onSelect(item);
    }
  }
</script>

<article
  class:active={selected}
  class="stream-card"
  aria-current={selected ? "true" : undefined}
>
  <div class="stream-card-topline">
    <span class="content-kind">{$translator(item.type === "post" ? "common.discussion" : "common.change")}</span>
    {#if rankingReason}
      <span class="ranking-reason">{rankingReason}</span>
    {/if}
    {#if item.type === "patch"}
      {#if statusInfo}
        <span class="badge {statusInfo.cls}">
          {statusInfo.label}
        </span>
      {/if}
      {#if item.pr_number}
        <span class="text-xs" style="color: var(--vercel-text-tertiary);">PR #{item.pr_number}</span>
      {/if}
      <VotingWindowMeta
        status={item.status}
        votingWindowKind={item.voting_window_kind}
        votingPeriodHours={item.voting_period_hours}
        votingStartedAt={item.voting_started_at}
        votingEndsAt={item.voting_ends_at}
      />
    {:else if item.tags && item.tags.length > 0}
      <span class="stream-tag">{item.tags[0]}</span>
    {/if}
  </div>

  <h2 class="mt-1 text-base font-semibold">
    <a
      class="card-link"
      href={href}
      style="color: var(--vercel-text);"
      onclick={handleOpen}
    >
      {item.title}
    </a>
  </h2>

  <p class="mt-1 line-clamp-2 text-sm" style="color: var(--vercel-text-secondary);">
    {snippet}
  </p>

  {#if item.type === "post" && item.poll}
    <PollCard postId={item.id} poll={item.poll} compact />
  {/if}

  <div class="mt-2 flex items-center justify-between gap-2">
    <div class="flex items-center gap-3 text-xs" style="color: var(--vercel-text-tertiary);">
      {#if item.type === "post" && item.tags && item.tags.length > 0}
        <span>{item.tags.join(", ")}</span>
      {/if}
      {#if item.type === "patch"}
        <span>{$translator("patch.for")} {item.for_count} · {$translator("patch.against")} {item.against_count}</span>
        {#if countdown}
          <span class:urgent={countdownUrgent} class="vote-countdown">
            <Clock3Icon size={14} strokeWidth={1.8} aria-hidden="true" />
            {countdown}
          </span>
        {/if}
      {/if}
      {#if item.type === "post"}
        <span class="flex items-center gap-1">
          <HeartIcon class="size-3.5" aria-hidden="true" />
          {item.like_count}
        </span>
      {/if}
      <span class="flex items-center gap-1">
        <MessageCircleIcon class="size-3.5" aria-hidden="true" />
        {item.reply_count}
      </span>
    </div>

    <AuthorMeta username={item.author_username ?? $translator("common.anonymous")} userId={item.author_id} createdAt={item.created_at} />
  </div>
</article>

<style>
  .stream-card {
    position: relative;
    display: block;
    padding: 1rem;
    border-bottom: 1px solid var(--vercel-border);
    transition: background 180ms ease, box-shadow 180ms ease;
  }

  .stream-card:hover {
    background: var(--vercel-hover);
  }

  .stream-card.active {
    background: var(--vercel-hover-strong);
    box-shadow: inset 2px 0 var(--vercel-text);
  }

  .stream-card-topline {
    display: flex;
    min-height: 1.25rem;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }

  .content-kind {
    color: var(--vercel-text-tertiary);
    font-size: 0.65rem;
    font-weight: 650;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .stream-tag {
    overflow: hidden;
    color: var(--vercel-text-tertiary);
    font-size: 0.7rem;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .ranking-reason {
    overflow: hidden;
    max-width: 12rem;
    color: var(--vercel-text-secondary);
    font-size: 0.68rem;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .vote-countdown {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.15rem 0.4rem;
    border-radius: 999px;
    color: var(--vercel-warning);
    background: color-mix(in srgb, var(--vercel-warning) 10%, transparent);
    font-size: 0.65rem;
    font-weight: 600;
    white-space: nowrap;
  }

  .vote-countdown.urgent {
    color: var(--vercel-danger);
    background: color-mix(in srgb, var(--vercel-danger) 10%, transparent);
  }

  .card-link::after {
    content: "";
    position: absolute;
    inset: 0;
  }

  .stream-card:has(.card-link:focus-visible) {
    outline: 2px solid var(--vercel-text);
    outline-offset: -2px;
  }

  .card-link:focus-visible {
    outline: none;
  }
</style>
