<script lang="ts">
  import { onDestroy, onMount, tick } from "svelte";
  import { getFeed, type FeedItem } from "../lib/posts";
  import FeedCard from "./FeedCard.svelte";

  let {
    onSelect = null,
    selectedId = null,
    onFirstItem = null,
    onStateChange = null,
  }: {
    onSelect?: ((item: FeedItem) => void) | null;
    selectedId?: string | null;
    onFirstItem?: ((item: FeedItem) => void) | null;
    onStateChange?: ((state: "loading" | "ready" | "empty" | "error") => void) | null;
  } = $props();

  // ---- reactive state (all $state for Svelte 5 runes mode) ----
  let items = $state<FeedItem[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let page = $state(1);
  let hasMore = $state(true);
  let busy = $state(false);

  // ---- non-reactive: DOM refs and internal bookkeeping ----
  let sentinel: HTMLDivElement;
  let observer: IntersectionObserver | null = null;
  let loaded = new Set<number>();

  onMount(async () => {
    onStateChange?.("loading");
    await loadOnce();
    loading = false;
    onStateChange?.(error ? "error" : items.length ? "ready" : "empty");
    await tick();
    if (!sentinel || observer) return;
    observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && hasMore && !busy) {
        loadOnce();
      }
    }, { rootMargin: "300px" });
    observer.observe(sentinel);
  });

  onDestroy(() => {
    observer?.disconnect();
    observer = null;
  });

  /** Load the current page, then increment. Each page# runs at most once. */
  async function loadOnce() {
    if (loaded.has(page) || busy) return;
    const requestedPage = page;
    loaded.add(requestedPage);
    busy = true;
    try {
      error = null;
      const next = await getFeed(requestedPage);
      if (next.length === 0) { hasMore = false; return; }
      items = [...items, ...next];
      if (items.length === next.length && next[0]) onFirstItem?.(next[0]);
      page++;
    } catch (e) {
      loaded.delete(requestedPage);
      error = e instanceof Error ? e.message : "加载失败";
    } finally {
      busy = false;
    }
  }

  function retry() {
    loadOnce();
  }
</script>

{#if loading}
  <div class="empty-state">
    <div class="spinner mb-3"></div>
    加载中…
  </div>
{:else if error && items.length === 0}
  <div class="empty-state">
    <p style="color: var(--vercel-danger);">动态加载失败</p>
    <p class="mt-1 text-sm" style="color: var(--vercel-text-tertiary);">
      请检查网络连接后重试
    </p>
    <button class="btn btn-secondary btn-sm mt-3" onclick={retry}>重试</button>
  </div>
{:else if items.length === 0}
  <div class="empty-state">
    <p>还没有内容</p>
  </div>
{:else}
  {#each items as item (item.id)}
    <FeedCard {item} {onSelect} selected={selectedId === item.id} />
  {/each}

  <div
    bind:this={sentinel}
    class="flex justify-center py-6 text-sm text-surface-400"
  >
    {#if error}
      <div class="flex flex-col items-center gap-2">
        <span style="color: var(--vercel-danger);">更多内容加载失败</span>
        <button class="btn btn-secondary btn-sm" onclick={retry}>重试</button>
      </div>
    {:else if busy}
      加载中…
    {:else if !hasMore}
      没有更多了
    {/if}
  </div>
{/if}
