<script lang="ts">
  import { ArrowLeft } from "@lucide/svelte";
  import { onMount } from "svelte";
  import { translateError, translator } from "../../lib/i18n";
  import { requestLogin } from "../../lib/login";
  import {
    isModerationRestricted,
    moderationTargetContentId,
    onModerationUpdateForPath,
  } from "../../lib/moderation";
  import { createReport } from "../../lib/admin";
  import { getPost, listComments, createComment, deleteContent, getPostLikeState, likePost, unlikePost, updateContent, listContentHistory, type Post, type Comment, type Poll } from "../../lib/posts";
  import { toaster } from "../../stores/toaster";
  import { currentUser } from "../../stores/auth";
  import TimelineItem from "./TimelineItem.svelte";
  import WritingAssist from "./WritingAssist.svelte";
  import ConfirmDialog from "../ConfirmDialog.svelte";
  import ReportDialog from "../moderation/ReportDialog.svelte";
  import ContentEditModal from "../content/ContentEditModal.svelte";
  import RevisionHistoryModal, { type RevisionSnapshot } from "../content/RevisionHistoryModal.svelte";

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
  let reportOpen = false;
  let reportTarget = "";
  let reportReason = "";
  let reporting = false;
  let postRestricted = false;
  let editTarget: Post | Comment | null = null;
  let editKind: "post" | "comment" = "post";
  let historyTarget: Post | Comment | null = null;
  let translatedPostTitle: string | null = null;

  async function loadPostDetail(showError = true) {
    try {
      const [p, c] = await Promise.all([getPost(postId), listComments(postId)]);
      post = p;
      comments = c;
    } catch {
      if (showError) {
        toaster.error($translator("common.error"), $translator("post.loadFailed"));
      }
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    void loadPostDetail();
    return onModerationUpdateForPath(`/posts/${postId}`, (detail) => {
      const targetContentId = moderationTargetContentId(detail, postId);
      if (
        detail.type === "moderation_pending"
        && targetContentId === postId
        && post
      ) {
        const canSeePending = $currentUser?.id === post.author_id
          || $currentUser?.role === "moderator"
          || $currentUser?.role === "super_admin";
        if (canSeePending) {
          post = {
            ...post,
            moderation_status: "pending_review",
            moderation_reason: null,
            moderation_review_note: null,
          };
        } else {
          post = null;
          comments = [];
        }
      }
      void loadPostDetail(false);
    });
  });

  function postReturnTo(fragment?: string) {
    return `/posts/${postId}${fragment ? `#${fragment}` : ""}`;
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

  function focusCommentReply(comment: Comment) {
    if (!$currentUser) {
      requestLogin(postReturnTo(comment.id), () => handleReplyClick(comment));
      return;
    }
    handleReplyClick(comment);
  }

  function focusReply() {
    if (!$currentUser) {
      requestLogin(postReturnTo(), focusReply);
      return;
    }
    document.querySelector<HTMLTextAreaElement>("#reply-textarea")?.focus();
  }

  async function handleContentLike(id: string, liked: boolean) {
    if (!$currentUser) {
      requestLogin(postReturnTo(id), () => void handleContentLike(id, liked));
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
    } catch {
      try {
        const state = await getPostLikeState(id);
        if (post?.id === id) post = { ...post, ...state };
        else comments = comments.map((comment) => comment.id === id ? { ...comment, ...state } : comment);
        if (state.liked_by_me !== !liked) throw new Error("LIKE_NOT_APPLIED");
      } catch {
        toaster.error($translator("common.operationFailed"), $translator("common.tryAgain"));
      }
    } finally {
      likingId = null;
    }
  }

  async function handleShare(contentId?: string) {
    if (!post) return;
    const data = {
      title: post.title,
      text: post.content.slice(0, 120),
      url: `${window.location.origin}${postReturnTo(contentId)}`,
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

  function handlePollUpdate(poll: Poll) {
    if (post) post = { ...post, poll };
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

  function requestReport(contentId: string) {
    if (!$currentUser) {
      requestLogin(postReturnTo(contentId), () => openReport(contentId));
      return;
    }
    openReport(contentId);
  }

  function openReport(contentId: string) {
    reportTarget = contentId;
    reportReason = "";
    reportOpen = true;
  }

  async function submitReport(reason: string) {
    if (!reason.trim() || reporting) return;
    reporting = true;
    try {
      await createReport(reportTarget, reason.trim());
      reportOpen = false;
      toaster.success(
        $translator("moderation.reportSuccessTitle"),
        $translator("moderation.reportSuccessDescription"),
      );
    } catch (error) {
      toaster.error(
        $translator("moderation.reportFailed"),
        translateError(error, $translator, "common.tryAgain"),
      );
    } finally {
      reporting = false;
    }
  }

  function openEdit(target: Post | Comment, kind: "post" | "comment") {
    editTarget = target;
    editKind = kind;
  }

  async function saveEdit(payload: {
    revision_number: number;
    title?: string;
    content: string;
    tags?: string[] | null;
  }) {
    if (!editTarget) return;
    const updated = await updateContent(editTarget.id, payload);
    if (editKind === "post" && post?.id === updated.id) {
      post = { ...post, ...updated };
    } else {
      comments = comments.map((comment) =>
        comment.id === updated.id ? { ...comment, ...updated } : comment,
      );
    }
    editTarget = null;
  }

  function historyCurrent(): RevisionSnapshot | null {
    if (!historyTarget) return null;
    return {
      version: historyTarget.revision_number,
      title: "title" in historyTarget ? historyTarget.title : null,
      content: historyTarget.content,
      tags: "tags" in historyTarget ? historyTarget.tags : null,
      edited_at: historyTarget.updated_at ?? historyTarget.created_at,
    };
  }

  async function loadTargetHistory(): Promise<RevisionSnapshot[]> {
    if (!historyTarget) return [];
    return (await listContentHistory(historyTarget.id)).map((revision) => ({
      version: revision.version,
      title: revision.title,
      content: revision.content,
      tags: revision.tags,
      edited_at: revision.edited_at,
    }));
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
    moderationStatus: Post["moderation_status"];
    moderationReason: string | null;
    moderationReviewNote: string | null;
    revisionNumber: number;
    updatedAt: string | null;
  }> = [];

  $: if (post) {
    postRestricted = isModerationRestricted(post.moderation_status);
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
        moderationStatus: post.moderation_status,
        moderationReason: post.moderation_reason,
        moderationReviewNote: post.moderation_review_note,
        revisionNumber: post.revision_number,
        updatedAt: post.updated_at,
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
        moderationStatus: c.moderation_status,
        moderationReason: c.moderation_reason,
        moderationReviewNote: c.moderation_review_note,
        revisionNumber: c.revision_number,
        updatedAt: c.updated_at,
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
  {#if !embedded}<button class="btn btn-ghost btn-sm back-btn" onclick={() => window.history.back()}>
    <ArrowLeft size={16} strokeWidth={1.8} aria-hidden="true" />
    <span>{$translator("common.back")}</span>
  </button>{/if}

  <div class="mb-6 ml-7">
    <h1 class="text-xl font-bold" style="color: var(--vercel-text);">{translatedPostTitle ?? postTitle}</h1>
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
            ? ($currentUser?.id === post?.author_id && post.revision_number === 1 && !post.poll ? handleDelete : null)
            : ($currentUser?.id === comments[i - 1]?.author_id && comments[i - 1]?.revision_number === 1 ? () => handleDeleteComment(i) : null)}
          onEdit={i === 0
            ? ($currentUser?.id === post?.author_id && !post.poll ? () => openEdit(post, "post") : null)
            : ($currentUser?.id === comments[i - 1]?.author_id ? () => openEdit(comments[i - 1], "comment") : null)}
          onHistory={item.revisionNumber > 1
            ? () => (historyTarget = i === 0 ? post : comments[i - 1])
            : null}
          revisionNumber={item.revisionNumber}
          liked={item.liked}
          likeCount={item.likeCount}
          replyCount={item.replyCount}
          liking={likingId === item.key}
          onLike={() => handleContentLike(item.key, item.liked)}
          onDiscuss={i === 0 ? focusReply : () => focusCommentReply(comments[i - 1])}
          onShare={() => handleShare(i === 0 ? undefined : item.key)}
          onReport={$currentUser?.id === item.userId
            ? null
            : () => requestReport(item.key)}
          poll={i === 0 ? post.poll : null}
          onPollUpdate={i === 0 ? handlePollUpdate : null}
          aiText={item.content}
          aiTitle={item.title}
          aiContext={i === 0 ? "post" : "comment"}
          moderationStatus={item.moderationStatus}
          moderationReason={item.moderationReason}
          moderationReviewNote={item.moderationReviewNote}
          moderationTargetHref={`/posts/${postId}`}
          onTranslationChange={i === 0
            ? (translation) => (translatedPostTitle = translation?.title ?? null)
            : null}
        />
      {/each}
    </div>
  </div>

  <!-- Reply form -->
  {#if $currentUser && !postRestricted}
    <div class="mt-4 ml-7 pt-4 border-t" style="border-color: var(--vercel-border);">
      {#if replyingTo}
        <div class="mb-2 flex items-center gap-2 text-xs" style="color: var(--vercel-text-tertiary);">
          <span>{$translator("common.replyingTo", { name: replyingTo.author_username ?? $translator("common.anonymous") })}</span>
          <button class="reply-cancel" onclick={cancelReply}>{$translator("common.cancel")}</button>
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
        <div class="mt-2 flex items-center justify-between gap-2">
          <WritingAssist
            body={replyText}
            context="comment"
            onApply={(value) => (replyText = value.body)}
          />
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
  {:else if !$currentUser && !postRestricted}
    <div class="mt-4 ml-7 pt-4 border-t text-center" style="border-color: var(--vercel-border);">
    <a href="/login" class="login-reply-link text-sm">{$translator("post.loginToReply")}</a>
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

<ReportDialog
  bind:open={reportOpen}
  bind:reason={reportReason}
  {reporting}
  onsubmit={submitReport}
/>

<ContentEditModal
  show={editTarget !== null}
  kind={editKind}
  title={editTarget && "title" in editTarget ? editTarget.title : ""}
  content={editTarget?.content ?? ""}
  tags={editTarget && "tags" in editTarget ? editTarget.tags : null}
  revisionNumber={editTarget?.revision_number ?? 1}
  onclose={() => (editTarget = null)}
  onsave={saveEdit}
/>

<RevisionHistoryModal
  show={historyTarget !== null}
  current={historyCurrent()}
  load={loadTargetHistory}
  onclose={() => (historyTarget = null)}
/>

<style>
  .back-btn {
    margin-bottom: 1rem;
  }

  .reply-cancel,
  .login-reply-link {
    color: var(--vercel-text-tertiary);
    transition: color 150ms ease;
  }

  .reply-cancel:hover,
  .login-reply-link:hover {
    color: var(--vercel-text);
  }
</style>
