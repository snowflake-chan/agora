<script lang="ts">
  import type { Post } from "../../lib/posts";
  import { stripMarkdown } from "../../lib/utils";
  import AuthorMeta from "../AuthorMeta.svelte";

  let { post }: { post: Post } = $props();

  let snippet = $derived(stripMarkdown(post.content));
</script>

<article
  class="post-card relative px-4 py-4 border-b transition-colors"
  style="border-color: var(--vercel-border);"
  onmouseenter={(e) => e.currentTarget.style.background = '#141417'}
  onmouseleave={(e) => e.currentTarget.style.background = ''}
>
  <h2 class="text-base font-semibold">
    <a class="card-link" href={`/posts/${post.id}`} style="color: var(--vercel-text);">
      {post.title}
    </a>
  </h2>

  <p class="mt-1 line-clamp-2 text-sm" style="color: var(--vercel-text-secondary);">
    {snippet}
  </p>

  <div class="mt-2 flex items-center justify-between gap-2">
    <div class="flex items-center gap-3 text-xs" style="color: var(--vercel-text-tertiary);">
      {#if post.tags && post.tags.length > 0}
        <span>{post.tags.join(", ")}</span>
      {/if}
      <span class="flex items-center gap-1">
        <svg class="size-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
        {post.reply_count}
      </span>
    </div>

    <AuthorMeta username={post.author_username ?? "匿名"} userId={post.author_id} createdAt={post.created_at} />
  </div>
</article>

<style>
  .card-link::after {
    content: "";
    position: absolute;
    inset: 0;
  }

  .post-card:has(.card-link:focus-visible) {
    outline: 2px solid var(--vercel-text);
    outline-offset: -2px;
  }

  .card-link:focus-visible {
    outline: none;
  }
</style>
