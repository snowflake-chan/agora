<script lang="ts">
  import { onMount } from "svelte";
  import { marked } from "marked";
  import { getPatch, deletePatch, submitPatch, votePatch, listVotes, type Patch, type Vote } from "../../lib/patches";
  import { toaster } from "../../stores/toaster";
  import { currentUser } from "../../stores/auth";
  import AuthorMeta from "../AuthorMeta.svelte";
  import ConfirmDialog from "../ConfirmDialog.svelte";

  export let patchId: string;

  let patch: Patch | null = null;
  let votes: Vote[] = [];
  let loading = true;
  let currentUserVote: Vote | null = null;

  let showVoteDialog = false;
  let pendingChoice = "";
  let showDeleteDialog = false;

  const STATUS_MAP: Record<string, { label: string; type: string }> = {
    draft: { label: "草稿", type: "neutral" },
    voting: { label: "投票中", type: "warning" },
    passed: { label: "通过待合并", type: "info" },
    merged: { label: "已合并", type: "success" },
    rejected: { label: "未通过", type: "danger" },
    failed: { label: "合并失败", type: "danger" },
  };

  $: statusInfo = patch ? STATUS_MAP[patch.status] ?? { label: patch.status, type: "neutral" } : { label: "", type: "neutral" };
  $: deadlineStr = patch?.voting_ends_at ? formatDeadline(patch.voting_ends_at) : null;

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
      window.location.href = "/patches";
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

  $: totalVotes = patch ? patch.for_count + patch.against_count + patch.abstain_count : 0;
  $: forPct = totalVotes > 0 ? Math.round((patch!.for_count / totalVotes) * 100) : 0;
  $: againstPct = totalVotes > 0 ? Math.round((patch!.against_count / totalVotes) * 100) : 0;
  $: abstainPct = totalVotes > 0 ? Math.round((patch!.abstain_count / totalVotes) * 100) : 0;
</script>

{#if loading}
  <div class="empty-state">
    <div class="spinner mb-3"></div>
    加载中...
  </div>
{:else if !patch}
  <div class="empty-state">变更不存在</div>
{:else}
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
        href="https://github.com/{patch.pr_number}"
        target="_blank"
        class="text-sm transition-colors"
        style="color: var(--vercel-text-secondary);"
        on:mouseenter={(e) => e.currentTarget.style.color = 'var(--vercel-text)'}
        on:mouseleave={(e) => e.currentTarget.style.color = 'var(--vercel-text-secondary)'}
      >
        PR #{patch.pr_number} ↗
      </a>
    </div>
    <h1 class="mt-2 text-xl font-bold" style="color: var(--vercel-text);">{patch.title}</h1>
    <div class="mt-1">
      <AuthorMeta username={patch.author_username ?? "匿名"} createdAt={patch.created_at} />
    </div>
  </div>

  <!-- Content (rendered markdown) -->
  <div class="card p-4 mb-8">
    {#await marked.parse(patch.content, { breaks: true, gfm: true }) then html}
      <div class="markdown-body">{@html html}</div>
    {/await}
  </div>

  <!-- Vote panel -->
  {#if patch.status === "voting"}
    <div class="card p-4 mb-8">
      <h3 class="mb-3 text-sm font-semibold" style="color: var(--vercel-text);">投票</h3>

      {#if deadlineStr && deadlineStr !== "已截止"}
        <p class="mb-3 text-xs" style="color: var(--vercel-text-tertiary);">{deadlineStr}，截止后自动计票</p>
      {/if}

      <!-- Vote bars -->
      <div class="progress-bar mb-4" style="height: 6px; border-radius: 3px;">
        {#if forPct > 0}
          <div class="progress-fill" style="width: {forPct}%; background: var(--vercel-success);"></div>
        {/if}
        {#if againstPct > 0}
          <div class="progress-fill" style="width: {againstPct}%; background: var(--vercel-danger);"></div>
        {/if}
        {#if abstainPct > 0}
          <div class="progress-fill" style="width: {abstainPct}%; background: rgba(255,255,255,0.15);"></div>
        {/if}
      </div>
      <!-- Note: this stacked bar approach is simplified - see note below -->
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
        {#if currentUserVote}
          <div class="mb-3 text-sm" style="color: var(--vercel-text-secondary);">
            你的投票：<span class="font-medium" style="color: var(--vercel-text);">{currentUserVote.choice === "for" ? "赞成" : currentUserVote.choice === "against" ? "反对" : "弃权"}</span>
          </div>
        {/if}
        <div class="flex gap-2">
          <button
            class="btn {currentUserVote?.choice === 'for' ? 'btn-primary' : 'btn-secondary'} btn-sm"
            on:click={() => promptVote("for")}
          >
            赞成
          </button>
          <button
            class="btn {currentUserVote?.choice === 'against' ? 'btn-primary' : 'btn-secondary'} btn-sm"
            on:click={() => promptVote("against")}
          >
            反对
          </button>
          <button
            class="btn {currentUserVote?.choice === 'abstain' ? 'btn-primary' : 'btn-secondary'} btn-sm"
            on:click={() => promptVote("abstain")}
          >
            弃权
          </button>
        </div>
      {:else}
        <a href="/login" class="text-sm transition-colors" style="color: var(--vercel-text-secondary);" on:mouseenter={(e) => e.currentTarget.style.color = 'var(--vercel-text)'} on:mouseleave={(e) => e.currentTarget.style.color = 'var(--vercel-text-secondary)'}>登录后参与投票</a>
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
        <button class="btn btn-primary btn-sm" on:click={handleSubmit}>
          提交投票
        </button>
        <button class="btn btn-danger btn-sm" on:click={() => (showDeleteDialog = true)}>
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