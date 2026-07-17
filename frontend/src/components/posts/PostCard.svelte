<script lang="ts">
  import type { Post } from "../../lib/posts";
  import AuthorMeta from "../AuthorMeta.svelte";

  export let post: Post;

  function stripMarkdown(md: string): string {
    return md
      .replace(/^#{1,6}\s+(.+)$/gm, '$1')    // strip heading markers
      .replace(/\*\*(.+?)\*\*/g, '$1')        // bold
      .replace(/\*(.+?)\*/g, '$1')            // italic
      .replace(/`{1,3}.+?`{1,3}/g, (m) => m.replace(/`/g, ''))  // inline code
      .replace(/\[(.+?)\]\(.+?\)/g, '$1')      // links
      .replace(/!\[.*?\]\(.+?\)/g, '[图片]')   // images
      .replace(/^[-*+]\s+/gm, '')              // unordered list markers
      .replace(/^\d+\.\s+/gm, '')              // ordered list markers
      .replace(/^>\s+/gm, '')                  // blockquote
      .replace(/---+/g, '')                    // hr
      .replace(/\n{3,}/g, '\n\n')              // collapse newlines
      .trim();
  }

  $: snippet = stripMarkdown(post.content);
</script>

<a
  href={`/posts/${post.id}`}
  class="group block border-b border-surface-200/50 px-4 py-4 transition-colors hover:bg-surface-50"
>
  <h2 class="text-base font-semibold text-surface-900 group-hover:text-primary-700">
    {post.title}
  </h2>

  <p class="mt-1 line-clamp-2 text-sm text-surface-500">
    {snippet}
  </p>

  <div class="mt-2 flex items-center justify-between gap-2">
    <div class="flex items-center gap-3 text-xs text-surface-400">
      {#if post.tags && post.tags.length > 0}
        <span>{post.tags.join(", ")}</span>
      {/if}
      <span class="flex items-center gap-1">
        <svg class="size-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
        {post.reply_count}
      </span>
    </div>

    <AuthorMeta username={post.author_username ?? "匿名"} createdAt={post.created_at} />
  </div>
</a>
