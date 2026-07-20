<script lang="ts">
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

  let menuOpen = false;
  let guild = $state<UserGuildBadge | null>(null);
  let profileHref = $derived(userId ? `/users/${userId}` : "#");

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
</script>

<svelte:window on:click={handleClickOutside} />

<div id={contentId ?? undefined} class="relative mb-6 ml-7 content-node">
  <div class="card">
    <!-- Header -->
    <div class="flex items-center gap-2 px-4 py-2 border-b" style="border-color: var(--vercel-border);">
      <a href={profileHref} class="avatar avatar-sm no-underline hover:opacity-80 transition-opacity" style="cursor: {userId ? 'pointer' : 'default'};">
        {(username ?? "?")[0].toUpperCase()}
      </a>
      <a href={profileHref} class="text-sm font-medium no-underline hover:underline" style="color: var(--vercel-text); cursor: {userId ? 'pointer' : 'default'};">{username ?? $translator("common.anonymous")}</a>
      {#if guild}
        <a class="timeline-guild" href={`/guilds/${guild.guild_id}`}>
          Lv.{guild.guild_level} {guild.guild_name}
        </a>
      {/if}
      <span class="text-xs" style="color: var(--vercel-text-tertiary);">{timeAgo(createdAt)}</span>

      {#if onReply || onDelete || onReport}
        <div class="ml-auto timeline-menu relative">
          <button
            class="btn-icon"
            style="width: 1.5rem; height: 1.5rem;"
            on:click|stopPropagation={() => (menuOpen = !menuOpen)}
            aria-label={$translator("common.moreActions")}
            aria-expanded={menuOpen}
          >
            <span class="text-sm leading-none" style="color: var(--vercel-text-tertiary);">⋮</span>
          </button>

          {#if menuOpen}
            <div class="menu-dropdown absolute right-0 top-full mt-1 z-50" style="min-width: 8rem;">
              {#if onReply}
                <button class="menu-item" on:click={() => { menuOpen = false; onReply(); }}>
                  {$translator("common.reply")}
                </button>
              {/if}
              {#if onReport}
                <button class="menu-item" on:click={() => { menuOpen = false; onReport(); }}>
                  {$translator("common.report")}
                </button>
              {/if}
              {#if onDelete}
                <button class="menu-item menu-item-danger" on:click={() => { menuOpen = false; onDelete(); }}>
                  {$translator("common.delete")}
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
          on:click={onLike}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" fill={liked ? "currentColor" : "none"}>
            <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.8-7.5 1.1-1.1a5.5 5.5 0 0 0-.1-7.8Z"/>
          </svg>
          <span>{$translator("common.like")}</span>
          {#if likeCount > 0}<span class="action-count">{likeCount}</span>{/if}
        </button>
        <button type="button" class="post-action" on:click={onDiscuss}>
          <svg viewBox="0 0 24 24" aria-hidden="true" fill="none">
            <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M21 12a8.4 8.4 0 0 1-9 8 9.8 9.8 0 0 1-4.3-1L3 20l1.4-3.7A7.4 7.4 0 0 1 3 12a8.4 8.4 0 0 1 9-8 8.4 8.4 0 0 1 9 8Z"/>
          </svg>
          <span>{$translator("common.reply")}</span>
          {#if replyCount > 0}<span class="action-count">{replyCount}</span>{/if}
        </button>
        <button type="button" class="post-action" on:click={onShare}>
          <svg viewBox="0 0 24 24" aria-hidden="true" fill="none">
            <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M16 6l-4-4-4 4M12 2v14"/>
          </svg>
          <span>{$translator("common.share")}</span>
        </button>
      </div>
    {/if}
  </div>
</div>

<style>
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
    background: rgba(255, 255, 255, 0.05);
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
    color: #f47286;
  }

  .post-action svg {
    width: 1rem;
    height: 1rem;
  }

  .action-count {
    font-variant-numeric: tabular-nums;
  }
</style>
