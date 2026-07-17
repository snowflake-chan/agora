<script lang="ts">
  import type { Comment } from "../../lib/posts";

  export let comment: Comment;
  export let isLast: boolean = false;

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

<div class="relative pl-10">
  <!-- Gray timeline line -->
  <div
    class="absolute left-[15px] top-0 w-px bg-surface-200"
    class:inset-y-0={!isLast}
    class:h-0={isLast}
  ></div>

  <!-- Avatar on the line -->
  <div
    class="absolute left-[7px] flex size-[18px] items-center justify-center rounded-full bg-surface-50 ring-2 ring-surface-50"
  >
    <span class="text-[9px] font-bold text-primary-700">
      {(comment.author_username ?? "?")[0].toUpperCase()}
    </span>
  </div>

  <!-- Comment body -->
  <div class="pb-6">
    <div class="mb-1 flex items-center gap-2 text-xs text-surface-500">
      <span class="font-medium text-surface-700">{comment.author_username ?? "匿名"}</span>
      <span>·</span>
      <span>{timeAgo(comment.created_at)}</span>
    </div>

    <div class="rounded-lg border border-surface-200 bg-surface-50/30 px-4 py-3 text-sm text-surface-800">
      {#if comment.replying_to_username}
        <span class="mr-1 font-medium text-primary-600">@{comment.replying_to_username}</span>
      {/if}
      {comment.content}
    </div>
  </div>
</div>
