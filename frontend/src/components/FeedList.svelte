<script lang="ts">
  import { onMount, afterUpdate } from "svelte";
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
    await loadPage();
    loading = false;
  });

  afterUpdate(() => {
    // Set up observer once sentinel exists and we're not loading
    if (sentinel && !observer && !loading) {
      observer = new IntersectionObserver(async (entries) => {
        if (entries[0].isIntersecting && hasMore && !busy) {
          await loadPage();
        }
      }, { rootMargin: "200px" });
      observer.observe(sentinel);
    }
  });

  async function loadPage() {
    if (busy) return;
    busy = true;
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
      busy = false;
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
