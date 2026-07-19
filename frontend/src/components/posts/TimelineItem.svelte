<script lang="ts">
  import { marked } from "marked";
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
  } = $props();

  let menuOpen = false;
  let profileHref = $derived(userId ? `/users/${userId}` : "#");

  function handleClickOutside(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest(".timeline-menu")) {
      menuOpen = false;
    }
  }
</script>

<svelte:window on:click={handleClickOutside} />

<div class="relative mb-6 ml-7">
  <div class="card">
    <!-- Header -->
    <div class="flex items-center gap-2 px-4 py-2 border-b" style="border-color: var(--vercel-border);">
      <a href={profileHref} class="avatar avatar-sm no-underline hover:opacity-80 transition-opacity" style="cursor: {userId ? 'pointer' : 'default'};">
        {(username ?? "?")[0].toUpperCase()}
      </a>
      <a href={profileHref} class="text-sm font-medium no-underline hover:underline" style="color: var(--vercel-text); cursor: {userId ? 'pointer' : 'default'};">{username ?? "匿名"}</a>
      <span class="text-xs" style="color: var(--vercel-text-tertiary);">{timeAgo(createdAt)}</span>

      {#if onReply || onDelete}
        <div class="ml-auto timeline-menu relative">
          <button
            class="btn-icon"
            style="width: 1.5rem; height: 1.5rem;"
            on:click|stopPropagation={() => (menuOpen = !menuOpen)}
          >
            <span class="text-sm leading-none" style="color: var(--vercel-text-tertiary);">⋮</span>
          </button>

          {#if menuOpen}
            <div class="menu-dropdown absolute right-0 top-full mt-1 z-50" style="min-width: 8rem;">
              {#if onReply}
                <button class="menu-item" on:click={() => { menuOpen = false; onReply(); }}>
                  回复
                </button>
              {/if}
              {#if onDelete}
                <button class="menu-item menu-item-danger" on:click={() => { menuOpen = false; onDelete(); }}>
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
        {@html marked.parse(content, { breaks: true, gfm: true })}
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
