<script lang="ts">
  import { onMount } from "svelte";
  import { renderMarkdown } from "../../lib/markdown";
  import { timeAgo } from "../../lib/utils";
  import { getUserGuild, type UserGuildBadge } from "../../lib/guilds";

  let {
    username,
    userId = null,
    contentId = null,
    createdAt,
    content,
    title = null,
    tags = null,
    replyingToUsername = null,
    onReply = null,
    onDelete = null,
    onReport = null,
  }: {
    username: string;
    userId: string | null;
    contentId: string | null;
    createdAt: string;
    content: string;
    title: string | null;
    tags: string[] | null;
    replyingToUsername: string | null;
    onReply: (() => void) | null;
    onDelete: (() => void) | null;
    onReport: (() => void) | null;
  } = $props();

  let menuOpen = $state(false);
  let badge = $state<UserGuildBadge | null>(null);
  let profileHref = $derived(userId ? `/users/${userId}` : "#");

  const _badgeCache: Record<string, UserGuildBadge | null> = {};

  onMount(async () => {
    if (!userId) return;
    if (userId in _badgeCache) { badge = _badgeCache[userId]; return; }
    try {
      badge = await getUserGuild(userId);
      _badgeCache[userId] = badge;
    } catch {
      _badgeCache[userId] = null;
    }
  });

  function handleClickOutside(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest(".timeline-menu")) {
      menuOpen = false;
    }
  }
</script>

<svelte:window onclick={handleClickOutside} />

<div class="relative mb-6 ml-7">
  <div class="card">
    <!-- Header -->
    <div class="flex items-center gap-2 px-4 py-2 border-b" style="border-color: var(--vercel-border);">
      <a href={profileHref} class="avatar avatar-sm no-underline hover:opacity-80 transition-opacity" style="cursor: {userId ? 'pointer' : 'default'};">
        {(username ?? "?")[0].toUpperCase()}
      </a>
      <a href={profileHref} class="text-sm font-medium no-underline hover:underline" style="color: var(--vercel-text); cursor: {userId ? 'pointer' : 'default'};">{username ?? "匿名"}</a>
      {#if badge}
        <a href="/guilds/{badge.guild_id}" class="no-underline" style="
          font-size: 9px; font-weight: 700; padding: 0 5px; border-radius: 99px; line-height: 1.6;
          color: var(--vercel-warning); background: rgba(245,158,11,0.12);
          border: 1px solid rgba(245,158,11,0.3); white-space: nowrap; display: inline-block;
        ">Lv.{badge.guild_level} {badge.guild_name}</a>
      {/if}
      <span class="text-xs" style="color: var(--vercel-text-tertiary);">{timeAgo(createdAt)}</span>

      {#if onReply || onDelete || onReport}
        <div class="ml-auto timeline-menu relative">
          <button
            class="btn-icon"
            style="width: 1.5rem; height: 1.5rem;"
            onclick={(e) => { e.stopPropagation(); menuOpen = !menuOpen; }}
            aria-label="更多操作"
            aria-expanded={menuOpen}
          >
            <span class="text-sm leading-none" style="color: var(--vercel-text-tertiary);" aria-hidden="true">⋮</span>
          </button>

          {#if menuOpen}
            <div class="menu-dropdown absolute right-0 top-full mt-1 z-50" style="min-width: 8rem;">
              {#if onReply}
                <button class="menu-item" onclick={() => { menuOpen = false; onReply(); }}>
                  回复
                </button>
              {/if}
              {#if onReport}
                <button class="menu-item" style="display:block;width:100%;text-align:left;" onclick={() => { menuOpen = false; onReport(); }}>
                  举报
                </button>
              {/if}
              {#if onDelete}
                <button class="menu-item menu-item-danger" style="display:block;width:100%;text-align:left;" onclick={() => { menuOpen = false; onDelete(); }}>
                  删除
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
        <span class="mr-1 font-medium" style="color: var(--vercel-text);">@{replyingToUsername}</span>
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
  </div>
</div>
