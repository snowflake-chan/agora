<script lang="ts">
  import { onDestroy, onMount, tick } from "svelte";
  import { API_BASE } from "../lib/config";
  import { translator } from "../lib/i18n";
  import { getFeed, type FeedItem, type FeedMode } from "../lib/posts";
  import FeedCard from "./FeedCard.svelte";

  let {
    onSelect = null,
    selectedId = null,
    onFirstItem = null,
    onStateChange = null,
    onItemsUpdated = null,
    mode = "recommended",
  }: {
    onSelect?: ((item: FeedItem) => void) | null;
    selectedId?: string | null;
    onFirstItem?: ((item: FeedItem) => void) | null;
    onStateChange?: ((state: "loading" | "ready" | "empty" | "error") => void) | null;
    onItemsUpdated?: ((items: FeedItem[]) => void) | null;
    mode?: FeedMode;
  } = $props();

  // ---- reactive state (all $state for Svelte 5 runes mode) ----
  let items = $state<FeedItem[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let page = $state(1);
  let hasMore = $state(true);
  let busy = $state(false);
  let refreshing = $state(false);
  let liveState = $state<"connecting" | "connected" | "reconnecting">("connecting");

  // ---- non-reactive: DOM refs and internal bookkeeping ----
  let sentinel: HTMLDivElement;
  let observer: IntersectionObserver | null = null;
  let eventSource: EventSource | null = null;
  let refreshTimer: ReturnType<typeof setTimeout> | null = null;
  let refreshPending = false;
  let removedIds = new Set<string>();
  let loaded = new Set<number>();

  onMount(async () => {
    onStateChange?.("loading");
    await loadOnce();
    loading = false;
    onStateChange?.(error ? "error" : items.length ? "ready" : "empty");
    connectFeedStream();
    document.addEventListener("visibilitychange", handleVisibilityChange);
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
    eventSource?.close();
    eventSource = null;
    if (refreshTimer) clearTimeout(refreshTimer);
    document.removeEventListener("visibilitychange", handleVisibilityChange);
  });

  /** Load the current page, then increment. Each page# runs at most once. */
  async function loadOnce() {
    if (loaded.has(page) || busy) return;
    const requestedPage = page;
    loaded.add(requestedPage);
    busy = true;
    try {
      error = null;
      const next = await getFeed(requestedPage, mode);
      if (next.length === 0) { hasMore = false; return; }
      items = mergeUnique(items, next);
      onItemsUpdated?.(items);
      if (items.length === next.length && next[0]) onFirstItem?.(next[0]);
      page++;
    } catch {
      loaded.delete(requestedPage);
      error = "FEED_LOAD_FAILED";
    } finally {
      busy = false;
    }
  }

  function retry() {
    loadOnce();
  }

  function connectFeedStream() {
    eventSource?.close();
    eventSource = new EventSource(`${API_BASE}/posts/-/feed/stream`);
    eventSource.onopen = () => {
      liveState = "connected";
    };
    eventSource.onerror = () => {
      liveState = "reconnecting";
    };
    eventSource.addEventListener("feed", scheduleRefresh);
  }

  function scheduleRefresh(event?: Event) {
    if (event instanceof MessageEvent) {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "removed" && payload.item_id) {
          removedIds.add(payload.item_id);
        }
      } catch {}
    }
    if (refreshTimer) return;
    refreshTimer = setTimeout(() => {
      refreshTimer = null;
      refreshFirstPage();
    }, 450);
  }

  async function refreshFirstPage() {
    if (document.visibilityState !== "visible") {
      refreshPending = true;
      return;
    }
    if (refreshing) {
      refreshPending = true;
      return;
    }
    refreshing = true;
    try {
      const next = await getFeed(1, mode);
      const nextIds = new Set(next.map((item) => item.id));
      const retained = items.filter(
        (item) => !nextIds.has(item.id) && !removedIds.has(item.id),
      );
      items = mergeUnique(next, retained);
      removedIds.clear();
      onItemsUpdated?.(items);
      if (!selectedId && next[0]) onFirstItem?.(next[0]);
    } catch {
      // The next SSE event or the manual retry can recover a transient refresh.
    } finally {
      refreshing = false;
      if (refreshPending) {
        refreshPending = false;
        scheduleRefresh();
      }
    }
  }

  function handleVisibilityChange() {
    if (document.visibilityState === "visible" && refreshPending) {
      refreshPending = false;
      scheduleRefresh();
    }
  }

  function mergeUnique(first: FeedItem[], second: FeedItem[]): FeedItem[] {
    const seen = new Set<string>();
    return [...first, ...second].filter((item) => {
      if (seen.has(item.id)) return false;
      seen.add(item.id);
      return true;
    });
  }
</script>

{#if loading}
  <div class="empty-state">
    <div class="spinner mb-3"></div>
    {$translator("feed.loading")}
  </div>
{:else if error && items.length === 0}
  <div class="empty-state">
    <p style="color: var(--vercel-danger);">{$translator("feed.loadFailed")}</p>
    <p class="mt-1 text-sm" style="color: var(--vercel-text-tertiary);">
      {$translator("feed.loadFailedDescription")}
    </p>
    <button class="btn btn-secondary btn-sm mt-3" onclick={retry}>{$translator("feed.retry")}</button>
  </div>
{:else if items.length === 0}
  <div class="empty-state">
    <p>{$translator(mode === "following" ? "feed.emptyFollowing" : "feed.empty")}</p>
  </div>
{:else}
  <div class="feed-status" aria-live="polite">
    <span class:connected={liveState === "connected"} class="live-dot"></span>
    <span>{$translator(liveState === "connected" ? "feed.live" : "feed.reconnecting")}</span>
    {#if refreshing}<span class="status-update">{$translator("feed.updating")}</span>{/if}
  </div>
  {#each items as item (item.id)}
    <FeedCard {item} {onSelect} selected={selectedId === item.id} />
  {/each}

  <div
    bind:this={sentinel}
    class="flex justify-center py-6 text-sm text-surface-400"
  >
    {#if error}
      <div class="flex flex-col items-center gap-2">
        <span style="color: var(--vercel-danger);">{$translator("feed.moreFailed")}</span>
        <button class="btn btn-secondary btn-sm" onclick={retry}>{$translator("feed.retry")}</button>
      </div>
    {:else if busy}
      {$translator("feed.loadingMore")}
    {:else if !hasMore}
      {$translator("feed.noMore")}
    {/if}
  </div>
{/if}

<style>
  .feed-status {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    min-height: 2rem;
    padding: 0.45rem 1rem;
    border-bottom: 1px solid var(--vercel-border);
    color: var(--vercel-text-tertiary);
    font-size: 0.68rem;
  }

  .live-dot {
    width: 0.4rem;
    height: 0.4rem;
    border-radius: 50%;
    background: var(--vercel-warning);
    box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.1);
  }

  .live-dot.connected {
    background: var(--vercel-success);
    box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.1);
  }

  .status-update {
    margin-left: auto;
    color: var(--vercel-text-secondary);
  }
</style>
