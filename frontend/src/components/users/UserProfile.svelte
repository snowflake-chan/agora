<script lang="ts">
  import { PenLineIcon } from "@lucide/svelte";
  import { onMount } from "svelte";
  import { translator } from "../../lib/i18n";
  import { requestLogin } from "../../lib/login";
  import {
    followUser,
    getUser,
    getUserContent,
    unfollowUser,
    type UserContentItem,
    type UserPublic,
  } from "../../lib/auth";
  import { deleteContent } from "../../lib/posts";
  import { deletePatch } from "../../lib/patches";
  import { avatarInitial, displayName, stripMarkdown } from "../../lib/utils";
  import { currentUser } from "../../stores/auth";
  import { toaster } from "../../stores/toaster";
  import ConfirmDialog from "../ConfirmDialog.svelte";
  import VotingWindowMeta from "../patches/VotingWindowMeta.svelte";
  import ModerationNotice from "../posts/ModerationNotice.svelte";
  import RelativeTime from "../RelativeTime.svelte";
  import {
    hasModerationNotice,
    isModerationRestricted,
    onModerationUpdate,
  } from "../../lib/moderation";

  let { userId }: { userId: string } = $props();

  let user = $state<UserPublic | null>(null);
  let items = $state<UserContentItem[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let followingBusy = $state(false);
  let filter = $state<"all" | "post" | "comment" | "patch">("all");
  let pendingDelete = $state<UserContentItem | null>(null);
  let showDeleteDialog = $state(false);
  const filters = [
    { value: "all", key: "common.all" },
    { value: "post", key: "common.posts" },
    { value: "comment", key: "common.comment" },
    { value: "patch", key: "common.changes" },
  ] as const;

  let visibleItems = $derived(
    filter === "all" ? items : items.filter((item) => item.type === filter)
  );

  async function loadProfile(showError = true) {
    try {
      [user, items] = await Promise.all([
        getUser(userId),
        getUserContent(userId),
      ]);
    } catch {
      if (showError) error = "PROFILE_LOAD_FAILED";
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    void loadProfile();
    return onModerationUpdate(() => {
      if ($currentUser?.id === userId) void loadProfile(false);
    });
  });

  async function toggleFollow() {
    if (!user) return;
    if (!$currentUser) {
      requestLogin(window.location.pathname, toggleFollow);
      return;
    }
    followingBusy = true;
    try {
      const state = user.is_following
        ? await unfollowUser(user.id)
        : await followUser(user.id);
      user = { ...user, ...state };
    } catch (e: any) {
      toaster.error($translator("profile.followFailed"), $translator("common.tryAgain"));
    } finally {
      followingBusy = false;
    }
  }

  function itemHref(item: UserContentItem): string {
    if (item.type === "post") return `/posts/${item.id}`;
    if (item.type === "patch") return `/patches/${item.id}`;
    if (!item.root_id || !item.root_type) return "#";
    const base = item.root_type === "post" ? "posts" : "patches";
    return `/${base}/${item.root_id}#${item.id}`;
  }

  function requestDelete(item: UserContentItem) {
    pendingDelete = item;
    showDeleteDialog = true;
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    try {
      if (pendingDelete.type === "patch") await deletePatch(pendingDelete.id);
      else await deleteContent(pendingDelete.id);
      items = items.filter((item) => item.id !== pendingDelete?.id);
      toaster.success($translator("profile.contentDeleted"));
    } catch (e: any) {
      toaster.error($translator("profile.deleteFailed"), $translator("common.tryAgain"));
    } finally {
      pendingDelete = null;
    }
  }
</script>

{#if loading}
  <div class="profile-skeleton" aria-label={$translator("profile.loading")}>
    <div></div><div></div><div></div>
  </div>
{:else if error}
  <div class="empty-state"><p style="color: var(--vercel-danger);">{$translator("profile.loadFailed")}</p></div>
{:else if user}
  <header class="profile-header">
    <div class="profile-identity">
      <div class="profile-avatar">{avatarInitial(user.nickname, user.username)}</div>
      <div class="min-w-0">
        <p class="profile-kicker">{$translator("profile.kicker")}</p>
        <h1>{displayName(user.nickname, user.username)}</h1>
        <p class="profile-handle">@{user.username}</p>
      </div>
    </div>

    {#if $currentUser?.id === user.id}
      <a class="btn btn-secondary btn-sm edit-profile-button" href="/my">
        <PenLineIcon size={14} strokeWidth={1.8} />
        {$translator("profile.edit")}
      </a>
    {:else}
      <button
        class:following={user.is_following}
        class:btn-primary={!user.is_following}
        class:btn-secondary={user.is_following}
        class="btn btn-sm follow-button"
        disabled={followingBusy}
        onclick={toggleFollow}
      >
        {followingBusy ? $translator("common.processing") : $translator(user.is_following ? "profile.following" : "profile.follow")}
      </button>
    {/if}

    {#if user.bio}<p class="profile-bio">{user.bio}</p>{/if}

    <div class="profile-stats">
      <span>{$translator("profile.followers", { count: user.follower_count })}</span>
      <span>{$translator("profile.followingCount", { count: user.following_count })}</span>
      <span>{$translator("profile.activityCount", { count: items.length })}</span>
    </div>
  </header>

  <nav class="content-filters" aria-label={$translator("profile.filters")}>
    {#each filters as option}
      <button
        class:active={filter === option.value}
        onclick={() => (filter = option.value)}
      >
        {$translator(option.key)}
      </button>
    {/each}
  </nav>

  <section class="profile-stream" aria-label={$translator("profile.userContent")}>
    {#if visibleItems.length === 0}
      <div class="empty-state">{$translator("profile.empty")}</div>
    {:else}
      {#each visibleItems as item (item.id)}
        {@const moderationRestricted = isModerationRestricted(item.moderation_status)}
        {@const moderationVisible = hasModerationNotice(item.moderation_status)}
        <article class="profile-item">
          <div class="item-rail">
            <span>{$translator(item.type === "post" ? "common.post" : item.type === "patch" ? "common.change" : "common.comment")}</span>
            <RelativeTime value={item.created_at} />
          </div>

          {#if moderationVisible}
            <div class="item-status">
              <ModerationNotice
                status={item.moderation_status}
                reason={item.moderation_reason}
                reviewNote={item.moderation_review_note}
                compact
              />
            </div>
          {/if}

          {#if item.type === "comment" && item.root_id && !moderationRestricted}
            <a class="context-root" href={itemHref(item)}>
              <span>{$translator("profile.repliedTo")}</span>
              <strong>{item.root_title ?? $translator(item.root_type === "post" ? "common.post" : "common.change")}</strong>
            </a>
          {/if}

          {#if item.replying_to_username && !moderationRestricted}
            <a class="context-reply" href={itemHref(item)}>
              <span>↳ @{item.replying_to_username}</span>
              {#if item.replying_to_content}
                <span>{stripMarkdown(item.replying_to_content)}</span>
              {/if}
            </a>
          {/if}

          <a
            class="item-main"
            class:private-item={moderationRestricted}
            href={itemHref(item)}
          >
            {#if item.title}<h2>{item.title}</h2>{/if}
            <p>{stripMarkdown(item.content)}</p>
          </a>

          <footer class="item-footer">
            {#if !moderationRestricted}
              <div class="item-counts">
                {#if item.type !== "patch"}<span>♡ {item.like_count}</span>{/if}
                <a href={itemHref(item)}>↳ {item.reply_count}</a>
                {#if item.pr_number}<span>PR #{item.pr_number}</span>{/if}
                {#if item.status}<span>{$translator(`status.${item.status}`)}</span>{/if}
                {#if item.type === "patch"}
                  <VotingWindowMeta
                    status={item.status}
                    votingWindowKind={item.voting_window_kind}
                    votingPeriodHours={item.voting_period_hours}
                    votingStartedAt={item.voting_started_at}
                    votingEndsAt={item.voting_ends_at}
                  />
                {/if}
              </div>
            {:else}
              <span></span>
            {/if}
            {#if item.can_delete}
              <button class="delete-item" onclick={() => requestDelete(item)}>{$translator("common.delete")}</button>
            {/if}
          </footer>
        </article>
      {/each}
    {/if}
  </section>
{/if}

<ConfirmDialog
  bind:open={showDeleteDialog}
  title={$translator("profile.deleteContentTitle")}
  description={$translator("profile.deleteContentDescription")}
  confirmText={$translator("common.delete")}
  onConfirm={confirmDelete}
/>

<style>
  .profile-header {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 1rem 2rem;
    padding: 1.5rem 0 1.75rem;
    border-bottom: 1px solid var(--vercel-border);
  }
  .profile-identity { display: flex; align-items: center; gap: 1rem; }
  .profile-avatar {
    display: grid; width: 3.75rem; height: 3.75rem; place-items: center;
    border: 1px solid var(--vercel-border-hover); border-radius: 1rem;
    background: var(--vercel-surface-muted); color: var(--vercel-text);
    font-size: 1.25rem; font-weight: 650;
  }
  .profile-kicker {
    color: var(--vercel-text-tertiary); font-size: .625rem; font-weight: 650;
    letter-spacing: .14em; text-transform: uppercase;
  }
  .profile-header h1 { font-size: 1.5rem; font-weight: 650; letter-spacing: 0; }
  .profile-handle { color: var(--vercel-text-tertiary); font-size: .8rem; }
  .profile-bio {
    grid-column: 1 / -1; max-width: 42rem; color: var(--vercel-text-secondary);
    font-size: .875rem; line-height: 1.65;
  }
  .profile-stats {
    display: flex; grid-column: 1 / -1; gap: 1.25rem;
    color: var(--vercel-text-tertiary); font-size: .75rem;
  }
  .profile-stats strong { color: var(--vercel-text); font-variant-numeric: tabular-nums; }
  .follow-button {
    align-self: center; min-width: 5.5rem;
  }
  .follow-button.following {
    background: transparent;
    color: var(--vercel-text-secondary);
    border-color: var(--vercel-border-hover);
  }
  .edit-profile-button {
    align-self: center;
    min-width: 5.5rem;
  }
  .content-filters {
    display: flex; gap: 1.25rem; overflow-x: auto;
    border-bottom: 1px solid var(--vercel-border);
  }
  .content-filters button {
    position: relative; padding: .9rem 0; color: var(--vercel-text-tertiary);
    font-size: .78rem; white-space: nowrap;
  }
  .content-filters button.active { color: var(--vercel-text); }
  .content-filters button.active::after {
    position: absolute; right: 0; bottom: -1px; left: 0; height: 2px;
    background: var(--vercel-text); content: "";
  }
  .profile-stream { border-bottom: 1px solid var(--vercel-border); }
  .profile-item {
    display: grid; grid-template-columns: 4.5rem minmax(0, 1fr);
    gap: .25rem 1rem; padding: 1.25rem 0;
    border-bottom: 1px solid var(--vercel-border);
  }
  .profile-item:last-child { border-bottom: 0; }
  .item-rail {
    display: flex; grid-row: 1 / span 4; flex-direction: column; gap: .3rem;
    color: var(--vercel-text-tertiary); font-size: .65rem;
  }
  .item-rail span { font-weight: 650; letter-spacing: .1em; }
  .context-root, .context-reply {
    display: flex; min-width: 0; gap: .4rem; color: var(--vercel-text-tertiary);
    font-size: .7rem;
  }
  .item-status { margin-bottom: .25rem; }
  .context-root strong { overflow: hidden; color: var(--vercel-text-secondary); text-overflow: ellipsis; white-space: nowrap; }
  .context-reply {
    flex-direction: column; padding: .5rem .65rem; border-left: 2px solid var(--vercel-border-hover);
    background: var(--vercel-surface-muted); line-height: 1.45;
  }
  .context-reply span:last-child {
    display: -webkit-box; overflow: hidden; color: var(--vercel-text-secondary);
    -webkit-box-orient: vertical; -webkit-line-clamp: 2;
  }
  .item-main h2 { margin-bottom: .35rem; color: var(--vercel-text); font-size: 1rem; font-weight: 620; }
  .item-main p {
    display: -webkit-box; overflow: hidden; max-width: 65ch;
    color: var(--vercel-text-secondary); font-size: .83rem; line-height: 1.55;
    -webkit-box-orient: vertical; -webkit-line-clamp: 3;
  }
  .item-footer { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-top: .5rem; }
  .item-counts {
    display: flex; flex-wrap: wrap; align-items: center; gap: .5rem 1rem;
    color: var(--vercel-text-tertiary); font-size: .7rem;
  }
  .delete-item { color: var(--vercel-text-tertiary); font-size: .7rem; }
  .delete-item:hover { color: var(--vercel-danger); }
  .profile-skeleton { display: grid; gap: .75rem; padding: 2rem 0; }
  .profile-skeleton div { height: 5rem; border-radius: .5rem; background: var(--vercel-surface-muted); animation: pulse 1.2s ease-in-out infinite alternate; }
  @keyframes pulse { to { opacity: .45; } }
  @media (max-width: 36rem) {
    .profile-header { grid-template-columns: 1fr; }
    .follow-button, .edit-profile-button { justify-self: start; }
    .profile-item { grid-template-columns: 1fr; }
    .item-rail { grid-row: auto; flex-direction: row; justify-content: space-between; }
  }
</style>
