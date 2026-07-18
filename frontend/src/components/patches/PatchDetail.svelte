<script lang="ts">
  import { onMount } from "svelte";
  import { marked } from "marked";
  import { getPatch, deletePatch, submitPatch, votePatch, listVotes, type Patch, type Vote } from "../../lib/patches";
  import { toaster } from "../../stores/toaster";
  import { currentUser } from "../../stores/auth";
  import { GITHUB_REPO } from "../../lib/config";
  import AuthorMeta from "../AuthorMeta.svelte";
  import ConfirmDialog from "../ConfirmDialog.svelte";

  export let patchId: string;

  let patch: Patch | null = null;
  let votes: Vote[] = [];
  let loading = true;
  let currentUserVote: Vote | null = null;

  // Dialogs
  let showVoteDialog = false;
  let pendingChoice = "";
  let showDeleteDialog = false;

  const STATUS_MAP: Record<string, { label: string; cls: string }> = {
    draft: { label: "草稿", cls: "bg-surface-300 text-surface-700" },
    voting: { label: "投票中", cls: "bg-warning-500 text-white" },
    passed: { label: "通过待合并", cls: "bg-info-500 text-white" },
    merged: { label: "已合并", cls: "bg-success-500 text-white" },
    rejected: { label: "未通过", cls: "bg-error-500 text-white" },
    failed: { label: "合并失败", cls: "bg-error-500 text-white" },
  };

  $: statusInfo = patch ? STATUS_MAP[patch.status] ?? { label: patch.status, cls: "" } : { label: "", cls: "" };
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
      toaster.error({ title: "错误", description: "无法加载变更" });
    } finally {
      loading = false;
    }
  });

  async function handleDelete() {
    try {
      await deletePatch(patchId);
      window.location.href = "/patches";
    } catch {
      toaster.error({ title: "删除失败" });
    }
  }

  async function handleSubmit() {
    try {
      patch = await submitPatch(patchId);
      toaster.success({ title: "已提交投票", description: "窗口期 3 天" });
    } catch (e: any) {
      toaster.error({ title: "提交失败", description: e.message ?? "" });
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
      toaster.success({ title: "投票成功" });
    } catch (e: any) {
      toaster.error({ title: "投票失败", description: e.message ?? "" });
    }
  }

  $: totalVotes = patch ? patch.for_count + patch.against_count + patch.abstain_count : 0;
  $: forPct = totalVotes > 0 ? Math.round((patch!.for_count / totalVotes) * 100) : 0;
  $: againstPct = totalVotes > 0 ? Math.round((patch!.against_count / totalVotes) * 100) : 0;
  $: abstainPct = totalVotes > 0 ? Math.round((patch!.abstain_count / totalVotes) * 100) : 0;
</script>

