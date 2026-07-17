<script lang="ts">
  import { onMount } from "svelte";
  import { getPost, listComments, createComment, type Post, type Comment } from "../../lib/posts";
  import { toaster } from "../../stores/toaster";
  import { currentUser } from "../../stores/auth";
  import CommentItem from "./CommentItem.svelte";

  export let postId: string;

  let post: Post | null = null;
  let comments: Comment[] = [];
  let loading = true;
  let replyText = "";
  let replyingTo: Comment | null = null;
  let submitting = false;

  onMount(async () => {
    try {
      const [p, c] = await Promise.all([getPost(postId), listComments(postId)]);
      post = p;
      comments = c;
    } catch {
      toaster.error({ title: "错误", description: "无法加载帖子" });
    } finally {
      loading = false;
    }
  });

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

  function cancelReply() {
    replyingTo = null;
    replyText = "";
  }

  function handleReplyClick(c: Comment) {
    replyingTo = c;
    replyText = "";
    setTimeout(() => {
      const ta = document.querySelector<HTMLTextAreaElement>("#reply-textarea");
      ta?.focus();
    }, 0);
  }

  async function handleSubmitReply() {
    if (!replyText.trim()) return;
    submitting = true;
    try {
      const newComment = await createComment(postId, {
        content: replyText.trim(),
        ...(replyingTo ? { replying_id: replyingTo.id } : {}),
      });
      comments = [...comments, newComment];
      replyText = "";
      replyingTo = null;
      if (post) post.reply_count++;
    } catch (e: any) {
      toaster.error({ title: "错误", description: e.message ?? "回复失败" });
    } finally {
      submitting = false;
    }
  }
</script>

{#if loading}
  <div class="flex justify-center py-12 text-sm text-surface-400">加载中…</div>
{:else if !post}
  <div class="flex justify-center py-12 text-sm text-surface-500">帖子不存在</div>
{:else}
  <!-- Post header -->
  <div class="border-b border-surface-200/50 pb-6">
    <div class="flex items-center gap-3">
      <div
        class="flex size-10 items-center justify-center rounded-full bg-surface-200 text-base font-bold text-surface-600"
      >
        {(post.author_username ?? "?")[0].toUpperCase()}
      </div>
      <div>
        <div class="font-medium text-surface-900">{post.author_username ?? "匿名"}</div>
        <div class="text-xs text-surface-400">{timeAgo(post.created_at)}</div>
      </div>
    </div>
    <h1 class="mt-3 text-xl font-bold text-surface-900">{post.title}</h1>
    <p class="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-surface-700">{post.content}</p>
    {#if post.tags && post.tags.length > 0}
      <div class="mt-3 flex flex-wrap gap-2">
        {#each post.tags as tag}
          <span class="rounded-full bg-surface-100 px-2.5 py-0.5 text-xs text-surface-600">{tag}</span>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Comment timeline -->
  <div class="pt-4">
    {#if comments.length === 0}
      <p class="py-8 text-center text-sm text-surface-400">暂无回复，来写第一条吧</p>
    {:else}
      {#each comments as comment, i}
        <div class="group relative">
          <CommentItem {comment} isLast={i === comments.length - 1 && !$currentUser} />
          {#if $currentUser}
            <button
              class="absolute bottom-6 left-10 text-xs text-surface-400 opacity-0 transition-opacity hover:text-primary-600 group-hover:opacity-100"
              on:click={() => handleReplyClick(comment)}
            >
              回复
            </button>
          {/if}
        </div>
      {/each}
    {/if}
  </div>

  <!-- Reply form -->
  {#if $currentUser}
    <div class="border-t border-surface-200/50 pt-4">
      {#if replyingTo}
        <div class="mb-2 flex items-center gap-2 text-xs text-surface-500">
          <span>回复 <span class="font-medium text-primary-600">@{replyingTo.author_username}</span></span>
          <button class="text-surface-400 hover:text-surface-600" on:click={cancelReply}>取消</button>
        </div>
      {/if}
      <div class="flex gap-3">
        <div
          class="mt-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-surface-200 text-[10px] font-bold text-surface-600"
        >
          {($currentUser.username ?? "?")[0].toUpperCase()}
        </div>
        <div class="flex-1">
          <textarea
            id="reply-textarea"
            bind:value={replyText}
            class="input min-h-[80px] resize-y text-sm"
            placeholder="写下你的回复…"
          ></textarea>
          <div class="mt-2 flex justify-end">
            <button
              class="btn preset-filled-primary-500 text-sm"
              on:click={handleSubmitReply}
              disabled={submitting || !replyText.trim()}
            >
              {submitting ? "发送中…" : "回复"}
            </button>
          </div>
        </div>
      </div>
    </div>
  {:else}
    <div class="border-t border-surface-200/50 pt-4 text-center">
      <a href="/login" class="text-sm text-primary-600 hover:text-primary-700">登录后参与回复</a>
    </div>
  {/if}
{/if}
