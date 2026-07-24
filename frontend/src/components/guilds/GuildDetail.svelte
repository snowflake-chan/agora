<script lang="ts">
  import { onMount, tick } from "svelte";
  import {
    getGuild, joinGuild, leaveGuild,
    getMyMembership, listMembers, listGuildPatches, listDiscussions,
    createDiscussion, deleteDiscussion,
    getGuildLevel, listGuildProposals,
    type Guild, type GuildMember, type GuildDiscussion,
    type GuildLevelDetail, type GuildProposalContribution,
  } from "../../lib/guilds";
  import { createReport } from "../../lib/admin";
  import { translator, translateError } from "../../lib/i18n";
  import type { DisplayTranslation } from "../../lib/ai";
  import { requestLogin } from "../../lib/login";
  import { guildLevelColor, guildLevelKey, isGuildLogoImage } from "../../lib/guildPresentation";
  import { onModerationUpdateForPath } from "../../lib/moderation";
  import type { Patch } from "../../lib/patches";
  import VoteSummary from "../patches/VoteSummary.svelte";
  import { currentUser, initAuth } from "../../stores/auth";
  import { toaster } from "../../stores/toaster";
  import { avatarInitial } from "../../lib/utils";
  import { Flag, LockKeyhole, RefreshCw, Trash2 } from "@lucide/svelte";
  import ConfirmDialog from "../ConfirmDialog.svelte";
  import ReportDialog from "../moderation/ReportDialog.svelte";
  import VotingWindowMeta from "../patches/VotingWindowMeta.svelte";
  import GuildMemberCard from "./GuildMemberCard.svelte";
  import ModerationNotice from "../posts/ModerationNotice.svelte";
  import PostAiTools from "../posts/PostAiTools.svelte";
  import RelativeTime from "../RelativeTime.svelte";

  let { guildId }: { guildId: string } = $props();

  let guild = $state<Guild | null>(null);
  let members = $state<GuildMember[]>([]);
  let patches = $state<Patch[]>([]);
  let discussions = $state<GuildDiscussion[]>([]);
  let patchesError = $state(false);
  let discussionsError = $state(false);
  let discussionsLoading = $state(false);
  let discussionTranslations = $state<Record<string, DisplayTranslation | null>>({});
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let joining = $state(false);
  let leaving = $state(false);
  let tab = $state<"patches" | "members" | "discussions">("patches");

  let discussionTitle = $state("");
  let discussionContent = $state("");
  let discussionSending = $state(false);
  let myMembership = $state<GuildMember | null>(null);
  let confirmOpen = $state(false);
  let confirmTitle = $state("");
  let confirmDescription = $state("");
  let confirmAction = $state<() => void>(() => {});
  let reportOpen = $state(false);
  let reportTarget = $state<GuildDiscussion | null>(null);
  let reportReason = $state("");
  let reporting = $state(false);

  let levelDetail = $state<GuildLevelDetail | null>(null);
  let contributions = $state<GuildProposalContribution[]>([]);
  let contributionsTotal = $state(0);
  let contributionsLoading = $state(false);
  let contributionsError = $state(false);

  let contributors = $derived(topContributors(contributions));

  onMount(() => {
    void (async () => {
      await initAuth();
      await loadAll();
      await revealHashTarget();
    })();
    return onModerationUpdateForPath(`/guilds/${guildId}`, () => {
      if (canViewDiscussions()) void loadDiscussions();
    });
  });

  async function loadAll() {
    loading = true;
    loadError = null;
    actionError = null;
    patchesError = false;
    discussionsError = false;
    discussions = [];
    contributionsError = false;
    try {
      const [g, m, mine, lvl] = await Promise.all([
        getGuild(guildId),
        listMembers(guildId),
        $currentUser ? getMyMembership(guildId) : Promise.resolve(null),
        getGuildLevel(guildId),
      ]);
      guild = g;
      members = m;
      myMembership = mine;
      levelDetail = lvl;
      await loadContributions();
      try {
        patches = await listGuildPatches(guildId);
      } catch {
        patches = [];
        patchesError = true;
      }
      if (canViewDiscussions()) {
        await loadDiscussions();
      }
    } catch (e: any) {
      loadError = translateError(e, $translator, "guild.loadFailed");
    } finally {
      loading = false;
      contributionsLoading = false;
    }
  }

  async function loadContributions() {
    contributionsLoading = true;
    contributionsError = false;
    try {
      const result = await listGuildProposals(guildId);
      contributions = result.items;
      contributionsTotal = result.total;
    } catch {
      contributions = [];
      contributionsTotal = 0;
      contributionsError = true;
    } finally {
      contributionsLoading = false;
    }
  }

  async function handleJoin() {
    joining = true;
    actionError = null;
    try { await joinGuild(guildId); await loadAll(); } catch (e: any) {
      actionError = translateError(e, $translator, "guild.joinFailed");
    }
    finally { joining = false; }
  }

  async function handleLeave() {
    leaving = true;
    actionError = null;
    try { await leaveGuild(guildId); await loadAll(); } catch (e: any) {
      actionError = translateError(e, $translator, "guild.leaveFailed");
    }
    finally { leaving = false; }
  }

  async function handlePostDiscussion() {
    if (!discussionContent.trim()) return;
    discussionSending = true;
    actionError = null;
    try {
      await createDiscussion(guildId, { title: discussionTitle.trim() || null, content: discussionContent.trim() });
      discussionTitle = "";
      discussionContent = "";
      await loadDiscussions();
    } catch (e: any) {
      actionError = translateError(e, $translator, "guild.discussionFailed");
    }
    finally { discussionSending = false; }
  }

  async function handleDeletePost(postId: string) {
    actionError = null;
    try {
      await deleteDiscussion(guildId, postId);
      discussions = discussions.filter((d) => d.id !== postId);
    } catch (e: any) {
      actionError = translateError(e, $translator, "guild.deleteDiscussionFailed");
    }
  }

  async function loadDiscussions() {
    discussionsLoading = true;
    discussionsError = false;
    try {
      discussions = await listDiscussions(guildId);
    } catch {
      discussions = [];
      discussionsError = true;
    } finally {
      discussionsLoading = false;
    }
  }

  function isApprovedMember() {
    return Boolean(myMembership && ["approved", ""].includes(myMembership.status));
  }

  function canViewDiscussions() {
    return isApprovedMember()
      || $currentUser?.role === "moderator"
      || $currentUser?.role === "super_admin";
  }

  async function revealHashTarget() {
    const rawTargetId = window.location.hash.slice(1);
    if (!rawTargetId) return;
    let targetId: string;
    try {
      targetId = decodeURIComponent(rawTargetId);
    } catch {
      return;
    }
    tab = "discussions";
    await tick();
    document.getElementById(targetId)?.scrollIntoView({ block: "center" });
  }

  function requestGuildLogin() {
    requestLogin(
      `${window.location.pathname}${window.location.search}${window.location.hash}`,
      () => {
        void (async () => {
          await loadAll();
          await revealHashTarget();
        })();
      },
    );
  }

  function openReport(discussion: GuildDiscussion) {
    if (!$currentUser) {
      requestGuildLogin();
      return;
    }
    reportTarget = discussion;
    reportReason = "";
    reportOpen = true;
  }

  async function submitReport(reason: string) {
    if (!reportTarget || !reason.trim() || reporting) return;
    reporting = true;
    try {
      await createReport(reportTarget.id, reason.trim(), "content");
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

  function roleLabel(role: string) {
    return $translator(`guild.role.${role}`);
  }

  function requestConfirmation(
    title: string,
    description: string,
    action: () => void,
  ) {
    confirmTitle = title;
    confirmDescription = description;
    confirmAction = action;
    confirmOpen = true;
  }

  function topContributors(items: GuildProposalContribution[], limit: number = 5) {
    const counts = new Map<string, number>();
    for (const item of items) {
      counts.set(item.username, (counts.get(item.username) || 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, limit);
  }
</script>

{#if loading}
  <div class="empty-state"><div class="spinner mb-3"></div>{$translator("guild.loading")}</div>
{:else if loadError}
  <div class="empty-state"><p style="color: var(--vercel-danger);">{loadError}</p></div>
{:else if guild}
  <header class="guild-header mb-6 text-center">
    <div class="guild-mark w-20 h-20 mx-auto flex items-center justify-center text-3xl mb-4" style="border-color: {guildLevelColor(guild.level)};">
      {#if isGuildLogoImage(guild.logo)}
        <img src={guild.logo!} alt="" class="guild-logo-image" loading="lazy" />
      {:else}
        {guild.logo || avatarInitial(guild.name)}
      {/if}
    </div>
    <div class="inline-flex items-center gap-2 mb-1">
      <h1 class="text-2xl font-bold" style="color: var(--vercel-text);">{guild.name}</h1>
      <span class="text-xs font-bold px-2 py-0.5 rounded-full" style="background: {guildLevelColor(guild.level)}22; color: {guildLevelColor(guild.level)}; border: 1px solid {guildLevelColor(guild.level)}44;">
        {$translator(guildLevelKey(guild.level))}
      </span>
    </div>
    {#if guild.description}
      <p class="text-sm mt-2 max-w-md mx-auto" style="color: var(--vercel-text-secondary);">{guild.description}</p>
    {/if}
    <div class="flex items-center justify-center gap-3 mt-3 text-xs" style="color: var(--vercel-text-tertiary);">
      <span>{$translator("guild.membersCount", { count: guild.member_count })}</span>
      <span>·</span>
      <span>{$translator("tokens.guildScore")}: {levelDetail?.proposal_score ?? 0}</span>
      <span>·</span>
      <span>{$translator("guild.presidentName", { name: guild.president_username })}</span>
    </div>

    {#if levelDetail}
      <div class="level-progress mx-auto mt-4 max-w-xs">
        <div class="flex items-center justify-between text-xs mb-1" style="color: var(--vercel-text-secondary);">
          <span>{$translator(guildLevelKey(levelDetail.current_level))}</span>
          {#if levelDetail.next_level && levelDetail.next_threshold}
            <span>{$translator("tokens.guildNextLevel", { level: levelDetail.next_level, score: levelDetail.next_threshold })}</span>
          {:else}
            <span>{$translator("guild.level.5")}</span>
          {/if}
        </div>
        <div class="level-progress-track" style="background: var(--vercel-border);">
          <div
            class="level-progress-fill"
            style="width: {Math.min(100, Math.round((levelDetail.progress_to_next ?? 0) * 100))}%; background: {guildLevelColor(levelDetail.current_level)};"
          ></div>
        </div>
      </div>
    {/if}

    {#if $currentUser}
      <div class="mt-4">
        {#if isApprovedMember()}
          <div class="flex items-center justify-center gap-2">
            <span class="text-xs px-2 py-0.5 rounded-full" style="background: var(--vercel-success-bg); color: var(--vercel-success);">
              {$translator("guild.joined")} · {roleLabel(myMembership!.role)}
            </span>
            {#if myMembership!.role !== "president"}
              <button
                class="btn btn-ghost btn-xs"
                onclick={() => requestConfirmation(
                  $translator("guild.leaveTitle"),
                  $translator("guild.leaveDescription"),
                  handleLeave,
                )}
                disabled={leaving}
              >{$translator("guild.leave")}</button>
            {/if}
            {#if myMembership!.role === "president" || myMembership!.role === "vice_president"}
              <a href="/guilds/{guildId}/manage" class="btn btn-ghost btn-xs no-underline">{$translator("guild.manage")}</a>
            {/if}
          </div>
        {:else if myMembership?.status === "pending"}
          <span class="text-xs px-2 py-1" style="color: var(--vercel-warning);">
            {$translator("guild.requestPending")}
          </span>
        {:else}
          <button class="btn btn-primary btn-sm" onclick={handleJoin} disabled={joining}>
            {$translator(joining ? "guild.joining" : "guild.join")}
          </button>
        {/if}
      </div>
    {/if}
  </header>

  {#if actionError}
    <div class="action-error mb-4" role="alert">{actionError}</div>
  {/if}

  {#if contributionsLoading}
    <div class="card p-4 mb-4">
      <div class="text-xs mb-2" style="color: var(--vercel-text-secondary);">{$translator("guild.proposalContributions")}</div>
      <div class="empty-state py-6"><div class="spinner mb-2"></div></div>
    </div>
  {:else if contributionsError}
    <div class="card p-4 mb-4">
      <div class="text-xs mb-2" style="color: var(--vercel-text-secondary);">{$translator("guild.proposalContributions")}</div>
      <div class="inline-error" role="alert">
        <span>{$translator("guild.proposalContributionsLoadFailed")}</span>
        <button class="btn btn-ghost btn-xs" type="button" onclick={loadContributions}>
          <RefreshCw size={13} aria-hidden="true" />
          {$translator("common.retry")}
        </button>
      </div>
    </div>
  {:else if contributions.length > 0}
    <div class="card p-4 mb-4">
      <div class="flex items-center justify-between mb-3">
        <div class="text-xs font-medium" style="color: var(--vercel-text-secondary);">{$translator("guild.proposalContributions")}</div>
        <div class="text-xs" style="color: var(--vercel-text-tertiary);">{contributionsTotal} {$translator("common.proposals")}</div>
      </div>
      <div class="contributor-list">
        {#each contributors as [username, count], index (username)}
          <div class="contributor-row flex items-center justify-between py-1.5" class:border-b={index < contributors.length - 1}>
            <div class="flex items-center gap-2 text-sm" style="color: var(--vercel-text);">
              <span class="contributor-rank w-5 text-xs text-center" style="color: var(--vercel-text-tertiary);">{index + 1}</span>
              <span class="truncate">{username}</span>
            </div>
            <span class="text-xs" style="color: var(--vercel-text-tertiary);">{count} {$translator("common.proposals")}</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <div class="guild-tabs flex gap-1 border-b mb-4" style="border-color: var(--vercel-border);">
    <button class="filter-tab" class:active={tab === "patches"} onclick={() => tab = "patches"}>{$translator("guild.tabs.patches")}</button>
    <button class="filter-tab" class:active={tab === "members"} onclick={() => tab = "members"}>{$translator("guild.tabs.members")}</button>
    <button class="filter-tab" class:active={tab === "discussions"} onclick={() => tab = "discussions"}>{$translator("guild.tabs.discussions")}</button>
  </div>

  {#if tab === "patches"}
    {#if patchesError}
      <div class="inline-error" role="alert">
        <span>{$translator("guild.patchesLoadFailed")}</span>
        <button class="btn btn-ghost btn-xs" type="button" onclick={loadAll}>
          <RefreshCw size={13} aria-hidden="true" />
          {$translator("common.retry")}
        </button>
      </div>
    {:else if patches.length === 0}
      <div class="empty-state"><p>{$translator("guild.noPatches")}</p></div>
    {:else}
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {#each patches as p (p.id)}
          <a href="/patches/{p.id}" class="patch-card card p-4 block no-underline">
            <h3 class="font-semibold text-sm" style="color: var(--vercel-text);">{p.title}</h3>
            <div class="flex flex-wrap items-center gap-2 mt-2 text-xs" style="color: var(--vercel-text-tertiary);">
              <VoteSummary
                forCount={p.for_count}
                againstCount={p.against_count}
                abstainCount={p.abstain_count}
              />
              <RelativeTime value={p.created_at} />
              <VotingWindowMeta
                status={p.status}
                votingWindowKind={p.voting_window_kind}
                votingPeriodHours={p.voting_period_hours}
                votingStartedAt={p.voting_started_at}
                votingEndsAt={p.voting_ends_at}
              />
            </div>
          </a>
        {/each}
      </div>
    {/if}

  {:else if tab === "members"}
    <div class="guild-members-grid gap-3">
      {#each members as m (m.id)}
        <GuildMemberCard member={m} />
      {/each}
    </div>

  {:else}
    {#if !canViewDiscussions()}
      <div class="private-state text-center">
        <LockKeyhole size={22} aria-hidden="true" />
        <p>{$translator(
          myMembership?.status === "pending"
            ? "guild.discussionsPending"
            : "guild.discussionsPrivate",
        )}</p>
        {#if $currentUser && !myMembership}
          <button class="btn btn-primary btn-sm mt-3" onclick={handleJoin} disabled={joining}>
            {$translator(joining ? "guild.joining" : "guild.join")}
          </button>
        {:else if !$currentUser}
          <button class="btn btn-primary btn-sm mt-3" type="button" onclick={requestGuildLogin}>
            {$translator("nav.login")}
          </button>
        {/if}
      </div>
    {:else if discussionsLoading}
      <div class="empty-state"><div class="spinner mb-3"></div>{$translator("guild.loading")}</div>
    {:else if discussionsError}
      <div class="inline-error" role="alert">
        <span>{$translator("guild.discussionsLoadFailed")}</span>
        <button class="btn btn-ghost btn-xs" type="button" onclick={loadDiscussions}>
          <RefreshCw size={13} aria-hidden="true" />
          {$translator("common.retry")}
        </button>
      </div>
    {:else}
      {#if isApprovedMember()}
        <div class="card p-4 mb-4">
          <input class="input mb-2" type="text" bind:value={discussionTitle} aria-label={$translator("guild.discussionTitlePlaceholder")} placeholder={$translator("guild.discussionTitlePlaceholder")} maxlength="200" />
          <textarea class="input mb-2" rows="3" bind:value={discussionContent} aria-label={$translator("guild.discussionPlaceholder")} placeholder={$translator("guild.discussionPlaceholder")} maxlength="20000"></textarea>
          <div class="flex justify-end">
            <button class="btn btn-primary btn-sm" onclick={handlePostDiscussion} disabled={discussionSending || !discussionContent.trim()}>
              {$translator(discussionSending ? "common.sending" : "common.publish")}
            </button>
          </div>
        </div>
      {/if}

      {#if discussions.length === 0}
        <div class="empty-state"><p>{$translator("guild.noDiscussions")}</p></div>
      {:else}
        {#each discussions as d (d.id)}
          {@const displayTranslation = discussionTranslations[d.id] ?? null}
          <div id={d.id} class="card discussion-card p-4 mb-2">
            <ModerationNotice
              status={d.moderation_status}
              reason={d.moderation_reason}
              reviewNote={d.moderation_review_note}
              compact
            />
            <div class="flex items-center justify-between mb-1">
              <div class="flex items-center gap-2 text-xs" style="color: var(--vercel-text-tertiary);">
                <a href="/users/{d.author_id}" class="font-medium no-underline" style="color: var(--vercel-text-secondary);">{d.author_username}</a>
                <span>·</span>
                <RelativeTime value={d.created_at} />
              </div>
              <div class="discussion-actions">
                {#if $currentUser?.id !== d.author_id && d.moderation_status !== "pending_review" && d.moderation_status !== "rejected"}
                  <button
                    class="btn-icon discussion-action"
                    type="button"
                    title={$translator("common.report")}
                    aria-label={$translator("common.report")}
                    onclick={() => openReport(d)}
                  ><Flag size={15} aria-hidden="true" /></button>
                {/if}
                {#if $currentUser?.id === d.author_id && d.revision_number === 1}
                  <button
                    class="btn-icon discussion-action discussion-delete"
                    type="button"
                    title={$translator("common.delete")}
                    aria-label={$translator("common.delete")}
                    onclick={() => requestConfirmation(
                      $translator("guild.deleteDiscussionTitle"),
                      $translator("guild.deleteDiscussionDescription"),
                      () => handleDeletePost(d.id),
                    )}
                  ><Trash2 size={15} aria-hidden="true" /></button>
                {/if}
              </div>
            </div>
            {#if d.title}
              <h4 class="font-semibold text-sm mb-1" style="color: var(--vercel-text);">{displayTranslation?.title ?? d.title}</h4>
            {/if}
            <p class="text-sm" style="color: var(--vercel-text-secondary);">{displayTranslation?.body ?? d.content}</p>
            {#if d.moderation_status !== "pending_review" && d.moderation_status !== "rejected"}
              <PostAiTools
                text={d.content}
                title={d.title}
                context="guild"
                compact
                sourceContentId={d.id}
                sourceRevisionNumber={d.revision_number}
                moderationTargetHref={`/guilds/${guildId}`}
                onModerationQueued={() => {
                  discussions = discussions.map((item) => item.id === d.id
                    ? {
                        ...item,
                        moderation_status: "pending_review",
                        moderation_reason: null,
                        moderation_review_note: null,
                      }
                    : item);
                }}
                onTranslationChange={(translation) => {
                  discussionTranslations = {
                    ...discussionTranslations,
                    [d.id]: translation,
                  };
                }}
              />
            {/if}
          </div>
        {/each}
      {/if}
    {/if}
  {/if}
{/if}

<ConfirmDialog
  bind:open={confirmOpen}
  title={confirmTitle}
  description={confirmDescription}
  confirmText={$translator("common.confirm")}
  onConfirm={confirmAction}
/>

<ReportDialog
  bind:open={reportOpen}
  bind:reason={reportReason}
  {reporting}
  onsubmit={submitReport}
/>

<style>
  .guild-header {
    padding: 1.5rem 1rem 1.75rem;
    border-bottom: 1px solid var(--vercel-border);
  }

  .guild-mark {
    border: 2px solid var(--vercel-border);
    border-radius: var(--vercel-radius-lg);
    background: var(--vercel-surface);
  }

  .guild-logo-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: inherit;
  }

  .action-error {
    padding: 0.75rem 1rem;
    color: var(--vercel-danger);
    background: color-mix(in srgb, var(--vercel-danger) 9%, transparent);
    border-left: 3px solid var(--vercel-danger);
    font-size: 0.8125rem;
  }

  .patch-card {
    border: 1px solid var(--vercel-border);
    transition: border-color 180ms ease, background 180ms ease;
  }

  .patch-card:hover {
    border-color: var(--vercel-border-hover);
    background: var(--vercel-hover);
  }

  .private-state {
    display: grid;
    justify-items: center;
    gap: 0.625rem;
    padding: 3rem 1rem;
    color: var(--vercel-text-tertiary);
    border-block: 1px solid var(--vercel-border);
  }

  .discussion-delete {
    width: 1.75rem;
    height: 1.75rem;
  }

  .discussion-actions {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
  }

  .discussion-card {
    scroll-margin-top: 5rem;
  }

  .guild-members-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(12rem, 1fr));
  }

  @media (max-width: 30rem) {
    .guild-members-grid {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  .discussion-action {
    width: 1.75rem;
    height: 1.75rem;
  }

  .inline-error {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    color: var(--vercel-danger);
    background: color-mix(in srgb, var(--vercel-danger) 9%, transparent);
    border-left: 3px solid var(--vercel-danger);
    font-size: 0.8125rem;
  }

  .inline-error .btn {
    flex-shrink: 0;
  }

  .level-progress-track {
    height: 0.375rem;
    border-radius: 9999px;
    overflow: hidden;
  }

  .level-progress-fill {
    height: 100%;
    border-radius: inherit;
    transition: width 300ms ease;
  }

  .contributor-list {
    display: grid;
    gap: 0;
  }

  .contributor-row {
    border-color: var(--vercel-border);
  }

  .contributor-row:last-child {
    border-bottom: none;
  }

  .contributor-rank {
    font-variant-numeric: tabular-nums;
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

  @media (max-width: 40rem) {
    .guild-header :global(.inline-flex) {
      flex-wrap: wrap;
      justify-content: center;
    }

    .guild-header > :global(.flex) {
      flex-wrap: wrap;
      row-gap: 0.25rem;
    }

    .guild-tabs {
      overflow-x: auto;
      scrollbar-width: none;
    }

    .guild-tabs::-webkit-scrollbar {
      display: none;
    }

    .filter-tab {
      flex: 0 0 auto;
      white-space: nowrap;
    }

    .inline-error {
      align-items: flex-start;
      flex-direction: column;
    }
  }
</style>
