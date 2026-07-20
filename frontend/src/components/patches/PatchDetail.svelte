<script lang="ts">
  import { onMount } from "svelte";
  import { renderMarkdown } from "../../lib/markdown";
  import { getPatch, deletePatch, submitPatch, votePatch, listVotes, type Patch, type Vote } from "../../lib/patches";
  import { toaster } from "../../stores/toaster";
  import { currentUser } from "../../stores/auth";
  import { GITHUB_REPO } from "../../lib/config";
  import AuthorMeta from "../AuthorMeta.svelte";
  import ConfirmDialog from "../ConfirmDialog.svelte";

  let { patchId = "" }: { patchId: string } = $props();

  let patch = $state<Patch | null>(null);
  let votes = $state<Vote[]>([]);
  let loading = $state(true);
  let currentUserVote: Vote | null = $state(null);

  let showVoteDialog = $state(false);
  let pendingChoice = $state("");
  let showDeleteDialog = $state(false);

  const STATUS_MAP: Record<string, { label: string; type: string }> = {
    draft: { label: "草稿", type: "neutral" },
    voting: { label: "投票中", type: "warning" },
    passed: { label: "通过待合并", type: "info" },
    merged: { label: "已合并", type: "success" },
    rejected: { label: "未通过", type: "danger" },
    failed: { label: "合并失败", type: "danger" },
  };

  let statusInfo = $derived(patch ? STATUS_MAP[patch.status] ?? { label: patch.status, type: "neutral" } : { label: "", type: "neutral" });
  let deadlineStr = $derived(patch?.voting_ends_at ? formatDeadline(patch.voting_ends_at) : null);

  function formatDeadline(iso: string): string {
    const end = new Date(iso);
    const now = new Date();
    const diff = end.getTime() - now.getTime();
    if (diff <= 0) return "已截止";
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(hours / 24);
    if (days > 0) return `剩余 ${days} 天 ${hours % 24} 小时`;
    return `剩余 ${hours} 小时`;
  }

  onMount(async () => {
    try {
      const [p, v] = await Promise.all([getPatch(patchId), listVotes(patchId)]);
      patch = p;
      votes = v;
      const myVote = v.find((v) => v.voter_id === $currentUser?.id);
      if (myVote) currentUserVote = myVote;
    } catch {
      toaster.error("错误", "无法加载变更");
    } finally {
      loading = false;
    }
  });

  async function handleDelete() {
    try {
      await deletePatch(patchId);
      window.location.href = "/";
    } catch {
      toaster.error("删除失败");
    }
  }

  async function handleSubmit() {
    try {
      patch = await submitPatch(patchId);
      toaster.success("已提交投票", "窗口期 3 天");
    } catch (e: any) {
      toaster.error("提交失败", e.message ?? "");
    }
  }

  function promptVote(choice: string) {
    pendingChoice = choice;
    showVoteDialog = true;
  }

  async function confirmVote() {
    try {
      const v = await votePatch(patchId, pendingChoice);
      currentUserVote = v;
      votes = [...votes.filter((v) => v.voter_id !== $currentUser?.id), v];
      patch = await getPatch(patchId);
      toaster.success("投票成功");
    } catch (e: any) {
      toaster.error("投票失败", e.message ?? "");
    }
  }

  function goBack() {
    window.history.back();
  }

  let totalVotes = $derived(patch ? patch.for_count + patch.against_count + patch.abstain_count : 0);
  let forPct = $derived(patch && totalVotes > 0 ? Math.round((patch.for_count / totalVotes) * 100) : 0);
  let againstPct = $derived(patch && totalVotes > 0 ? Math.round((patch.against_count / totalVotes) * 100) : 0);
  let abstainPct = $derived(patch && totalVotes > 0 ? Math.round((patch.abstain_count / totalVotes) * 100) : 0);
</script>

