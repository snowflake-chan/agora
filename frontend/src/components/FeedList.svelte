<script lang="ts">
  import { onMount, tick } from "svelte";
  import { getFeed, type FeedItem } from "../lib/posts";
  import FeedCard from "./FeedCard.svelte";

  let items: FeedItem[] = [];
  let loading = true;
  let page = 1;
  let hasMore = true;
  let busy = false;
  let sentinel: HTMLDivElement;
  let observer: IntersectionObserver | null = null;

  onMount(async () => {
    await loadOnce();
    loading = false;
    await tick();
    if (!sentinel || observer) return;
    observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && hasMore && !busy) {
        loadOnce();
      }
    }, { rootMargin: "300px" });
    observer.observe(sentinel);
  });

  /** Load the current page, then increment. Each page# runs at most once. */
  let loaded = new Set<number>();
  async function loadOnce() {
    if (loaded.has(page) || busy) return;
    loaded.add(page);
    busy = true;
    try {
      let next = await getFeed(page);
      if (next.length === 0) { hasMore = false; return; }
      items = [...items, ...next];
      page++;
    } catch { /* ignore */ }
    finally { busy = false; }
  }
</script>

{#if loading}
  <div class="empty-state">加载中…</div>
{:else if items.length === 0}
  <div class="empty-state">
    <p>还没有内容</p>
  </div>
{:else}
  {#each items as item (item.id)}
    <FeedCard {item} />
  {/each}

  <div
    bind:this={sentinel}
    class="flex justify-center py-6 text-sm text-surface-400"
  >
    {#if busy}
      加载中…
    {:else if !hasMore}
      没有更多了
    {/if}
  </div>
{/if}
