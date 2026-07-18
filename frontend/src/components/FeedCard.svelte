<script lang="ts">
  import type { FeedItem } from "../lib/posts";
  import { stripMarkdown } from "../lib/utils";
  import AuthorMeta from "./AuthorMeta.svelte";

  let { item }: { item: FeedItem } = $props();

  const STATUS_MAP: Record<string, { label: string; cls: string }> = {
    draft: { label: "草稿", cls: "badge-neutral" },
    voting: { label: "投票中", cls: "badge-warning" },
    passed: { label: "通过待合并", cls: "badge-info" },
    merged: { label: "已合并", cls: "badge-success" },
    rejected: { label: "未通过", cls: "badge-danger" },
    failed: { label: "合并失败", cls: "badge-danger" },
  };

  let snippet = $derived(stripMarkdown(item.content));
  let href = $derived(item.type === "post" ? `/posts/${item.id}` : `/patches/${item.id}`);
  let statusInfo = $derived(
    item.type === "patch" && item.status ? STATUS_MAP[item.status] : null
  );
</script>

<a
  href={href}
  class="block px-4 py-4 border-b transition-colors"
  style="border-color: var(--vercel-border);"
  onmouseenter={(e) => e.currentTarget.style.background = '#141417'}
  onmouseleave={(e) => e.currentTarget.style.background = ''}
>
  {#if item.type === "patch"}
    <div class="flex items-center gap-2">
      {#if statusInfo}
        <span class="badge {statusInfo.cls}">
          {statusInfo.label}
        </span>
      {/if}
      {#if item.pr_number}
        <span class="text-xs" style="color: var(--vercel-text-tertiary);">PR #{item.pr_number}</span>
      {/if}
    </div>
  {/if}

  <h2 class="mt-1 text-base font-semibold" style="color: var(--vercel-text);">
    {item.title}
  </h2>

  <p class="mt-1 line-clamp-2 text-sm" style="color: var(--vercel-text-secondary);">
    {snippet}
  </p>

  <div class="mt-2 flex items-center justify-between gap-2">
    <div class="flex items-center gap-3 text-xs" style="color: var(--vercel-text-tertiary);">
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