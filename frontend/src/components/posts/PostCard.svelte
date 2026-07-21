<script lang="ts">
  import { HeartIcon, MessageCircleIcon } from "@lucide/svelte";
  import type { Post } from "../../lib/posts";
  import { translator } from "../../lib/i18n";
  import { stripMarkdown } from "../../lib/utils";
  import AuthorMeta from "../AuthorMeta.svelte";
  import PollCard from "./PollCard.svelte";

  let { post }: { post: Post } = $props();

  let snippet = $derived(stripMarkdown(post.content));
</script>

<article
  class="post-card relative px-4 py-4 border-b"
  style="border-color: var(--vercel-border);"
>
  <h2 class="text-base font-semibold">
    <a class="card-link" href={`/posts/${post.id}`} style="color: var(--vercel-text);">
      {post.title}
    </a>
  </h2>

  <p class="mt-1 line-clamp-2 text-sm" style="color: var(--vercel-text-secondary);">
    {snippet}
  </p>

  {#if post.poll}
    <PollCard postId={post.id} poll={post.poll} compact />
  {/if}

  <div class="mt-2 flex items-center justify-between gap-2">
    <div class="flex items-center gap-3 text-xs" style="color: var(--vercel-text-tertiary);">
      {#if post.tags && post.tags.length > 0}
        <span>{post.tags.join(", ")}</span>
      {/if}
      <span class="flex items-center gap-1">
        <HeartIcon size={14} strokeWidth={1.8} aria-hidden="true" />
        {post.like_count}
      </span>
      <span class="flex items-center gap-1">
        <MessageCircleIcon size={14} strokeWidth={1.8} aria-hidden="true" />
        {post.reply_count}
      </span>
    </div>

    <AuthorMeta username={post.author_username ?? $translator("common.anonymous")} userId={post.author_id} createdAt={post.created_at} />
  </div>
</article>

<style>
  .card-link::after {
    content: "";
    position: absolute;
    inset: 0;
  }

  .post-card {
    transition: background-color 150ms ease, border-color 150ms ease;
  }

  .post-card:hover {
    background: var(--vercel-hover);
  }

  .post-card:has(.card-link:focus-visible) {
    outline: 2px solid var(--vercel-text);
    outline-offset: -2px;
  }

  .card-link:focus-visible {
    outline: none;
  }
</style>
