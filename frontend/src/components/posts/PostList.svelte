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
      // ignore
    } finally {
      loading = false;
    }
  });
</script>

{#if loading}
  <div class="empty-state">
    <div class="spinner mb-3"></div>
    加载中...
  </div>
{:else if posts.length === 0}
  <div class="empty-state">
    <p>还没有帖子</p>
    <a href="/posts/new" class="btn btn-ghost btn-sm mt-3">发布第一条</a>
  </div>
{:else}
  {#each posts as post (post.id)}
    <PostCard {post} />
  {/each}
{/if}