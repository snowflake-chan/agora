<script lang="ts">
  import type { FeedItem } from "../lib/posts";
  import { stripMarkdown } from "../lib/utils";
  import AuthorMeta from "./AuthorMeta.svelte";

  let {
    item,
    selected = false,
    onSelect = null,
  }: {
    item: FeedItem;
    selected?: boolean;
    onSelect?: ((item: FeedItem) => void) | null;
  } = $props();

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
    <span class="content-kind">{item.type === "post" ? "讨论" : "变更"}</span>
    {#if item.type === "patch"}
      {#if statusInfo}
        <span class="badge {statusInfo.cls}">
          {statusInfo.label}
        </span>
      {/if}
      {#if item.pr_number}
        <span class="text-xs" style="color: var(--vercel-text-tertiary);">PR #{item.pr_number}</span>
      {/if}
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
          <svg class="size-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.8-7.5 1.1-1.1a5.5 5.5 0 0 0-.1-7.8Z"/></svg>
          {item.like_count}
        </span>
      {/if}
      <span class="flex items-center gap-1">
        <svg class="size-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
        {item.reply_count}
      </span>
    </div>

    <AuthorMeta username={item.author_username ?? "匿名"} userId={item.author_id} createdAt={item.created_at} />
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
    background: rgba(255, 255, 255, 0.035);
  }

  .stream-card.active {
    background: rgba(255, 255, 255, 0.055);
    box-shadow: inset 2px 0 var(--vercel-text);
  }

  .stream-card-topline {
    display: flex;
    min-height: 1.25rem;
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
