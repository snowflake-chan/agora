<script lang="ts">
  import { onMount, tick } from "svelte";
  import GlassModal from "../GlassModal.svelte";
  import ConfirmDialog from "../ConfirmDialog.svelte";
  import TimelineItem from "./TimelineItem.svelte";
  import { getPost, listComments, createComment, deleteContent, type Post, type Comment } from "../../lib/posts";
  import { createReport } from "../../lib/admin";
  import { toaster } from "../../stores/toaster";
  import { currentUser } from "../../stores/auth";

  let { postId = "" }: { postId: string } = $props();

  // all reactive state uses $state for Svelte 5 runes mode
  let post = $state<Post | null>(null);
  let comments = $state<Comment[]>([]);
  let loading = $state(true);
  let replyText = $state("");
  let replyingTo = $state<Comment | null>(null);
  let submitting = $state(false);
  let showDeleteDialog = $state(false);
  let pendingDelete = $state<"post" | "comment" | null>(null);
  let pendingDeleteId = $state<string | null>(null);
  let reportModal = $state(false);
  let reportTarget = $state("");
  let reportReason = $state("");
  let reporting = $state(false);

  // derived from post + comments
  let items = $derived.by(() => {
    if (!post) return [] as Array<{
      key: string; username: string; userId: string | null; createdAt: string;
      content: string; replyingToUsername: string | null; title: string | null; tags: string[] | null;
    }>;
    return [
      {
        key: post.id, username: post.author_username ?? "匿名", userId: post.author_id,
        createdAt: post.created_at, content: post.content, replyingToUsername: null,
        title: post.title, tags: post.tags,
      },
      ...comments.map((c) => ({
        key: c.id, username: c.author_username ?? "匿名", userId: c.author_id,
        createdAt: c.created_at, content: c.content,
        replyingToUsername: c.replying_to_username, title: null, tags: null as string[] | null,
      })),
    ];
  });

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

  function cancelReply() { replyingTo = null; replyText = ""; }

  function handleReplyClick(c: Comment) {
    replyingTo = c; replyText = "";
    tick().then(() => document.querySelector<HTMLTextAreaElement>("#reply-textarea")?.focus());
  }

  function handleDelete() { pendingDelete = "post"; showDeleteDialog = true; }

  function handleDeleteComment(commentId: string) { pendingDelete = "comment"; pendingDeleteId = commentId; showDeleteDialog = true; }

  async function confirmDelete() {
    if (pendingDelete === "post") {
      try { await deleteContent(postId); window.location.href = "/"; }
      catch { toaster.error("删除失败"); }
    } else if (pendingDelete === "comment" && pendingDeleteId) {
      try {
        await deleteContent(pendingDeleteId);
        comments = comments.filter((c) => c.id !== pendingDeleteId);
        if (post) post.reply_count--;
      } catch { toaster.error("删除失败"); }
    }
    showDeleteDialog = false;
  }

  async function handleSubmitReply() {
    if (!replyText.trim()) return;
    submitting = true;
    try {
      const newComment = await createComment(postId, { content: replyText.trim(), ...(replyingTo ? { replying_id: replyingTo.id } : {}) });
      comments = [...comments, newComment]; replyText = ""; replyingTo = null;
      if (post) post.reply_count++;
    } catch (e: any) { toaster.error("错误", e.message ?? "回复失败"); }
    finally { submitting = false; }
  }

  function openReportModal(contentId: string) { reportTarget = contentId; reportReason = ""; reportModal = true; }

  async function submitReport() {
    if (!reportReason.trim() || reporting) return;
    reporting = true;
    try { await createReport(reportTarget, reportReason.trim()); toaster.success("已举报", "管理员会尽快处理"); reportModal = false; }
    catch (e: any) { toaster.error("举报失败", e.message); }
    finally { reporting = false; }
  }
</script>

