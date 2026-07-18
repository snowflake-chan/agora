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
  <div class="empty-state">加载中…</div>
{:else if items.length === 0}
  <div class="empty-state">
    <p>还没有内容</p>
  </div>
{:else}
  {#each items as item (item.id)}
    <FeedCard {item} />
  {/each}
{/if}