{#if loading}
  <div class="empty-state">
    <div class="spinner mb-3"></div>
    加载中...
  </div>
{:else if !patch}
  <div class="empty-state">变更不存在</div>
{:else}
  <!-- Back button -->
  <button class="back-btn" onclick={goBack}>
    <svg class="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
    </svg>
    <span>返回</span>
  </button>

  <!-- Header -->
  <div class="mb-6">
    <div class="flex items-center gap-2">
      <span class="badge badge-{statusInfo.type}">
        {statusInfo.label}
      </span>
      {#if patch.status === "voting" && deadlineStr}
        <span class="text-xs" style="color: var(--vercel-text-tertiary);">{deadlineStr}</span>
      {/if}
      <a
        href="https://github.com/{GITHUB_REPO}/pull/{patch.pr_number}"
        target="_blank"
        class="text-sm transition-colors"
        style="color: var(--vercel-text-secondary);"
        onmouseenter={(e) => e.currentTarget.style.color = 'var(--vercel-text)'}
        onmouseleave={(e) => e.currentTarget.style.color = 'var(--vercel-text-secondary)'}
      >
        PR #{patch.pr_number} ↗
      </a>
    </div>
    <h1 class="mt-2 text-xl font-bold" style="color: var(--vercel-text);">{patch.title}</h1>
    <div class="mt-1">
      <AuthorMeta username={patch.author_username ?? "匿名"} userId={patch.author_id} createdAt={patch.created_at} />
    </div>
  </div>

  <!-- Content (rendered markdown) -->
  <div class="card p-4 mb-8">
    <div class="markdown-body">{@html renderMarkdown(patch.content)}</div>
  </div>

  <!-- Vote panel -->
  {#if patch.status === "voting"}
    <div class="card p-4 mb-8">
      <h3 class="mb-3 text-sm font-semibold" style="color: var(--vercel-text);">投票</h3>

      {#if deadlineStr && deadlineStr !== "已截止"}
        <p class="mb-3 text-xs" style="color: var(--vercel-text-tertiary);">{deadlineStr}，截止后自动计票</p>
      {/if}

      <!-- Vote bar -->
      {#if totalVotes > 0}
        <div class="flex h-2 mb-4 rounded-full overflow-hidden" style="background: rgba(255,255,255,0.06);">
          <div style="width: {forPct}%; background: var(--vercel-success); transition: width 0.3s;"></div>
          <div style="width: {againstPct}%; background: var(--vercel-danger); transition: width 0.3s;"></div>
          <div style="width: {abstainPct}%; background: rgba(255,255,255,0.1); transition: width 0.3s;"></div>
        </div>
      {/if}

      <div class="mb-4 flex justify-between text-xs" style="color: var(--vercel-text-tertiary);">
        <span>赞成 {patch.for_count}</span>
        <span>反对 {patch.against_count}</span>
        <span>弃权 {patch.abstain_count}</span>
      </div>

      {#if $currentUser}
        <div class="vote-buttons">
          <button
            class="vote-btn"
            class:vote-active-for={currentUserVote?.choice === "for"}
            class:vote-other={currentUserVote && currentUserVote.choice !== "for"}
            onclick={() => promptVote("for")}
          >
            <svg class="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
            </svg>
            <span>赞成</span>
            {#if currentUserVote?.choice === "for"}
              <svg class="size-3.5 checkmark" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
              </svg>
            {/if}
          </button>
          <button
            class="vote-btn"
            class:vote-active-against={currentUserVote?.choice === "against"}
            class:vote-other={currentUserVote && currentUserVote.choice !== "against"}
            onclick={() => promptVote("against")}
          >
            <svg class="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.096c.5 0 .905-.405.905-.904 0-.715.211-1.413.608-2.008L17 13V4h-3m-7 10h2" />
            </svg>
            <span>反对</span>
            {#if currentUserVote?.choice === "against"}
              <svg class="size-3.5 checkmark" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
              </svg>
            {/if}
          </button>
          <button
            class="vote-btn vote-btn-abstain"
            class:vote-active-abstain={currentUserVote?.choice === "abstain"}
            class:vote-other={currentUserVote && currentUserVote.choice !== "abstain"}
            onclick={() => promptVote("abstain")}
          >
            <svg class="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="9" stroke-width="2" />
              <path stroke-linecap="round" stroke-width="2" d="M8 12h8" />
            </svg>
            <span>弃权</span>
            {#if currentUserVote?.choice === "abstain"}
              <svg class="size-3.5 checkmark" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
              </svg>
            {/if}
          </button>
        </div>
      {:else}
        <a href="/login" class="text-sm transition-colors" style="color: var(--vercel-text-secondary);">登录后参与投票</a>
      {/if}
    </div>
  {/if}

  <!-- Results panel -->
  {#if patch.status === "merged" || patch.status === "rejected" || patch.status === "failed" || patch.status === "passed"}
    <div class="card p-4 mb-8">
      <h3 class="mb-3 text-sm font-semibold" style="color: var(--vercel-text);">
        {patch.status === "merged" ? "已合并" : patch.status === "rejected" ? "未通过" : patch.status === "failed" ? "合并失败" : "已通过"}
      </h3>
      <div class="flex gap-4 text-sm" style="color: var(--vercel-text-secondary);">
        <span>赞成 {patch.for_count}</span>
        <span>反对 {patch.against_count}</span>
        <span>弃权 {patch.abstain_count}</span>
        <span>总票数 {totalVotes}</span>
      </div>
    </div>
  {/if}

  <!-- Author actions -->
  {#if $currentUser?.id === patch.author_id}
    <div class="mb-8 flex gap-2">
      {#if patch.status === "draft"}
        <button class="btn btn-primary btn-sm" onclick={handleSubmit}>
          提交投票
        </button>
        <button class="btn btn-danger btn-sm" onclick={() => (showDeleteDialog = true)}>
          删除
        </button>
      {/if}
    </div>
  {/if}

  <!-- Vote list -->
  {#if votes.length > 0}
    <div class="card mb-8">
      <h3 class="px-4 py-2 text-sm font-semibold border-b" style="color: var(--vercel-text); border-color: var(--vercel-border);">
        投票记录
      </h3>
      {#each votes as v (v.id)}
        <div class="flex items-center justify-between px-4 py-2 text-sm border-b last:border-0" style="border-color: var(--vercel-border);">
          <span style="color: var(--vercel-text-secondary);">{v.voter_username ?? "匿名"}</span>
          <span class="text-xs" style="color: {v.choice === 'for' ? 'var(--vercel-success)' : v.choice === 'against' ? 'var(--vercel-danger)' : 'var(--vercel-text-tertiary)'};">
            {v.choice === "for" ? "赞成" : v.choice === "against" ? "反对" : "弃权"}
          </span>
        </div>
      {/each}
    </div>
  {/if}
{/if}

<ConfirmDialog
  bind:open={showDeleteDialog}
  title="删除变更"
  description="确认删除这个变更？此操作不可撤销。"
  confirmText="删除"
  onConfirm={handleDelete}
/>

<ConfirmDialog
  bind:open={showVoteDialog}
  title={pendingChoice === "for" ? "投赞成票" : pendingChoice === "against" ? "投反对票" : "投弃权票"}
  description={pendingChoice === "for" ? "确认投赞成票？" : pendingChoice === "against" ? "确认投反对票？" : "确认弃权？"}
  confirmText="确认"
  onConfirm={confirmVote}
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
    transition: all 0.2s var(--apple-ease);
  }

  .back-btn:hover {
    color: var(--vercel-text);
    background: rgba(255,255,255,0.08);
    border-color: rgba(255,255,255,0.12);
  }

  /* ---- vote buttons ---- */
  .vote-buttons {
    display: flex;
    gap: 0.5rem;
  }

  .vote-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.5rem 1rem;
    font-size: 0.8125rem;
    font-weight: 500;
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.08);
    background: rgba(255,255,255,0.04);
    color: var(--vercel-text-tertiary);
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.25, 0.1, 0.25, 1);
    user-select: none;
  }

  .vote-btn:hover {
    background: rgba(255,255,255,0.08);
    border-color: rgba(255,255,255,0.14);
    color: var(--vercel-text-secondary);
  }

  /* active – for */
  .vote-active-for {
    background: rgba(34, 197, 94, 0.18) !important;
    border-color: rgba(34, 197, 94, 0.55) !important;
    color: #fff !important;
    box-shadow: 0 0 12px rgba(34, 197, 94, 0.12);
  }

  /* active – against */
  .vote-active-against {
    background: rgba(239, 68, 68, 0.18) !important;
    border-color: rgba(239, 68, 68, 0.55) !important;
    color: #fff !important;
    box-shadow: 0 0 12px rgba(239, 68, 68, 0.12);
  }

  /* active – abstain */
  .vote-active-abstain {
    background: rgba(255,255,255,0.12) !important;
    border-color: rgba(255,255,255,0.35) !important;
    color: #fff !important;
  }

  /* non-active choices after voting – dimmed but clickable to switch */
  .vote-btn.vote-other {
    opacity: 0.28;
  }
  .vote-btn.vote-other:hover {
    opacity: 0.6;
  }

  .vote-btn .checkmark {
    margin-left: auto;
    opacity: 0.9;
  }
</style>