{#if loading}
  <div class="empty-state"><div class="spinner mb-3"></div>加载中...</div>
{:else if !post}
  <div class="empty-state">帖子不存在</div>
{:else}
  <button class="back-btn" onclick={() => window.history.back()}>
    <svg class="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
    <span>返回</span>
  </button>

  <div class="mb-6 ml-7">
    <h1 class="text-xl font-bold" style="color: var(--vercel-text);">{post.title}</h1>
    {#if post.tags?.length}
      <div class="mt-2 flex flex-wrap gap-2">
        {#each post.tags as tag}<span class="badge badge-neutral">{tag}</span>{/each}
      </div>
    {/if}
  </div>

  <div class="relative">
    <div class="timeline-line"></div>
    <div>
      {#each items as item, i (item.key)}
        <TimelineItem
          username={item.username} userId={item.userId} contentId={item.key}
          createdAt={item.createdAt} content={item.content}
          title={item.title} tags={item.tags}
          replyingToUsername={item.replyingToUsername}
          onReply={$currentUser && i > 0 ? () => handleReplyClick(comments[i - 1]) : null}
          onDelete={i === 0 ? ($currentUser?.id === post?.author_id ? handleDelete : null) : ($currentUser?.id === comments[i - 1]?.author_id ? () => handleDeleteComment(comments[i - 1].id) : null)}
          onReport={$currentUser ? () => openReportModal(item.key) : null}
        />
      {/each}
    </div>
  </div>

  {#if $currentUser}
    <div class="mt-4 ml-7 pt-4 border-t" style="border-color: var(--vercel-border);">
      {#if replyingTo}
        <div class="mb-2 flex items-center gap-2 text-xs" style="color: var(--vercel-text-tertiary);">
          <span>回复 <span class="font-medium" style="color: var(--vercel-text);">@{replyingTo.author_username}</span></span>
          <button class="cancel-reply-btn" onclick={cancelReply}>取消</button>
        </div>
      {/if}
      <textarea id="reply-textarea" bind:value={replyText} class="input" style="min-height: 80px; resize: vertical;" placeholder="写下你的回复..." aria-label="回复内容"></textarea>
      <div class="mt-2 flex justify-end">
        <button class="btn btn-primary btn-sm" onclick={handleSubmitReply} disabled={submitting || !replyText.trim()}>{submitting ? "发送中..." : "回复"}</button>
      </div>
    </div>
  {:else}
    <div class="mt-4 ml-7 pt-4 border-t text-center" style="border-color: var(--vercel-border);">
      <a href="/login" class="text-sm" style="color: var(--vercel-text-secondary);">登录后参与回复</a>
    </div>
  {/if}
{/if}

<ConfirmDialog bind:open={showDeleteDialog}
  title={pendingDelete === "post" ? "删除帖子" : "删除回复"}
  description={pendingDelete === "post" ? "确认要删除这个帖子？此操作不可撤销。" : "确认要删除这条回复？此操作不可撤销。"}
  confirmText="删除" onConfirm={confirmDelete}
/>

<GlassModal show={reportModal} title="举报内容" onclose={() => reportModal = false}>
  <textarea class="input" rows="3" bind:value={reportReason} placeholder="请详细描述举报理由..." style="width: 100%; margin-bottom: 1rem;"></textarea>
  <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
    <button class="btn btn-ghost btn-sm" onclick={() => reportModal = false}>取消</button>
    <button class="btn btn-primary btn-sm" onclick={submitReport} disabled={reporting || !reportReason.trim()}>{reporting ? "提交中..." : "提交举报"}</button>
  </div>
</GlassModal>

<style>
  .back-btn { display: inline-flex; align-items: center; gap: 0.375rem; padding: 0.375rem 0.75rem; margin-bottom: 1rem; font-size: 0.8125rem; font-weight: 500; color: var(--vercel-text-secondary); background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; cursor: pointer; transition: all 0.2s; }
  .back-btn:hover { color: var(--vercel-text); background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.12); }
  .cancel-reply-btn { color: var(--vercel-text-tertiary); transition: color .18s ease; }
  .cancel-reply-btn:hover { color: var(--vercel-text); }
</style>
