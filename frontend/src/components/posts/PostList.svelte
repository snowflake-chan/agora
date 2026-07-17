<script lang="ts">
  import { onMount } from "svelte";
  import { listPosts, type Post } from "../../lib/posts";
  import PostCard from "./PostCard.svelte";

  let posts: Post[] = [];
  let loading = true;

  onMount(async () => {
    try {
      posts = await listPosts();
    } catch {
      // ignore — show empty
    } finally {
      loading = false;
    }
  });
</script>

{#if loading}
  <div class="flex justify-center py-12 text-sm text-surface-400">加载中…</div>
{:else if posts.length === 0}
  <div class="flex flex-col items-center justify-center py-12 text-sm text-surface-400">
    <p>还没有帖子</p>
    <a href="/posts/new" class="mt-2 text-primary-600 hover:text-primary-700">发布第一条</a>
  </div>
{:else}
  {#each posts as post (post.id)}
    <PostCard {post} />
  {/each}
{/if}
