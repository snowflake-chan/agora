<script lang="ts">
  import { onMount } from "svelte";
  import { getFeed, type FeedItem } from "../lib/posts";
  import FeedCard from "./FeedCard.svelte";

  let items: FeedItem[] = [];
  let loading = true;

  onMount(async () => {
    try {
      items = await getFeed();
    } catch {
      // ignore
    } finally {
      loading = false;
    }
  });
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
{/if}
