<script lang="ts">
  import { onMount } from "svelte";
  import { getPost, listComments, createComment, deleteContent, likePost, unlikePost, type Post, type Comment } from "../../lib/posts";
  import { toaster } from "../../stores/toaster";
  import { currentUser } from "../../stores/auth";
  import TimelineItem from "./TimelineItem.svelte";
  import ConfirmDialog from "../ConfirmDialog.svelte";

  export let postId: string;

  let post: Post | null = null;
  let comments: Comment[] = [];
  let loading = true;
  let replyText = "";
  let replyingTo: Comment | null = null;
  let submitting = false;
  let liking = false;

  let showDeleteDialog = false;
  let pendingDelete: "post" | "comment" | null = null;
  let pendingDeleteIndex = 0;

  onMount(async () => {
    try {
      const [p, c] = await Promise.all([getPost(postId), listComments(postId)]);
      post = p;
      comments = c;
    } catch {
      toaster.error("错误", "无法加载帖子");
    } finally {
      loading = false;
    }
  });

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

  function focusReply() {
    if (!$currentUser) {
      window.location.href = `/login?returnTo=${encodeURIComponent(window.location.pathname)}`;
      return;
    }
    document.querySelector<HTMLTextAreaElement>("#reply-textarea")?.focus();
  }

  async function handleLike() {
    if (!post) return;
    if (!$currentUser) {
      window.location.href = `/login?returnTo=${encodeURIComponent(window.location.pathname)}`;
      return;
    }
    liking = true;
    try {
      const state = post.liked_by_me
        ? await unlikePost(post.id)
        : await likePost(post.id);
      post = { ...post, ...state };
    } catch (e: any) {
      toaster.error("操作失败", e.message ?? "请稍后重试");
    } finally {
      liking = false;
    }
  }

  async function handleShare() {
    if (!post) return;
    const data = {
      title: post.title,
      text: post.content.slice(0, 120),
      url: window.location.href,
    };
    try {
      if (navigator.share) {
        await navigator.share(data);
      } else {
        await navigator.clipboard.writeText(data.url);
        toaster.success("链接已复制", "可以粘贴给其他人了");
      }
    } catch (e: any) {
      if (e?.name !== "AbortError") {
        toaster.error("转发失败", "无法复制链接，请稍后重试");
      }
    }
  }

  function handleDelete() {
    pendingDelete = "post";
    showDeleteDialog = true;
  }

  function handleDeleteComment(i: number) {
    pendingDelete = "comment";
    pendingDeleteIndex = i;
    showDeleteDialog = true;
  }

  async function confirmDelete() {
    if (pendingDelete === "post") {
      try {
        await deleteContent(postId);
        window.location.href = "/";
      } catch {
        toaster.error("删除失败");
      }
    } else if (pendingDelete === "comment") {
      const comment = comments[pendingDeleteIndex - 1];
      if (!comment) return;
      try {
        await deleteContent(comment.id);
        comments = comments.filter((c) => c.id !== comment.id);
        if (post) post.reply_count--;
      } catch {
        toaster.error("删除失败");
      }
    }
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
      toaster.error("错误", e.message ?? "回复失败");
    } finally {
      submitting = false;
    }
  }

  let postTitle = "";
  let postTags: string[] | null = null;
  let items: Array<{
    key: string;
    username: string;
    userId: string | null;
    createdAt: string;
    content: string;
    replyingToUsername: string | null;
    title: string | null;
    tags: string[] | null;
  }> = [];

  $: if (post) {
    postTitle = post.title;
    postTags = post.tags;
    items = [
      {
        key: post.id,
        username: post.author_username ?? "匿名",
        userId: post.author_id,
        createdAt: post.created_at,
        content: post.content,
        replyingToUsername: null,
        title: post.title,
        tags: post.tags,
      },
      ...comments.map((c) => ({
        key: c.id,
        username: c.author_username ?? "匿名",
        userId: c.author_id,
        createdAt: c.created_at,
        content: c.content,
        replyingToUsername: c.replying_to_username,
        title: null,
        tags: null,
      })),
    ];
  }
</script>

