<script lang="ts">
  import { marked } from "marked";
  import { timeAgo } from "../../lib/utils";

  export let username: string;
  export let createdAt: string;
  export let content: string;
  export let title: string | null = null;
  export let tags: string[] | null = null;
  export let replyingToUsername: string | null = null;
  export let onReply: (() => void) | null = null;
  export let onDelete: (() => void) | null = null;

  let menuOpen = false;

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
      <div class="avatar avatar-sm">
        {(username ?? "?")[0].toUpperCase()}
      </div>
      <span class="text-sm font-medium" style="color: var(--vercel-text);">{username ?? "匿名"}</span>
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
      {#if title}
        <h1 class="mb-2 text-lg font-bold" style="color: var(--vercel-text);">{title}</h1>
        <hr class="divider mb-3" />
      {/if}
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