{#if loading}
  <div class="flex justify-center py-12 text-sm text-surface-400-600">加载中…</div>
{:else if !patch}
  <div class="flex justify-center py-12 text-sm text-surface-500">变更不存在</div>
{:else}
  <!-- Header -->
  <div class="mb-6">
    <div class="flex items-center gap-2">
      <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium {statusInfo.cls}">
        {statusInfo.label}
      </span>
      {#if patch.status === "voting" && deadlineStr}
        <span class="text-xs text-surface-500">{deadlineStr}</span>
      {/if}
      <a
        href="https://github.com/{GITHUB_REPO}/pull/{patch.pr_number}"
        target="_blank"
        class="text-sm text-primary-600 hover:text-primary-700"
      >
        PR #{patch.pr_number} ↗
      </a>
    </div>
    <h1 class="mt-2 text-xl font-bold text-surface-900-100">{patch.title}</h1>
    <div class="mt-1">
      <AuthorMeta username={patch.author_username ?? "匿名"} createdAt={patch.created_at} />
    </div>
  </div>

  <!-- Content (rendered markdown) -->
  <div class="mb-8 rounded-md border border-surface-200-800 bg-surface p-4">
    {#await marked.parse(patch.content, { breaks: true, gfm: true }) then html}
      <div class="markdown-body">{@html html}</div>
    {/await}
  </div>

  <!-- Vote panel -->
  {#if patch.status === "voting"}
    <div class="mb-8 rounded-md border border-surface-200-800 bg-surface p-4">
      <h3 class="mb-3 text-sm font-semibold text-surface-900-100">投票</h3>

      {#if deadlineStr && deadlineStr !== "已截止"}
        <p class="mb-3 text-xs text-surface-500">{deadlineStr}，截止后自动计票</p>
      {/if}

      <!-- Vote bars -->
      <div class="mb-4 flex h-2 overflow-hidden rounded-full bg-surface-200">
        {#if forPct > 0}
          <div class="bg-success-500 transition-all" style="width: {forPct}%"></div>
        {/if}
        {#if againstPct > 0}
          <div class="bg-error-500 transition-all" style="width: {againstPct}%"></div>
        {/if}
        {#if abstainPct > 0}
          <div class="bg-surface-400 transition-all" style="width: {abstainPct}%"></div>
        {/if}
      </div>

      <div class="mb-4 flex justify-between text-xs text-surface-500">
        <span>赞成 {patch.for_count}</span>
        <span>反对 {patch.against_count}</span>
        <span>弃权 {patch.abstain_count}</span>
      </div>

      {#if $currentUser}
        {#if currentUserVote}
          <div class="mb-3 text-sm text-surface-600">
            你的投票：<span class="font-medium">{currentUserVote.choice === "for" ? "赞成" : currentUserVote.choice === "against" ? "反对" : "弃权"}</span>
          </div>
        {/if}
        <div class="flex gap-2">
          <button
            class="btn {currentUserVote?.choice === 'for' ? 'preset-filled-success-500' : 'preset-tonal'} text-sm"
            on:click={() => promptVote("for")}
          >
            赞成
          </button>
          <button
            class="btn {currentUserVote?.choice === 'against' ? 'preset-filled-error-500' : 'preset-tonal'} text-sm"
            on:click={() => promptVote("against")}
          >
            反对
          </button>
          <button
            class="btn {currentUserVote?.choice === 'abstain' ? 'preset-filled-surface-300' : 'preset-tonal'} text-sm"
            on:click={() => promptVote("abstain")}
          >
            弃权
          </button>
        </div>
      {:else}
        <a href="/login" class="text-sm text-primary-600 hover:text-primary-700">登录后参与投票</a>
      {/if}
    </div>
  {/if}

  <!-- Results panel -->
  {#if patch.status === "merged" || patch.status === "rejected" || patch.status === "failed" || patch.status === "passed"}
    <div class="mb-8 rounded-md border border-surface-200-800 bg-surface p-4">
      <h3 class="mb-3 text-sm font-semibold text-surface-900-100">
        {patch.status === "merged" ? "已合并" : patch.status === "rejected" ? "未通过" : patch.status === "failed" ? "合并失败" : "已通过"}
      </h3>
      <div class="flex gap-4 text-sm text-surface-500">
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
        <button class="btn preset-filled-primary-500 text-sm" on:click={handleSubmit}>
          提交投票
        </button>
        <button class="btn preset-filled-error-500 text-sm" on:click={() => (showDeleteDialog = true)}>
          删除
        </button>
      {/if}
    </div>
  {/if}

  <!-- Vote list -->
  {#if votes.length > 0}
    <div class="rounded-md border border-surface-200-800 bg-surface">
      <h3 class="border-b border-surface-200-800 px-4 py-2 text-sm font-semibold text-surface-900-100">
        投票记录
      </h3>
      {#each votes as v (v.id)}
        <div class="flex items-center justify-between border-b border-surface-200-800/50 px-4 py-2 text-sm last:border-0">
          <span class="text-surface-700-300">{v.voter_username ?? "匿名"}</span>
          <span class="text-xs {v.choice === 'for' ? 'text-success-500' : v.choice === 'against' ? 'text-error-500' : 'text-surface-400'}">
            {v.choice === "for" ? "赞成" : v.choice === "against" ? "反对" : "弃权"}
          </span>
        </div>
      {/each}
    </div>
  {/if}
{/if}

<!-- Confirm dialogs -->
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
