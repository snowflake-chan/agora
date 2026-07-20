<script lang="ts">
  import {
    EllipsisIcon,
    FlagIcon,
    HeartIcon,
    MessageCircleIcon,
    ReplyIcon,
    Share2Icon,
    Trash2Icon,
  } from "@lucide/svelte";
  import { onMount } from "svelte";
  import { getUserGuild, type UserGuildBadge } from "../../lib/guilds";
  import { translator } from "../../lib/i18n";
  import { renderMarkdown } from "../../lib/markdown";
  import { timeAgo } from "../../lib/utils";

  let {
    username,
    userId = null,
    createdAt,
    content,
    title = null,
    tags = null,
    replyingToUsername = null,
    onReply = null,
    onDelete = null,
    onReport = null,
    liked = false,
    likeCount = null,
    replyCount = null,
    liking = false,
    onLike = null,
    onDiscuss = null,
    onShare = null,
    contentId = null,
    replyingToContent = null,
    replyingToId = null,
  }: {
    username: string;
    userId: string | null;
    createdAt: string;
    content: string;
    title: string | null;
    tags: string[] | null;
    replyingToUsername: string | null;
    onReply: (() => void) | null;
    onDelete: (() => void) | null;
    onReport?: (() => void) | null;
    liked?: boolean;
    likeCount?: number | null;
    replyCount?: number | null;
    liking?: boolean;
    onLike?: (() => void) | null;
    onDiscuss?: (() => void) | null;
    onShare?: (() => void) | null;
    contentId?: string | null;
    replyingToContent?: string | null;
    replyingToId?: string | null;
  } = $props();

  let menuOpen = $state(false);
  let menuButton = $state<HTMLButtonElement | null>(null);
  let guild = $state<UserGuildBadge | null>(null);
  let profileHref = $derived(userId ? `/users/${userId}` : "#");
  let menuId = $derived(
    `timeline-actions-${(contentId ?? `${userId ?? "anonymous"}-${createdAt}`).replace(/[^a-zA-Z0-9_-]/g, "-")}`,
  );

  onMount(async () => {
    if (!userId) return;
    try {
      guild = await getUserGuild(userId);
    } catch {
      guild = null;
    }
  });

  function handleClickOutside(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest(".timeline-menu")) {
      menuOpen = false;
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (!menuOpen || event.key !== "Escape") return;
    event.preventDefault();
    menuOpen = false;
    menuButton?.focus();
  }

  function runMenuAction(action: () => void) {
    menuOpen = false;
    action();
  }
</script>

<svelte:window onclick={handleClickOutside} onkeydown={handleKeydown} />