{#if loading}
  <div class="empty-state">
    <div class="spinner mb-3"></div>
    加载中...
  </div>
{:else if !post}
  <div class="empty-state">帖子不存在</div>
{:else}
  <!-- Back button -->
  <button class="back-btn" onclick={() => window.history.back()}>
    <svg class="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
    </svg>
    <span>返回</span>
  </button>

  <div class="mb-6 ml-7">
    <h1 class="text-xl font-bold" style="color: var(--vercel-text);">{postTitle}</h1>
    {#if postTags && postTags.length > 0}
      <div class="mt-2 flex flex-wrap gap-2">
        {#each postTags as tag}
          <span class="badge badge-neutral">{tag}</span>
        {/each}
      </div>
    {/if}
  </div>

  <div class="relative">
    <div class="timeline-line"></div>

    <div>
      {#each items as item, i (item.key)}
        <TimelineItem
          username={item.username}
          userId={item.userId}
          createdAt={item.createdAt}
          content={item.content}
          title={item.title}
          tags={item.tags}
          replyingToUsername={item.replyingToUsername}
          onReply={$currentUser && i > 0 ? () => handleReplyClick(comments[i - 1]) : null}
          onDelete={i === 0
            ? ($currentUser?.id === post?.author_id ? handleDelete : null)
            : ($currentUser?.id === comments[i - 1]?.author_id ? () => handleDeleteComment(i) : null)}
          liked={i === 0 ? post.liked_by_me : false}
          likeCount={i === 0 ? post.like_count : null}
          replyCount={i === 0 ? post.reply_count : null}
          {liking}
          onLike={i === 0 ? handleLike : null}
          onDiscuss={i === 0 ? focusReply : null}
          onShare={i === 0 ? handleShare : null}
        />
      {/each}
    </div>
  </div>

  <!-- Reply form -->
  {#if $currentUser}
    <div class="mt-4 ml-7 pt-4 border-t" style="border-color: var(--vercel-border);">
      {#if replyingTo}
        <div class="mb-2 flex items-center gap-2 text-xs" style="color: var(--vercel-text-tertiary);">
          <span>回复 <span class="font-medium" style="color: var(--vercel-text);">@{replyingTo.author_username}</span></span>
          <button class="transition-colors" style="color: var(--vercel-text-tertiary);" onmouseenter={(e) => e.currentTarget.style.color = 'var(--vercel-text)'} onmouseleave={(e) => e.currentTarget.style.color = 'var(--vercel-text-tertiary)'} onclick={cancelReply}>取消</button>
        </div>
      {/if}
      <div class="flex-1">
        <textarea
          id="reply-textarea"
          bind:value={replyText}
          class="input"
          style="min-height: 80px; resize: vertical;"
          placeholder="写下你的回复..."
        ></textarea>
        <div class="mt-2 flex justify-end">
          <button
            class="btn btn-primary btn-sm"
            onclick={handleSubmitReply}
            disabled={submitting || !replyText.trim()}
          >
            {submitting ? "发送中..." : "回复"}
          </button>
        </div>
      </div>
    </div>
  {:else}
    <div class="mt-4 ml-7 pt-4 border-t text-center" style="border-color: var(--vercel-border);">
      <a href="/login" class="text-sm transition-colors" style="color: var(--vercel-text-secondary);" onmouseenter={(e) => e.currentTarget.style.color = 'var(--vercel-text)'} onmouseleave={(e) => e.currentTarget.style.color = 'var(--vercel-text-secondary)'}>登录后参与回复</a>
    </div>
  {/if}
{/if}

<ConfirmDialog
  bind:open={showDeleteDialog}
  title={pendingDelete === "post" ? "删除帖子" : "删除回复"}
  description={pendingDelete === "post" ? "确认要删除这个帖子？此操作不可撤销。" : "确认要删除这条回复？此操作不可撤销。"}
  confirmText="删除"
  onConfirm={confirmDelete}
/>

<style>
  .back-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    margin-bottom: 1rem;
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--vercel-text-secondary);
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .back-btn:hover {
    color: var(--vercel-text);
    background: rgba(255,255,255,0.08);
    border-color: rgba(255,255,255,0.12);
  }
</style>
