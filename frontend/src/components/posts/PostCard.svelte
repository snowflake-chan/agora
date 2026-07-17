<script lang="ts">
  import type { Post } from "../../lib/posts";

  export let post: Post;

  function timeAgo(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "刚刚";
    if (mins < 60) return `${mins} 分钟前`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours} 小时前`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days} 天前`;
    return new Date(dateStr).toLocaleDateString("zh-CN");
  }
</script>

<a
  href={`/posts/${post.id}`}
  class="group block border-b border-surface-200/50 px-4 py-4 transition-colors hover:bg-surface-50"
>
  <div class="flex items-start gap-3">
    <div
      class="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-surface-200 text-sm font-bold text-surface-600"
    >
      {(post.author_username ?? "?")[0].toUpperCase()}
    </div>

    <div class="min-w-0 flex-1">
      <div class="mb-1 flex items-center gap-2 text-sm text-surface-500">
        <span class="font-medium text-surface-700">{post.author_username ?? "匿名"}</span>
        <span>·</span>
        <span>{timeAgo(post.created_at)}</span>
      </div>

      <h2 class="text-base font-semibold text-surface-900 group-hover:text-primary-700">
        {post.title}
      </h2>

      <p class="mt-0.5 line-clamp-2 text-sm text-surface-500">
        {post.content}
      </p>

      <div class="mt-2 flex items-center gap-4 text-xs text-surface-400">
        {#if post.tags && post.tags.length > 0}
          <span>{post.tags.join(", ")}</span>
        {/if}
        <span class="flex items-center gap-1">
          <svg class="size-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
          {post.reply_count}
        </span>
      </div>
    </div>
  </div>
</a>