<div id={contentId ?? undefined} class="relative mb-6 ml-7 content-node">
  <div class="card">
    <!-- Header -->
    <div class="timeline-header px-4 py-2 border-b" style="border-color: var(--vercel-border);">
      <a href={profileHref} class="avatar avatar-sm no-underline hover:opacity-80 transition-opacity" style="cursor: {userId ? 'pointer' : 'default'};">
        {(username ?? "?")[0].toUpperCase()}
      </a>
      <div class="timeline-identity">
        <a href={profileHref} class="timeline-author text-sm font-medium no-underline hover:underline" style="cursor: {userId ? 'pointer' : 'default'};">{username ?? $translator("common.anonymous")}</a>
        {#if guild}
          <a class="timeline-guild" href={`/guilds/${guild.guild_id}`}>
            Lv.{guild.guild_level} {guild.guild_name}
          </a>
        {/if}
        <span class="timeline-time text-xs">{timeAgo(createdAt)}</span>
      </div>

      {#if onReply || onDelete || onReport}
        <div class="timeline-menu relative">
          <button
            bind:this={menuButton}
            type="button"
            class="btn-icon timeline-menu-trigger"
            onclick={(event) => {
              event.stopPropagation();
              menuOpen = !menuOpen;
            }}
            aria-label={$translator("common.moreActions")}
            aria-expanded={menuOpen}
            aria-controls={menuOpen ? menuId : undefined}
            title={$translator("common.moreActions")}
          >
            <EllipsisIcon size={17} strokeWidth={2} aria-hidden="true" />
          </button>

          {#if menuOpen}
            <div
              id={menuId}
              class="menu-dropdown timeline-menu-dropdown absolute right-0 top-full mt-1"
              aria-label={$translator("common.moreActions")}
            >
              {#if onReply}
                <button type="button" class="menu-item" onclick={() => runMenuAction(onReply)}>
                  <ReplyIcon size={15} strokeWidth={1.8} aria-hidden="true" />
                  <span>{$translator("common.reply")}</span>
                </button>
              {/if}
              {#if onReport}
                <button type="button" class="menu-item" onclick={() => runMenuAction(onReport)}>
                  <FlagIcon size={15} strokeWidth={1.8} aria-hidden="true" />
                  <span>{$translator("common.report")}</span>
                </button>
              {/if}
              {#if onDelete}
                <button type="button" class="menu-item menu-item-danger" onclick={() => runMenuAction(onDelete)}>
                  <Trash2Icon size={15} strokeWidth={1.8} aria-hidden="true" />
                  <span>{$translator("common.delete")}</span>
                </button>
              {/if}
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Body -->
    <div class="px-4 py-3 text-sm" style="color: var(--vercel-text-secondary);">
      {#if replyingToUsername}
        <a href={replyingToId ? `#${replyingToId}` : undefined} class="reply-trace">
          <span>{$translator("common.replyingTo", { name: replyingToUsername })}</span>
          {#if replyingToContent}
            <span class="reply-trace-copy">{replyingToContent}</span>
          {/if}
        </a>
      {/if}
      <div class="markdown-body">
        {@html renderMarkdown(content)}
      </div>
      {#if tags && tags.length > 0}
        <div class="mt-3 flex flex-wrap gap-2">
          {#each tags as tag}
            <span class="badge badge-neutral">{tag}</span>
          {/each}
        </div>
      {/if}
    </div>

    {#if likeCount !== null && replyCount !== null}
      <div class="post-actions" aria-label={$translator("post.actions")}>
        <button
          type="button"
          class:active={liked}
          class="post-action"
          aria-pressed={liked}
          aria-label={$translator(liked ? "common.unlike" : "common.like")}
          disabled={liking}
          onclick={onLike}
        >
          <HeartIcon size={16} strokeWidth={1.8} fill={liked ? "currentColor" : "none"} aria-hidden="true" />
          <span>{$translator("common.like")}</span>
          {#if likeCount > 0}<span class="action-count">{likeCount}</span>{/if}
        </button>
        <button type="button" class="post-action" onclick={onDiscuss}>
          <MessageCircleIcon size={16} strokeWidth={1.8} aria-hidden="true" />
          <span>{$translator("common.reply")}</span>
          {#if replyCount > 0}<span class="action-count">{replyCount}</span>{/if}
        </button>
        <button type="button" class="post-action" onclick={onShare}>
          <Share2Icon size={16} strokeWidth={1.8} aria-hidden="true" />
          <span>{$translator("common.share")}</span>
        </button>
      </div>
    {/if}
  </div>
</div>

<style>
  .timeline-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .timeline-identity {
    display: flex;
    min-width: 0;
    flex: 1;
    align-items: center;
    gap: 0.45rem;
  }

  .timeline-author {
    overflow: hidden;
    min-width: 0;
    color: var(--vercel-text);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .timeline-time {
    flex: 0 0 auto;
    color: var(--vercel-text-tertiary);
    white-space: nowrap;
  }

  .timeline-menu-trigger {
    width: 2rem;
    height: 2rem;
    color: var(--vercel-text-tertiary);
  }

  .timeline-menu-dropdown {
    z-index: var(--z-dropdown);
    min-width: 9.5rem;
  }

  .timeline-menu-dropdown :global(.menu-item) {
    min-height: 2.25rem;
    gap: 0.625rem;
  }

  .timeline-menu-dropdown :global(svg) {
    flex: 0 0 auto;
  }

  .timeline-guild {
    overflow: hidden;
    max-width: 8rem;
    padding: 0.05rem 0.35rem;
    border: 1px solid color-mix(in srgb, var(--vercel-warning) 28%, transparent);
    border-radius: 999px;
    color: var(--vercel-warning);
    background: color-mix(in srgb, var(--vercel-warning) 10%, transparent);
    font-size: 0.56rem;
    font-weight: 700;
    line-height: 1.5;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .post-actions {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    border-top: 1px solid var(--vercel-border);
    padding: 0.25rem;
  }

  .content-node {
    scroll-margin-top: 5rem;
  }

  .reply-trace {
    display: block;
    margin-bottom: 0.75rem;
    padding-left: 0.75rem;
    border-left: 2px solid var(--vercel-border-hover);
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
    line-height: 1.45;
  }

  .reply-trace:hover {
    color: var(--vercel-text-secondary);
  }

  .reply-trace-copy {
    display: -webkit-box;
    overflow: hidden;
    margin-top: 0.2rem;
    color: var(--vercel-text-secondary);
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }

  .post-action {
    display: inline-flex;
    min-height: 2.5rem;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    border-radius: 0.375rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.8125rem;
    font-weight: 500;
    transition: color 150ms ease, background 150ms ease;
  }

  .post-action:hover:not(:disabled) {
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .post-action:focus-visible {
    outline: 2px solid var(--vercel-text-secondary);
    outline-offset: -2px;
  }

  .post-action:disabled {
    cursor: wait;
    opacity: 0.55;
  }

  .post-action.active {
    color: var(--vercel-danger);
  }

  .post-action svg {
    width: 1rem;
    height: 1rem;
  }

  .action-count {
    font-variant-numeric: tabular-nums;
  }

  @media (max-width: 30rem) {
    .timeline-identity {
      flex-wrap: wrap;
      row-gap: 0.1rem;
    }

    .timeline-time {
      width: 100%;
    }
  }
</style>
