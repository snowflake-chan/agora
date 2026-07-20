<script lang="ts">
  import { onMount } from "svelte";
  import {
    getGuild, joinGuild, leaveGuild,
    getMyMembership, listMembers, listGuildPatches, listDiscussions,
    createDiscussion, deleteDiscussion,
    type Guild, type GuildMember, type GuildDiscussion,
  } from "../../lib/guilds";
  import { translator, translateError } from "../../lib/i18n";
  import type { Patch } from "../../lib/patches";
  import { currentUser, initAuth } from "../../stores/auth";
  import { timeAgo } from "../../lib/utils";
  import { LockKeyhole, Trash2 } from "@lucide/svelte";
  import ConfirmDialog from "../ConfirmDialog.svelte";
  import GuildMemberCard from "./GuildMemberCard.svelte";

  let { guildId }: { guildId: string } = $props();

  let guild = $state<Guild | null>(null);
  let members = $state<GuildMember[]>([]);
  let patches = $state<Patch[]>([]);
  let discussions = $state<GuildDiscussion[]>([]);
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

  const LEVEL_LABELS = ["", "heiker", "black客", "黑色的客人", "黑客", "Natriumchlorid"];
  const LEVEL_COLORS = ["", "#cd7f32", "#c0c0c0", "#ffd700", "#b9f2ff", "#ff4500"];

  onMount(async () => {
    await initAuth();
    await loadAll();
  });

  async function loadAll() {
    loading = true;
    loadError = null;
    try {
      const [g, m, mine, p] = await Promise.all([
        getGuild(guildId),
        listMembers(guildId),
        $currentUser ? getMyMembership(guildId) : Promise.resolve(null),
        listGuildPatches(guildId).catch(() => []),
      ]);
      guild = g;
      members = m;
      myMembership = mine;
      patches = p;
      if (isApprovedMember()) {
        const d = await listDiscussions(guildId).catch(() => []);
        discussions = d;
      }
    } catch (e: any) {
      loadError = translateError(e, $translator, "guild.loadFailed");
    } finally {
      loading = false;
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
      discussions = await listDiscussions(guildId);
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

  function isApprovedMember() {
    return Boolean(myMembership && ["approved", ""].includes(myMembership.status));
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
</script>

{#if loading}
  <div class="empty-state"><div class="spinner mb-3"></div>{$translator("guild.loading")}</div>
{:else if loadError}
  <div class="empty-state"><p style="color: var(--vercel-danger);">{loadError}</p></div>
{:else if guild}
  <header class="guild-header mb-6 text-center">
    <div class="guild-mark w-20 h-20 mx-auto flex items-center justify-center text-3xl mb-4" style="border-color: {LEVEL_COLORS[guild.level] || 'var(--vercel-border)'};">
      {guild.logo || guild.name[0].toUpperCase()}
    </div>
    <div class="inline-flex items-center gap-2 mb-1">
      <h1 class="text-2xl font-bold" style="color: var(--vercel-text);">{guild.name}</h1>
      <span class="text-xs font-bold px-2 py-0.5 rounded-full" style="background: {(LEVEL_COLORS[guild.level] || '#888')}22; color: {LEVEL_COLORS[guild.level] || '#888'}; border: 1px solid {(LEVEL_COLORS[guild.level] || '#888')}44;">
        Lv.{guild.level} {LEVEL_LABELS[guild.level] || ''}
      </span>
    </div>
    {#if guild.description}
      <p class="text-sm mt-2 max-w-md mx-auto" style="color: var(--vercel-text-secondary);">{guild.description}</p>
    {/if}
    <div class="flex items-center justify-center gap-3 mt-3 text-xs" style="color: var(--vercel-text-tertiary);">
      <span>{$translator("guild.membersCount", { count: guild.member_count })}</span>
      <span>·</span>
      <span>{$translator("guild.presidentName", { name: guild.president_username })}</span>
    </div>

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

  <div class="flex gap-1 border-b mb-4" style="border-color: var(--vercel-border);">
    <button class="filter-tab" class:active={tab === "patches"} onclick={() => tab = "patches"}>{$translator("guild.tabs.patches")}</button>
    <button class="filter-tab" class:active={tab === "members"} onclick={() => tab = "members"}>{$translator("guild.tabs.members")}</button>
    <button class="filter-tab" class:active={tab === "discussions"} onclick={() => tab = "discussions"}>{$translator("guild.tabs.discussions")}</button>
  </div>

  {#if tab === "patches"}
    {#if patches.length === 0}
      <div class="empty-state"><p>{$translator("guild.noPatches")}</p></div>
    {:else}
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {#each patches as p (p.id)}
          <a href="/patches/{p.id}" class="patch-card card p-4 block no-underline">
            <h3 class="font-semibold text-sm" style="color: var(--vercel-text);">{p.title}</h3>
            <div class="flex items-center gap-2 mt-2 text-xs" style="color: var(--vercel-text-tertiary);">
              <span>{$translator("guild.voteSummary", { for: p.for_count, against: p.against_count })}</span>
              <span>·</span>
              <span>{timeAgo(p.created_at)}</span>
            </div>
          </a>
        {/each}
      </div>
    {/if}

  {:else if tab === "members"}
    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
      {#each members as m (m.id)}
        <GuildMemberCard member={m} />
      {/each}
    </div>

  {:else}
    {#if !isApprovedMember()}
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
        {/if}
      </div>
    {:else}
      <div class="card p-4 mb-4">
        <input class="input mb-2" type="text" bind:value={discussionTitle} placeholder={$translator("guild.discussionTitlePlaceholder")} maxlength="200" />
        <textarea class="input mb-2" rows="3" bind:value={discussionContent} placeholder={$translator("guild.discussionPlaceholder")} maxlength="20000"></textarea>
        <div class="flex justify-end">
          <button class="btn btn-primary btn-sm" onclick={handlePostDiscussion} disabled={discussionSending || !discussionContent.trim()}>
            {$translator(discussionSending ? "common.sending" : "common.publish")}
          </button>
        </div>
      </div>

      {#if discussions.length === 0}
        <div class="empty-state"><p>{$translator("guild.noDiscussions")}</p></div>
      {:else}
        {#each discussions as d (d.id)}
          <div class="card p-4 mb-2">
            <div class="flex items-center justify-between mb-1">
              <div class="flex items-center gap-2 text-xs" style="color: var(--vercel-text-tertiary);">
                <a href="/users/{d.author_id}" class="font-medium no-underline" style="color: var(--vercel-text-secondary);">{d.author_username}</a>
                <span>·</span>
                <span>{timeAgo(d.created_at)}</span>
              </div>
              {#if $currentUser?.id === d.author_id}
                <button
                  class="btn-icon discussion-delete"
                  title={$translator("common.delete")}
                  aria-label={$translator("common.delete")}
                  onclick={() => requestConfirmation(
                    $translator("guild.deleteDiscussionTitle"),
                    $translator("guild.deleteDiscussionDescription"),
                    () => handleDeletePost(d.id),
                  )}
                ><Trash2 size={15} /></button>
              {/if}
            </div>
            {#if d.title}
              <h4 class="font-semibold text-sm mb-1" style="color: var(--vercel-text);">{d.title}</h4>
            {/if}
            <p class="text-sm" style="color: var(--vercel-text-secondary);">{d.content}</p>
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
</style>
