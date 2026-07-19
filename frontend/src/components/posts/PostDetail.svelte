<script lang="ts">
  import { onMount } from "svelte";
  import { translator } from "../../lib/i18n";
  import { getPost, listComments, createComment, deleteContent, likePost, unlikePost, type Post, type Comment } from "../../lib/posts";
  import { toaster } from "../../stores/toaster";
  import { currentUser } from "../../stores/auth";
  import TimelineItem from "./TimelineItem.svelte";
  import ConfirmDialog from "../ConfirmDialog.svelte";

  export let postId: string;
  export let embedded = false;

  let post: Post | null = null;
  let comments: Comment[] = [];
  let loading = true;
  let replyText = "";
  let replyingTo: Comment | null = null;
  let submitting = false;
  let likingId: string | null = null;

  let showDeleteDialog = false;
  let pendingDelete: "post" | "comment" | null = null;
  let pendingDeleteIndex = 0;

  onMount(async () => {
    try {
      const [p, c] = await Promise.all([getPost(postId), listComments(postId)]);
      post = p;
      comments = c;
    } catch {
      toaster.error($translator("common.error"), $translator("post.loadFailed"));
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

  function focusCommentReply(comment: Comment) {
    if (!$currentUser) {
      window.location.href = `/login?returnTo=${encodeURIComponent(window.location.pathname)}`;
      return;
    }
    handleReplyClick(comment);
  }

  function focusReply() {
    if (!$currentUser) {
      window.location.href = `/login?returnTo=${encodeURIComponent(window.location.pathname)}`;
      return;
    }
    document.querySelector<HTMLTextAreaElement>("#reply-textarea")?.focus();
  }

  async function handleContentLike(id: string, liked: boolean) {
    if (!$currentUser) {
      window.location.href = `/login?returnTo=${encodeURIComponent(window.location.pathname)}`;
      return;
    }
    likingId = id;
    try {
      const state = liked ? await unlikePost(id) : await likePost(id);
      if (post?.id === id) {
        post = { ...post, ...state };
      } else {
        comments = comments.map((comment) =>
          comment.id === id ? { ...comment, ...state } : comment
        );
      }
    } catch (e: any) {
      toaster.error($translator("common.operationFailed"), $translator("common.tryAgain"));
    } finally {
      likingId = null;
    }
  }

  async function handleShare(contentId?: string) {
    if (!post) return;
    const data = {
      title: post.title,
      text: post.content.slice(0, 120),
      url: `${window.location.origin}${window.location.pathname}${contentId ? `#${contentId}` : ""}`,
    };
    try {
      if (navigator.share) {
        await navigator.share(data);
      } else {
        await navigator.clipboard.writeText(data.url);
        toaster.success(
          $translator("common.linkCopied"),
          $translator("common.linkCopiedDescription"),
        );
      }
    } catch (e: any) {
      if (e?.name !== "AbortError") {
        toaster.error($translator("common.shareFailed"), $translator("common.copyFailed"));
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
        toaster.error($translator("post.deleteTitle"), $translator("common.tryAgain"));
      }
    } else if (pendingDelete === "comment") {
      const comment = comments[pendingDeleteIndex - 1];
      if (!comment) return;
      try {
        await deleteContent(comment.id);
        comments = comments.filter((c) => c.id !== comment.id);
        if (post) post.reply_count--;
      } catch {
        toaster.error($translator("post.deleteReplyTitle"), $translator("common.tryAgain"));
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
      toaster.error($translator("common.error"), $translator("post.replyFailed"));
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
    replyingToContent: string | null;
    replyingToId: string | null;
    title: string | null;
    tags: string[] | null;
    likeCount: number;
    liked: boolean;
    replyCount: number;
  }> = [];

  $: if (post) {
    postTitle = post.title;
    postTags = post.tags;
    items = [
      {
        key: post.id,
        username: post.author_username ?? $translator("common.anonymous"),
        userId: post.author_id,
        createdAt: post.created_at,
        content: post.content,
        replyingToUsername: null,
        replyingToContent: null,
        replyingToId: null,
        title: post.title,
        tags: post.tags,
        likeCount: post.like_count,
        liked: post.liked_by_me,
        replyCount: post.reply_count,
      },
      ...comments.map((c) => ({
        key: c.id,
        username: c.author_username ?? $translator("common.anonymous"),
        userId: c.author_id,
        createdAt: c.created_at,
        content: c.content,
        replyingToUsername: c.replying_to_username,
        replyingToContent: c.replying_to_content,
        replyingToId: c.replying_id,
        title: null,
        tags: null,
        likeCount: c.like_count,
        liked: c.liked_by_me,
        replyCount: c.reply_count,
      })),
    ];
  }
</script>

{#if loading}
  <div class="empty-state">
    <div class="spinner mb-3"></div>
    {$translator("common.loading")}
  </div>
{:else if !post}
  <div class="empty-state">{$translator("post.notFound")}</div>
{:else}
  <!-- Back button -->
  {#if !embedded}<button class="back-btn" onclick={() => window.history.back()}>
    <svg class="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
    </svg>
    <span>{$translator("common.back")}</span>
  </button>{/if}

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
          replyingToContent={item.replyingToContent}
          replyingToId={item.replyingToId}
          contentId={item.key}
          onReply={$currentUser && i > 0 ? () => handleReplyClick(comments[i - 1]) : null}
          onDelete={i === 0
            ? ($currentUser?.id === post?.author_id ? handleDelete : null)
            : ($currentUser?.id === comments[i - 1]?.author_id ? () => handleDeleteComment(i) : null)}
          liked={item.liked}
          likeCount={item.likeCount}
          replyCount={item.replyCount}
          liking={likingId === item.key}
          onLike={() => handleContentLike(item.key, item.liked)}
          onDiscuss={i === 0 ? focusReply : () => focusCommentReply(comments[i - 1])}
          onShare={() => handleShare(i === 0 ? undefined : item.key)}
        />
      {/each}
    </div>
  </div>

  <!-- Reply form -->
  {#if $currentUser}
    <div class="mt-4 ml-7 pt-4 border-t" style="border-color: var(--vercel-border);">
      {#if replyingTo}
        <div class="mb-2 flex items-center gap-2 text-xs" style="color: var(--vercel-text-tertiary);">
          <span>{$translator("common.replyingTo", { name: replyingTo.author_username ?? $translator("common.anonymous") })}</span>
          <button class="transition-colors" style="color: var(--vercel-text-tertiary);" onmouseenter={(e) => e.currentTarget.style.color = 'var(--vercel-text)'} onmouseleave={(e) => e.currentTarget.style.color = 'var(--vercel-text-tertiary)'} onclick={cancelReply}>{$translator("common.cancel")}</button>
        </div>
      {/if}
      <div class="flex-1">
        <textarea
          id="reply-textarea"
          bind:value={replyText}
          class="input"
          style="min-height: 80px; resize: vertical;"
          placeholder={$translator("post.replyPlaceholder")}
        ></textarea>
        <div class="mt-2 flex justify-end">
          <button
            class="btn btn-primary btn-sm"
            onclick={handleSubmitReply}
            disabled={submitting || !replyText.trim()}
          >
            {submitting ? $translator("common.sending") : $translator("common.reply")}
          </button>
        </div>
      </div>
    </div>
  {:else}
    <div class="mt-4 ml-7 pt-4 border-t text-center" style="border-color: var(--vercel-border);">
      <a href="/login" class="text-sm transition-colors" style="color: var(--vercel-text-secondary);" onmouseenter={(e) => e.currentTarget.style.color = 'var(--vercel-text)'} onmouseleave={(e) => e.currentTarget.style.color = 'var(--vercel-text-secondary)'}>{$translator("post.loginToReply")}</a>
    </div>
  {/if}
{/if}

<ConfirmDialog
  bind:open={showDeleteDialog}
  title={$translator(pendingDelete === "post" ? "post.deleteTitle" : "post.deleteReplyTitle")}
  description={$translator(pendingDelete === "post" ? "post.deleteDescription" : "post.deleteReplyDescription")}
  confirmText={$translator("common.delete")}
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
