<script lang="ts">
  import { onMount } from "svelte";
  import { getFeed, type FeedItem } from "../lib/posts";
  import FeedCard from "./FeedCard.svelte";

  let items: FeedItem[] = [];
  let loading = true;
  let loadingMore = false;
  let page = 1;
  let hasMore = true;
  let sentinel: HTMLDivElement;

  onMount(async () => {
    await loadPage();
    loading = false;

    // IntersectionObserver for infinite scroll
    const observer = new IntersectionObserver(async (entries) => {
      if (entries[0].isIntersecting && hasMore && !loadingMore) {
        await loadPage();
      }
    }, { rootMargin: "200px" });

    observer.observe(sentinel);

    return () => observer.disconnect();
  });

  async function loadPage() {
    loadingMore = page > 1;
    try {
      const next = await getFeed(page);
      if (next.length === 0) {
        hasMore = false;
        return;
      }
      items = [...items, ...next];
      page++;
    } catch {
      // ignore
    } finally {
      loadingMore = false;
    }
  }
</script>

{#if loading}
  <div class="flex justify-center py-12 text-sm text-surface-400">加载中…</div>
{:else if items.length === 0}
  <div class="flex flex-col items-center justify-center py-12 text-sm text-surface-400">
    <p>还没有内容</p>
    <a href="/posts/new" class="mt-2 text-primary-600 hover:text-primary-700">发布第一条</a>
  </div>
{:else}
  {#each items as item (item.id)}
    <FeedCard {item} />
  {/each}

  <!-- sentinel for infinite scroll -->
  <div
    bind:this={sentinel}
    class="flex justify-center py-6 text-sm text-surface-400"
  >
    {#if loadingMore}
      加载中…
    {:else if !hasMore}
      没有更多了
    {/if}
  </div>
{/if}
