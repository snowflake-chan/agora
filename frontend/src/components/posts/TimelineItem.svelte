<script lang="ts">
  import { Menu } from "@skeletonlabs/skeleton-svelte";
  import { marked } from "marked";
  import { timeAgo } from "../../lib/utils";

  export let username: string;
  export let createdAt: string;
  export let content: string;
  export let title: string | null = null;
  export let tags: string[] | null = null;
  export let replyingToUsername: string | null = null;
  export let onReply: (() => void) | null = null;
</script>

<div class="relative z-10 mb-6 ml-7 markdown-container">
  <!-- Card -->
  <div class="rounded-md border border-surface-200-800 bg-surface">
    <!-- Header -->
    <div class="flex items-center gap-2 rounded-t-md bg-surface-100-900 border-b border-surface-200-800 px-4 py-2">
      <div
        class="flex size-5 items-center justify-center rounded-full bg-surface-300-700 text-[9px] font-bold text-surface-600-400"
      >
        {(username ?? "?")[0].toUpperCase()}
      </div>
      <span class="text-sm font-medium text-surface-700-300">{username ?? "匿名"}</span>
      <span class="text-xs text-surface-400-600">{timeAgo(createdAt)}</span>
      <div class="ml-auto">
        <Menu>
          <Menu.Trigger class="flex size-6 items-center justify-center rounded-md text-surface-400-600 hover:bg-surface-200-800 hover:text-surface-600-400">
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
            <span class="rounded-full bg-surface-100 px-2.5 py-0.5 text-xs text-surface-600-400">{tag}</span>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</div>

