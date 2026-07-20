<script lang="ts">
  import {
    ArrowLeft,
    CheckIcon,
    CircleMinusIcon,
    ExternalLink,
    FlagIcon,
    ThumbsDownIcon,
    ThumbsUpIcon,
  } from "@lucide/svelte";
  import { onMount } from "svelte";
  import { createReport, type ReportTargetType } from "../../lib/admin";
  import {
    formatVotingPeriod,
    getVotingCountdown,
    isActiveCreatorWindow,
    resolveVotingPeriodHours,
    type VotingCountdown,
  } from "../../lib/governance";
  import { locale, translateError, translator } from "../../lib/i18n";
  import { requestLogin } from "../../lib/login";
  import { renderMarkdown } from "../../lib/markdown";
  import { getPatch, deletePatch, submitPatch, votePatch, listVotes, listPatchComments, createPatchComment, type Patch, type Vote } from "../../lib/patches";
  import { deleteContent, likePost, unlikePost, type Comment } from "../../lib/posts";
  import { toaster } from "../../stores/toaster";
  import { currentUser } from "../../stores/auth";
  import { GITHUB_REPO } from "../../lib/config";
  import AuthorMeta from "../AuthorMeta.svelte";
  import ConfirmDialog from "../ConfirmDialog.svelte";
  import GlassModal from "../GlassModal.svelte";
  import TimelineItem from "../posts/TimelineItem.svelte";
  import VotingWindowMeta from "./VotingWindowMeta.svelte";

  let { patchId = "", embedded = false }: { patchId: string; embedded?: boolean } = $props();

  let patch = $state<Patch | null>(null);
  let votes = $state<Vote[]>([]);
  let loading = $state(true);
  let currentUserVote: Vote | null = $state(null);
  let comments = $state<Comment[]>([]);
  let replyingTo = $state<Comment | null>(null);
  let replyText = $state("");
  let submittingReply = $state(false);
  let submittingPatch = $state(false);
  let likingId = $state<string | null>(null);

  let showSubmitDialog = $state(false);
  let showVoteDialog = $state(false);
  let pendingChoice = $state("");
  let showDeleteDialog = $state(false);
  let pendingCommentDelete = $state<Comment | null>(null);
  let reportOpen = $state(false);
  let reportTarget = $state("");
  let reportTargetType = $state<ReportTargetType>("content");
  let reportReason = $state("");
  let reporting = $state(false);
  let currentTime = $state(Date.now());

  const STATUS_TYPES: Record<string, string> = {
    draft: "neutral",
    voting: "warning",
    passed: "info",
    merged: "success",
    rejected: "danger",
    failed: "danger",
  };

  let statusInfo = $derived(patch
    ? {
        label: $translator(`status.${patch.status}`),
        type: STATUS_TYPES[patch.status] ?? "neutral",
      }
    : { label: "", type: "neutral" });
  let deadline = $derived(getVotingCountdown(patch?.voting_ends_at ?? null, currentTime));
  let deadlineStr = $derived(formatDeadline(deadline));
  let votingIsOpen = $derived(
    patch?.status === "voting" && deadline !== null && deadline.state !== "closed",
  );

  function formatDeadline(value: VotingCountdown | null): string | null {
    if (!value) return null;
    if (value.state === "closed") return $translator("patch.closed");
    if (value.state === "days") {
      return $translator("patch.remainingDaysHours", {
        days: value.days,
        hours: value.hours,
      });
    }
    if (value.state === "hours") {
      return $translator("patch.remainingHours", { hours: value.hours });
    }
    return $translator("patch.remainingMinutes", { minutes: value.minutes });
  }

  function voteLabel(choice: string): string {
    return $translator(
      choice === "for" ? "patch.for" : choice === "against" ? "patch.against" : "patch.abstain",
    );
  }

  onMount(async () => {
    try {
      const [p, v, c] = await Promise.all([
        getPatch(patchId),
        listVotes(patchId),
        listPatchComments(patchId),
      ]);
      patch = p;
      votes = v;
      comments = c;
      const myVote = v.find((v) => v.voter_id === $currentUser?.id);
      if (myVote) currentUserVote = myVote;
    } catch {
      toaster.error($translator("common.error"), $translator("patch.loadFailed"));
    } finally {
      loading = false;
    }
  });

  onMount(() => {
    const timer = window.setInterval(() => (currentTime = Date.now()), 30_000);
    return () => window.clearInterval(timer);
  });

  $effect(() => {
    const endsAt = patch?.voting_ends_at ? Date.parse(patch.voting_ends_at) : NaN;
    if (!Number.isFinite(endsAt)) return;
    const remaining = endsAt - Date.now();
    if (remaining <= 0) return;

    const timer = window.setTimeout(() => (currentTime = Date.now()), remaining + 25);
    return () => window.clearTimeout(timer);
  });

  function patchReturnTo(fragment?: string) {
    return `/patches/${patchId}${fragment ? `#${fragment}` : ""}`;
  }

  async function handleDelete() {
    try {
      await deletePatch(patchId);
      window.location.href = "/";
    } catch {
      toaster.error($translator("patch.deleteFailed"));
    }
  }

  async function handleSubmit() {
    if (submittingPatch) return;
    submittingPatch = true;
    try {
      const submittedPatch = await submitPatch(patchId);
      patch = submittedPatch;
      currentTime = Date.now();

      const periodHours = resolveVotingPeriodHours(
        submittedPatch.voting_period_hours,
        submittedPatch.voting_started_at,
        submittedPatch.voting_ends_at,
      );
      const duration = formatVotingPeriod(periodHours, $locale);
      const activeCreatorWindow = isActiveCreatorWindow(
        submittedPatch.voting_window_kind,
        submittedPatch.voting_period_hours,
        submittedPatch.voting_started_at,
        submittedPatch.voting_ends_at,
      );
      const message = duration
        ? $translator(
            activeCreatorWindow
              ? "patch.activeCreatorVotingWindow"
              : "patch.votingWindowDuration",
            { duration },
          )
        : $translator("patch.votingWindow");
      toaster.success($translator("patch.submitted"), message);
    } catch (e: any) {
      toaster.error($translator("patch.submitFailed"), $translator("common.tryAgain"));
    } finally {
      submittingPatch = false;
    }
  }

  function promptVote(choice: string) {
    if (!votingIsOpen) return;
    pendingChoice = choice;
    showVoteDialog = true;
  }

  async function confirmVote() {
    if (!votingIsOpen) {
      toaster.error($translator("patch.closed"), $translator("patch.awaitingTally"));
      return;
    }
    try {
      const v = await votePatch(patchId, pendingChoice);
      currentUserVote = v;
      votes = [...votes.filter((v) => v.voter_id !== $currentUser?.id), v];
      patch = await getPatch(patchId);
      toaster.success($translator("patch.voteSuccess"));
    } catch (e: any) {
      toaster.error($translator("patch.voteFailed"), $translator("common.tryAgain"));
    }
  }

  function requestDeleteComment(comment: Comment) {
    pendingCommentDelete = comment;
    showDeleteDialog = true;
  }

  async function confirmDelete() {
    if (!pendingCommentDelete) {
      await handleDelete();
      return;
    }
    const target = pendingCommentDelete;
    try {
      await deleteContent(target.id);
      comments = comments.filter((item) => item.id !== target.id);
      if (patch) patch = { ...patch, comment_count: Math.max(0, patch.comment_count - 1) };
    } catch {
      toaster.error($translator("patch.deleteReplyTitle"), $translator("common.tryAgain"));
    } finally {
      pendingCommentDelete = null;
    }
  }

  function beginReply(comment: Comment) {
    if (!$currentUser) {
      requestLogin(patchReturnTo(comment.id), () => beginReply(comment));
      return;
    }
    replyingTo = comment;
    replyText = "";
    setTimeout(() => document.querySelector<HTMLTextAreaElement>("#patch-reply")?.focus(), 0);
  }

  async function submitReply() {
    if (!replyText.trim()) return;
    submittingReply = true;
    try {
      const comment = await createPatchComment(patchId, {
        content: replyText.trim(),
        ...(replyingTo ? { replying_id: replyingTo.id } : {}),
      });
      comments = [...comments, comment];
      replyText = "";
      replyingTo = null;
      if (patch) patch = { ...patch, comment_count: patch.comment_count + 1 };
    } catch (e: any) {
      toaster.error($translator("patch.commentFailed"), $translator("common.tryAgain"));
    } finally {
      submittingReply = false;
    }
  }

  async function toggleCommentLike(comment: Comment) {
    if (!$currentUser) {
      requestLogin(patchReturnTo(comment.id), () => void toggleCommentLike(comment));
      return;
    }
    likingId = comment.id;
    try {
      const state = comment.liked_by_me
        ? await unlikePost(comment.id)
        : await likePost(comment.id);
      comments = comments.map((item) =>
        item.id === comment.id ? { ...item, ...state } : item
      );
    } catch (e: any) {
      toaster.error($translator("common.operationFailed"), $translator("common.tryAgain"));
    } finally {
      likingId = null;
    }
  }

  async function shareComment(comment: Comment) {
    const url = `${window.location.origin}${patchReturnTo(comment.id)}`;
    try {
      if (navigator.share) await navigator.share({ title: patch?.title, url });
      else {
        await navigator.clipboard.writeText(url);
        toaster.success($translator("common.linkCopied"));
      }
    } catch (e: any) {
      if (e?.name !== "AbortError") toaster.error($translator("common.shareFailed"));
    }
  }

  function requestReport(
    targetId: string,
    targetType: ReportTargetType = "content",
  ) {
    if (!$currentUser) {
      requestLogin(
        patchReturnTo(targetType === "content" ? targetId : undefined),
        () => openReport(targetId, targetType),
      );
      return;
    }
    openReport(targetId, targetType);
  }

  function openReport(targetId: string, targetType: ReportTargetType) {
    reportTarget = targetId;
    reportTargetType = targetType;
    reportReason = "";
    reportOpen = true;
  }

  async function submitReport() {
    if (!reportReason.trim() || reporting) return;
    reporting = true;
    try {
      await createReport(reportTarget, reportReason.trim(), reportTargetType);
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
    {$translator("common.loading")}
  </div>
{:else if !patch}
  <div class="empty-state">{$translator("patch.notFound")}</div>
{:else}
  <!-- Back button -->
  {#if !embedded}<button class="btn btn-ghost btn-sm back-btn" onclick={goBack}>
    <ArrowLeft size={16} strokeWidth={1.8} aria-hidden="true" />
    <span>{$translator("common.back")}</span>
  </button>{/if}

  <!-- Header -->
  <div class="mb-6">
    <div class="patch-meta-row">
      <span class="badge badge-{statusInfo.type}">
        {statusInfo.label}
      </span>
      <VotingWindowMeta
        status={patch.status}
        votingWindowKind={patch.voting_window_kind}
        votingPeriodHours={patch.voting_period_hours}
        votingStartedAt={patch.voting_started_at}
        votingEndsAt={patch.voting_ends_at}
        showHistory
      />
      {#if patch.status === "voting" && deadlineStr}
        <span class="text-xs" style="color: var(--vercel-text-tertiary);">{deadlineStr}</span>
      {/if}
      <a
        href="https://github.com/{GITHUB_REPO}/pull/{patch.pr_number}"
        target="_blank"
        rel="noreferrer"
        class="patch-pr-link text-sm"
      >
        PR #{patch.pr_number}
        <ExternalLink size={13} strokeWidth={1.8} aria-hidden="true" />
      </a>
    </div>
    <h1 class="mt-2 text-xl font-bold" style="color: var(--vercel-text);">{patch.title}</h1>
    <div class="patch-author-row mt-1">
      <AuthorMeta username={patch.author_username ?? $translator("common.anonymous")} userId={patch.author_id} createdAt={patch.created_at} />
      {#if $currentUser?.id !== patch.author_id}
        <button
          type="button"
          class="btn btn-ghost btn-sm patch-report-action"
          onclick={() => requestReport(patch.id, "patch")}
        >
          <FlagIcon size={14} strokeWidth={1.8} aria-hidden="true" />
          {$translator("common.report")}
        </button>
      {/if}
    </div>
  </div>

  <!-- Content (rendered markdown) -->
  <div class="card p-4 mb-8">
    <div class="markdown-body">{@html renderMarkdown(patch.content)}</div>
  </div>

  <!-- Vote panel -->
  {#if patch.status === "voting"}
    <section class="vote-panel mb-8">
      <div class="vote-heading">
        <div>
          <p class="section-kicker">{$translator("patch.governance")}</p>
          <h3>{$translator("patch.governance")}</h3>
        </div>
        {#if deadlineStr}<span class="vote-deadline">{deadlineStr}</span>{/if}
      </div>

      {#if deadlineStr && votingIsOpen}
        <p class="mb-3 text-xs" style="color: var(--vercel-text-tertiary);">
          {$translator("patch.autoTally", { deadline: deadlineStr })}
        </p>
      {:else if !votingIsOpen}
        <p class="vote-closed-note">{$translator("patch.awaitingTally")}</p>
      {/if}

      <!-- Vote bar -->
      {#if totalVotes > 0}
        <div class="vote-bar flex h-2 mb-4 rounded-full overflow-hidden">
          <div style="width: {forPct}%; background: var(--vercel-success); transition: width 0.3s;"></div>
          <div style="width: {againstPct}%; background: var(--vercel-danger); transition: width 0.3s;"></div>
          <div class="vote-bar-abstain" style="width: {abstainPct}%;"></div>
        </div>
      {/if}

      <div class="vote-totals">
        <div class="vote-total is-for"><strong>{patch.for_count}</strong><span>{$translator("patch.for")}</span></div>
        <div class="vote-total is-against"><strong>{patch.against_count}</strong><span>{$translator("patch.against")}</span></div>
        <div class="vote-total"><strong>{patch.abstain_count}</strong><span>{$translator("patch.abstain")}</span></div>
      </div>

      {#if votingIsOpen && $currentUser}
        <div class="vote-actions">
          <button
            class="vote-choice"
            class:is-for={currentUserVote?.choice === "for"}
            class:is-other={Boolean(currentUserVote && currentUserVote.choice !== "for")}
            aria-pressed={currentUserVote?.choice === "for"}
            onclick={() => promptVote("for")}
          >
            <ThumbsUpIcon size={16} strokeWidth={1.8} />
            <span>{$translator("patch.for")}</span>
            {#if currentUserVote?.choice === "for"}
              <CheckIcon class="vote-check" size={14} strokeWidth={2.5} />
            {/if}
          </button>
          <button
            class="vote-choice"
            class:is-against={currentUserVote?.choice === "against"}
            class:is-other={Boolean(currentUserVote && currentUserVote.choice !== "against")}
            aria-pressed={currentUserVote?.choice === "against"}
            onclick={() => promptVote("against")}
          >
            <ThumbsDownIcon size={16} strokeWidth={1.8} />
            <span>{$translator("patch.against")}</span>
            {#if currentUserVote?.choice === "against"}
              <CheckIcon class="vote-check" size={14} strokeWidth={2.5} />
            {/if}
          </button>
          <button
            class="vote-choice"
            class:is-abstain={currentUserVote?.choice === "abstain"}
            class:is-other={Boolean(currentUserVote && currentUserVote.choice !== "abstain")}
            aria-pressed={currentUserVote?.choice === "abstain"}
            onclick={() => promptVote("abstain")}
          >
            <CircleMinusIcon size={16} strokeWidth={1.8} />
            <span>{$translator("patch.abstain")}</span>
            {#if currentUserVote?.choice === "abstain"}
              <CheckIcon class="vote-check" size={14} strokeWidth={2.5} />
            {/if}
          </button>
        </div>
        <p class="vote-change-hint">{$translator("patch.voteChangeHint")}</p>
      {:else if votingIsOpen}
        <a href="/login" class="text-sm transition-colors" style="color: var(--vercel-text-secondary);">{$translator("patch.loginToVote")}</a>
      {/if}
    </section>
  {/if}

  <!-- Results panel -->
  {#if patch.status === "merged" || patch.status === "rejected" || patch.status === "failed" || patch.status === "passed"}
    <div class="card p-4 mb-8">
      <h3 class="mb-3 text-sm font-semibold" style="color: var(--vercel-text);">
        {statusInfo.label}
      </h3>
      <div class="flex gap-4 text-sm" style="color: var(--vercel-text-secondary);">
        <span>{$translator("patch.for")} {patch.for_count}</span>
        <span>{$translator("patch.against")} {patch.against_count}</span>
        <span>{$translator("patch.abstain")} {patch.abstain_count}</span>
        <span>{$translator("patch.totalVotes", { count: totalVotes })}</span>
      </div>
    </div>
  {/if}

  <!-- Author actions -->
  {#if $currentUser?.id === patch.author_id}
    <div class="mb-8 flex gap-2">
      {#if patch.status === "draft"}
        <button
          class="btn btn-primary btn-sm"
          disabled={submittingPatch}
          onclick={() => (showSubmitDialog = true)}
        >
          {$translator(submittingPatch ? "patch.submitting" : "patch.submit")}
        </button>
        <button class="btn btn-danger btn-sm" onclick={() => { pendingCommentDelete = null; showDeleteDialog = true; }}>
          {$translator("common.delete")}
        </button>
      {/if}
    </div>
  {/if}

  <!-- Discussion -->
  <section class="discussion-section" aria-labelledby="discussion-title">
    <div class="discussion-heading">
      <div>
        <p class="section-kicker">{$translator("common.discussion")}</p>
        <h2 id="discussion-title">{$translator("common.discussion")} <span>{patch.comment_count}</span></h2>
      </div>
      <p>{$translator("patch.discussionDescription")}</p>
    </div>

    {#if comments.length > 0}
      <div class="relative">
        <div class="timeline-line"></div>
        {#each comments as comment (comment.id)}
          <TimelineItem
            username={comment.author_username ?? $translator("common.anonymous")}
            userId={comment.author_id}
            createdAt={comment.created_at}
            content={comment.content}
            title={null}
            tags={null}
            replyingToUsername={comment.replying_to_username}
            replyingToContent={comment.replying_to_content}
            replyingToId={comment.replying_id}
            contentId={comment.id}
            onReply={$currentUser ? () => beginReply(comment) : null}
            onDelete={$currentUser?.id === comment.author_id ? () => requestDeleteComment(comment) : null}
            liked={comment.liked_by_me}
            likeCount={comment.like_count}
            replyCount={comment.reply_count}
            liking={likingId === comment.id}
            onLike={() => toggleCommentLike(comment)}
            onDiscuss={() => beginReply(comment)}
            onShare={() => shareComment(comment)}
            onReport={$currentUser?.id === comment.author_id
              ? null
              : () => requestReport(comment.id)}
          />
        {/each}
      </div>
    {:else}
      <div class="discussion-empty">{$translator("patch.discussionEmpty")}</div>
    {/if}

    {#if $currentUser}
      <div class="reply-composer">
        {#if replyingTo}
          <div class="replying-label">
            <span>{$translator("common.replyingTo", { name: replyingTo.author_username ?? $translator("common.anonymous") })}</span>
            <button type="button" onclick={() => (replyingTo = null)}>{$translator("common.cancel")}</button>
          </div>
        {/if}
        <textarea
          id="patch-reply"
          class="input"
          bind:value={replyText}
          placeholder={$translator("patch.commentPlaceholder")}
        ></textarea>
        <div class="composer-footer">
          <span>{$translator("common.markdownSupported")}</span>
          <button class="btn btn-primary btn-sm" disabled={submittingReply || !replyText.trim()} onclick={submitReply}>
            {submittingReply ? $translator("common.sending") : $translator("patch.joinDiscussion")}
          </button>
        </div>
      </div>
    {:else}
      <a class="discussion-login" href="/login?returnTo={encodeURIComponent(`/patches/${patchId}`)}">{$translator("patch.loginToDiscuss")}</a>
    {/if}
  </section>

  <!-- Vote list -->
  {#if votes.length > 0}
    <div class="card mb-8">
      <h3 class="px-4 py-2 text-sm font-semibold border-b" style="color: var(--vercel-text); border-color: var(--vercel-border);">
        {$translator("patch.voteRecords")}
      </h3>
      {#each votes as v (v.id)}
        <div class="flex items-center justify-between px-4 py-2 text-sm border-b last:border-0" style="border-color: var(--vercel-border);">
          <span style="color: var(--vercel-text-secondary);">{v.voter_username ?? $translator("common.anonymous")}</span>
          <span class="text-xs" style="color: {v.choice === 'for' ? 'var(--vercel-success)' : v.choice === 'against' ? 'var(--vercel-danger)' : 'var(--vercel-text-tertiary)'};">
            {voteLabel(v.choice)}
          </span>
        </div>
      {/each}
    </div>
  {/if}
{/if}

<ConfirmDialog
  bind:open={showSubmitDialog}
  title={$translator("patch.submitConfirmTitle")}
  description={$translator("patch.submitConfirmDescription")}
  confirmText={$translator("patch.submit")}
  tone="primary"
  onConfirm={handleSubmit}
/>

<ConfirmDialog
  bind:open={showDeleteDialog}
  title={$translator(pendingCommentDelete ? "patch.deleteReplyTitle" : "patch.deleteTitle")}
  description={$translator(pendingCommentDelete ? "patch.deleteReplyDescription" : "patch.deleteDescription")}
  confirmText={$translator("common.delete")}
  onConfirm={confirmDelete}
/>

<ConfirmDialog
  bind:open={showVoteDialog}
  title={$translator("patch.castVoteTitle", { choice: voteLabel(pendingChoice) })}
  description={$translator("patch.castVoteDescription", { choice: voteLabel(pendingChoice) })}
  confirmText={$translator("common.confirm")}
  onConfirm={confirmVote}
/>

<GlassModal
  show={reportOpen}
  title={$translator("moderation.reportTitle")}
  onclose={() => (reportOpen = false)}
>
  <textarea
    class="input report-reason"
    rows="4"
    bind:value={reportReason}
    maxlength="500"
    aria-label={$translator("moderation.reportReasonPlaceholder")}
    placeholder={$translator("moderation.reportReasonPlaceholder")}
  ></textarea>
  <div class="report-actions">
    <button class="btn btn-ghost btn-sm" onclick={() => (reportOpen = false)}>
      {$translator("common.cancel")}
    </button>
    <button
      class="btn btn-primary btn-sm"
      disabled={reporting || !reportReason.trim()}
      onclick={submitReport}
    >
      {$translator(reporting ? "moderation.reporting" : "moderation.reportSubmit")}
    </button>
  </div>
</GlassModal>

<style>
  .patch-meta-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }

  .patch-report-action {
    margin-left: auto;
  }

  .patch-author-row {
    display: flex;
    min-width: 0;
    align-items: center;
    gap: 0.75rem;
  }

  .patch-pr-link {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    color: var(--vercel-text-secondary);
    transition: color 150ms ease;
  }

  .patch-pr-link:hover {
    color: var(--vercel-text);
  }

  .section-kicker {
    margin-bottom: 0.2rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.625rem;
    font-weight: 650;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .vote-panel {
    overflow: hidden;
    padding: 1.125rem;
    border: 1px solid var(--vercel-border-hover);
    border-radius: var(--vercel-radius-lg);
    background: color-mix(in srgb, var(--vercel-accent) 3%, var(--vercel-card));
  }

  .vote-bar {
    background: var(--vercel-surface-muted);
  }

  .vote-bar > div {
    transition: width 0.3s ease;
  }

  .vote-bar-abstain {
    background: var(--vercel-neutral-bg);
  }

  .vote-heading,
  .discussion-heading,
  .composer-footer,
  .replying-label {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .vote-heading {
    margin-bottom: 1rem;
  }

  .vote-heading h3,
  .discussion-heading h2 {
    font-size: 1rem;
    font-weight: 650;
  }

  .vote-deadline {
    padding: 0.3rem 0.55rem;
    border: 1px solid var(--vercel-border);
    border-radius: 0.375rem;
    color: var(--vercel-text-secondary);
    font-size: 0.7rem;
    font-variant-numeric: tabular-nums;
  }

  .vote-totals {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.5rem;
    margin: 0.75rem 0 1rem;
  }

  .vote-total {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    padding: 0.6rem 0.7rem;
    border-radius: 0.4rem;
    background: var(--vercel-surface-muted);
  }

  .vote-total strong {
    color: var(--vercel-text);
    font-size: 1.125rem;
    font-variant-numeric: tabular-nums;
  }

  .vote-total span {
    color: var(--vercel-text-tertiary);
    font-size: 0.7rem;
  }

  .vote-total.is-for strong { color: var(--vercel-success); }
  .vote-total.is-against strong { color: var(--vercel-danger); }

  .vote-actions {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.5rem;
  }

  .vote-choice {
    display: inline-flex;
    min-width: 0;
    min-height: 2.5rem;
    padding: 0.5rem 0.7rem;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    border: 1px solid var(--vercel-border-hover);
    border-radius: 0.5rem;
    color: var(--vercel-text-secondary);
    background: var(--vercel-hover);
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: color 180ms ease, border-color 180ms ease, background 180ms ease, opacity 180ms ease, transform 180ms ease;
  }

  .vote-choice:hover {
    color: var(--vercel-text);
    transform: translateY(-1px);
  }

  .vote-choice.is-for {
    border-color: color-mix(in srgb, var(--vercel-success) 55%, transparent);
    color: var(--vercel-success);
    background: color-mix(in srgb, var(--vercel-success) 12%, transparent);
  }

  .vote-choice.is-against {
    border-color: color-mix(in srgb, var(--vercel-danger) 55%, transparent);
    color: var(--vercel-danger);
    background: color-mix(in srgb, var(--vercel-danger) 12%, transparent);
  }

  .vote-choice.is-abstain {
    border-color: var(--vercel-text-tertiary);
    color: var(--vercel-text);
    background: var(--vercel-hover-strong);
  }

  .vote-choice.is-other {
    opacity: 0.7;
  }

  .vote-choice.is-other:hover {
    opacity: 1;
  }

  .vote-change-hint {
    margin: 0.65rem 0 0;
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
    line-height: 1.45;
    text-align: center;
  }

  .vote-closed-note {
    margin: 0 0 0.75rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
    line-height: 1.45;
  }

  .vote-check {
    margin-left: auto;
  }

  .report-reason {
    width: 100%;
    resize: vertical;
  }

  .report-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    margin-top: 1rem;
  }

  .discussion-section {
    margin: 2.5rem 0;
    padding-top: 1.5rem;
    border-top: 1px solid var(--vercel-border);
  }

  .discussion-heading {
    align-items: end;
    margin-bottom: 1.25rem;
  }

  .discussion-heading h2 span {
    margin-left: 0.25rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.8rem;
    font-weight: 500;
  }

  .discussion-heading > p {
    max-width: 18rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
    text-align: right;
  }

  .discussion-empty {
    margin-left: 1.75rem;
    padding: 2rem 1rem;
    border: 1px dashed var(--vercel-border);
    border-radius: var(--vercel-radius);
    color: var(--vercel-text-tertiary);
    font-size: 0.8125rem;
    text-align: center;
  }

  .reply-composer {
    margin: 1rem 0 0 1.75rem;
    padding: 0.75rem;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius);
    background: var(--vercel-surface-muted);
  }

  .replying-label {
    margin-bottom: 0.5rem;
    color: var(--vercel-text-secondary);
    font-size: 0.72rem;
  }

  .replying-label button {
    color: var(--vercel-text-tertiary);
  }

  .composer-footer {
    margin-top: 0.5rem;
  }

  .composer-footer span {
    color: var(--vercel-text-tertiary);
    font-size: 0.68rem;
  }

  .discussion-login {
    display: block;
    margin-left: 1.75rem;
    padding: 1rem;
    border-top: 1px solid var(--vercel-border);
    font-size: 0.8125rem;
    text-align: center;
  }

  @media (max-width: 36rem) {
    .discussion-heading {
      align-items: start;
      flex-direction: column;
    }
    .discussion-heading > p { text-align: left; }
    .vote-actions { grid-template-columns: 1fr; }
  }

  .back-btn {
    margin-bottom: 1rem;
  }
</style>
