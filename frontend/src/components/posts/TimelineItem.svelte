<script lang="ts">
  import { Menu } from "@skeletonlabs/skeleton-svelte";
  import { marked } from "marked";

  export let username: string;
  export let createdAt: string;
  export let content: string;
  export let title: string | null = null;
  export let tags: string[] | null = null;
  export let replyingToUsername: string | null = null;
  export let onReply: (() => void) | null = null;

  function timeAgo(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "刚刚";
    if (mins < 60) return `${mins} 分钟前`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours} 小时前`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days} 天前`;
    return new Date(dateStr).toLocaleDateString("zh-CN");
  }
</script>

<div class="relative z-10 mb-6 ml-7 markdown-container">
  <!-- Card -->
  <div class="rounded-md border border-surface-200 bg-white">
    <!-- Header -->
    <div class="flex items-center gap-2 rounded-t-md bg-surface-50 border-b border-surface-100 px-4 py-2">
      <div
        class="flex size-5 items-center justify-center rounded-full bg-surface-300 text-[9px] font-bold text-surface-600"
      >
        {(username ?? "?")[0].toUpperCase()}
      </div>
      <span class="text-sm font-medium text-surface-700">{username ?? "匿名"}</span>
      <span class="text-xs text-surface-400">{timeAgo(createdAt)}</span>
      <div class="ml-auto">
        <Menu>
          <Menu.Trigger class="flex size-6 items-center justify-center rounded-md text-surface-400 hover:bg-surface-200 hover:text-surface-600">
            <span class="text-lg leading-none">⋮</span>
          </Menu.Trigger>
          <Menu.Positioner>
            <Menu.Content class="min-w-28 rounded-md">
              {#if onReply}
                <Menu.Item value="reply" onclick={onReply}>
                  <Menu.ItemText>回复</Menu.ItemText>
                </Menu.Item>
              {/if}
            </Menu.Content>
          </Menu.Positioner>
        </Menu>
      </div>
    </div>

    <!-- Body -->
    <div class="px-4 py-3 text-sm">
      {#if title}
        <h1 class="mb-2 text-lg font-bold text-surface-900">{title}</h1>
        <div class="mb-3 border-b border-surface-100"></div>
      {/if}
      {#if replyingToUsername}
        <span class="mr-1 font-medium text-primary-600">@{replyingToUsername}</span>
      {/if}
      <div class="markdown-body">
        {@html marked.parse(content, { breaks: true, gfm: true })}
      </div>
      {#if tags && tags.length > 0}
        <div class="mt-3 flex flex-wrap gap-2">
          {#each tags as tag}
            <span class="rounded-full bg-surface-100 px-2.5 py-0.5 text-xs text-surface-600">{tag}</span>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</div>

