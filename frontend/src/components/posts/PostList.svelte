<script lang="ts">
  import { onMount } from "svelte";
  import { translator } from "../../lib/i18n";
  import { onModerationUpdate } from "../../lib/moderation";
  import { listPosts, type Post } from "../../lib/posts";
  import PostCard from "./PostCard.svelte";
  import PostForm from "./PostForm.svelte";

  let posts = $state<Post[]>([]);
  let loading = $state(true);
  let showPostForm = $state(false);

  async function loadPosts() {
    try {
      posts = await listPosts();
    } catch {
      // ignore
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    void loadPosts();
    return onModerationUpdate(() => void loadPosts());
  });
</script>

{#if loading}
  <div class="empty-state">
    <div class="spinner mb-3"></div>
    {$translator("common.loading")}
  </div>
{:else if posts.length === 0}
  <div class="empty-state">
    <p>{$translator("post.empty")}</p>
    <a href="/posts/new" class="btn btn-ghost btn-sm mt-3" onclick={(e) => { e.preventDefault(); showPostForm = true; }}>{$translator("post.first")}</a>
  </div>
{:else}
  {#each posts as post (post.id)}
    <PostCard {post} />
  {/each}
{/if}

{#if showPostForm}
  <PostForm onClose={() => (showPostForm = false)} onSubmitted={() => { showPostForm = false; loadPosts(); }} />
{/if}
