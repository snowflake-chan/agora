<script lang="ts">
  import type { FeedItem } from "../lib/posts";
  import { stripMarkdown } from "../lib/utils";
  import AuthorMeta from "./AuthorMeta.svelte";

  export let item: FeedItem;

  const STATUS_MAP: Record<string, { label: string; cls: string }> = {
    draft: { label: "草稿", cls: "bg-surface-300 text-surface-700" },
    voting: { label: "投票中", cls: "bg-warning-500 text-white" },
    passed: { label: "通过待合并", cls: "bg-info-500 text-white" },
    merged: { label: "已合并", cls: "bg-success-500 text-white" },
    rejected: { label: "未通过", cls: "bg-error-500 text-white" },
    failed: { label: "合并失败", cls: "bg-error-500 text-white" },
  };

  $: snippet = stripMarkdown(item.content);
  $: href = item.type === "post" ? `/posts/${item.id}` : `/patches/${item.id}`;
  $: statusInfo = item.type === "patch" && item.status ? STATUS_MAP[item.status] : null;
</script>

<a
  href={href}
  class="group block border-b border-surface-200-800/50 px-4 py-4 transition-colors hover:bg-surface"
>
  <div class="flex items-center gap-2">
    {#if item.type === "patch"}
      {#if statusInfo}
        <span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium {statusInfo.cls}">
          {statusInfo.label}
        </span>
      {/if}
      {#if item.pr_number}
        <span class="text-xs text-surface-400">PR #{item.pr_number}</span>
      {/if}
    {:else}
      <span class="inline-flex items-center rounded-full bg-surface-200 px-2 py-0.5 text-xs text-surface-600">
        帖子
      </span>
    {/if}
  </div>

  <h2 class="mt-1 text-base font-semibold text-surface-900-100 group-hover:text-primary-700">
    {item.title}
  </h2>

  <p class="mt-1 line-clamp-2 text-sm text-surface-500">
    {snippet}
  </p>

  <div class="mt-2 flex items-center justify-between gap-2">
    <div class="flex items-center gap-3 text-xs text-surface-400-600">
      {#if item.type === "post" && item.tags && item.tags.length > 0}
        <span>{item.tags.join(", ")}</span>
      {/if}
      {#if item.type === "patch"}
        <span>赞成 {item.for_count} · 反对 {item.against_count}</span>
      {/if}
      {#if item.type === "post"}
        <span class="flex items-center gap-1">
          <svg class="size-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
          {item.reply_count}
        </span>
      {/if}
    </div>

    <AuthorMeta username={item.author_username ?? "匿名"} createdAt={item.created_at} />
  </div>
</a>
