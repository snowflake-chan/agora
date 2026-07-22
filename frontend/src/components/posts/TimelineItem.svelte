<script lang="ts">
  import {
    EllipsisIcon,
    FlagIcon,
    HeartIcon,
    HistoryIcon,
    MessageCircleIcon,
    PencilIcon,
    ReplyIcon,
    Share2Icon,
    Trash2Icon,
  } from "@lucide/svelte";
  import { onMount } from "svelte";
  import { getUserGuild, type UserGuildBadge } from "../../lib/guilds";
  import type { DisplayTranslation, TranslationContext } from "../../lib/ai";
  import { translator } from "../../lib/i18n";
  import { renderMarkdown } from "../../lib/markdown";
  import { isModerationRestricted, type ModerationStatus } from "../../lib/moderation";
  import type { Poll } from "../../lib/posts";
  import { avatarInitial, displayName } from "../../lib/utils";
  import RelativeTime from "../RelativeTime.svelte";
  import PollCard from "./PollCard.svelte";
  import PostAiTools from "./PostAiTools.svelte";
  import ModerationNotice from "./ModerationNotice.svelte";

  let {
    username,
    userId = null,
    createdAt,
    content,
    title = null,
    tags = null,
    replyingToUsername = null,
    onReply = null,
    onDelete = null,
    onEdit = null,
    onHistory = null,
    onReport = null,
    liked = false,
    likeCount = null,
    replyCount = null,
    liking = false,
    onLike = null,
    onDiscuss = null,
    onShare = null,
    contentId = null,
    replyingToContent = null,
    replyingToId = null,
    poll = null,
    onPollUpdate = null,
    aiText = null,
    aiTitle = null,
    aiContext = "comment",
    moderationStatus = null,
    moderationReason = null,
    moderationReviewNote = null,
    revisionNumber = 1,
    moderationTargetHref = null,
    onTranslationChange = null,
  }: {
    username: string;
    userId: string | null;
    createdAt: string;
    content: string;
    title: string | null;
    tags: string[] | null;
    replyingToUsername: string | null;
    onReply: (() => void) | null;
    onDelete: (() => void) | null;
    onEdit?: (() => void) | null;
    onHistory?: (() => void) | null;
    onReport?: (() => void) | null;
    liked?: boolean;
    likeCount?: number | null;
    replyCount?: number | null;
    liking?: boolean;
    onLike?: (() => void) | null;
    onDiscuss?: (() => void) | null;
    onShare?: (() => void) | null;
    contentId?: string | null;
    replyingToContent?: string | null;
    replyingToId?: string | null;
    poll?: Poll | null;
    onPollUpdate?: ((poll: Poll) => void) | null;
    aiText?: string | null;
    aiTitle?: string | null;
    aiContext?: TranslationContext;
    moderationStatus?: ModerationStatus | null;
    moderationReason?: string | null;
    moderationReviewNote?: string | null;
    revisionNumber?: number;
    moderationTargetHref?: string | null;
    onTranslationChange?: ((translation: DisplayTranslation | null) => void) | null;
  } = $props();

  let menuOpen = $state(false);
  let menuButton = $state<HTMLButtonElement | null>(null);
  let guild = $state<UserGuildBadge | null>(null);
  let moderationQueued = $state(false);
  let displayTranslation = $state<DisplayTranslation | null>(null);
  let displayedContent = $derived(displayTranslation?.body ?? content);
  let profileHref = $derived(userId ? `/users/${userId}` : "#");
  let menuId = $derived(
    `timeline-actions-${(contentId ?? `${userId ?? "anonymous"}-${createdAt}`).replace(/[^a-zA-Z0-9_-]/g, "-")}`,
  );
  let effectiveModerationStatus = $derived(
    moderationQueued ? "pending_review" : moderationStatus,
  );
  let moderationRestricted = $derived(isModerationRestricted(effectiveModerationStatus));

  $effect(() => {
    content;
    title;
    revisionNumber;
    displayTranslation = null;
    onTranslationChange?.(null);
  });

  $effect(() => {
    const nextStatus = moderationStatus;
    if (nextStatus !== "published") moderationQueued = false;
  });

  onMount(async () => {
    if (!userId) return;
    try {
      guild = await getUserGuild(userId);
    } catch {
      guild = null;
    }
  });

  function handleClickOutside(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest(".timeline-menu")) {
      menuOpen = false;
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (!menuOpen || event.key !== "Escape") return;
    event.preventDefault();
    menuOpen = false;
    menuButton?.focus();
  }

  function runMenuAction(action: () => void) {
    menuOpen = false;
    action();
  }

  function handleTranslationChange(translation: DisplayTranslation | null) {
    displayTranslation = translation;
    onTranslationChange?.(translation);
  }
</script>

<svelte:window onclick={handleClickOutside} onkeydown={handleKeydown} />

<div id={contentId ?? undefined} class="relative mb-6 ml-7 content-node">
  <div class="card">
    <!-- Header -->
    <div class="timeline-header px-4 py-2 border-b" style="border-color: var(--vercel-border);">
      {#if userId}
        <a href={profileHref} class="avatar avatar-sm no-underline hover:opacity-80 transition-opacity">
          {avatarInitial(username)}
        </a>
      {:else}
        <span class="avatar avatar-sm" aria-hidden="true">
          {avatarInitial(username)}
        </span>
      {/if}
      <div class="timeline-identity">
        {#if userId}
          <a href={profileHref} class="timeline-author text-sm font-medium no-underline hover:underline">{displayName(username, $translator("common.anonymous"))}</a>
        {:else}
          <span class="timeline-author text-sm font-medium">{displayName(username, $translator("common.anonymous"))}</span>
        {/if}
        {#if guild}
          <a class="timeline-guild" href={`/guilds/${guild.guild_id}`}>
            Lv.{guild.guild_level} {guild.guild_name}
          </a>
        {/if}
        <RelativeTime value={createdAt} className="timeline-time text-xs" />
        {#if revisionNumber > 1}
          <button
            type="button"
            class="edited-marker"
            onclick={onHistory ?? undefined}
            disabled={!onHistory}
            title={$translator("revision.viewHistory")}
          >
            {$translator("revision.edited")}
          </button>
        {/if}
      </div>

      {#if onDelete || onEdit || onHistory || (!moderationRestricted && (onReply || onReport))}
        <div class="timeline-menu relative">
          <button
            bind:this={menuButton}
            type="button"
            class="btn-icon timeline-menu-trigger"
            onclick={(event) => {
              event.stopPropagation();
              menuOpen = !menuOpen;
            }}
            aria-label={$translator("common.moreActions")}
            aria-expanded={menuOpen}
            aria-controls={menuOpen ? menuId : undefined}
            title={$translator("common.moreActions")}
          >
            <EllipsisIcon size={17} strokeWidth={2} aria-hidden="true" />
          </button>

          {#if menuOpen}
            <div
              id={menuId}
              class="menu-dropdown timeline-menu-dropdown absolute right-0 top-full mt-1"
              aria-label={$translator("common.moreActions")}
            >
              {#if onReply && !moderationRestricted}
                <button type="button" class="menu-item" onclick={() => runMenuAction(onReply)}>
                  <ReplyIcon size={15} strokeWidth={1.8} aria-hidden="true" />
                  <span>{$translator("common.reply")}</span>
                </button>
              {/if}
              {#if onEdit}
                <button type="button" class="menu-item" onclick={() => runMenuAction(onEdit)}>
                  <PencilIcon size={15} strokeWidth={1.8} aria-hidden="true" />
                  <span>{$translator("common.edit")}</span>
                </button>
              {/if}
              {#if onHistory}
                <button type="button" class="menu-item" onclick={() => runMenuAction(onHistory)}>
                  <HistoryIcon size={15} strokeWidth={1.8} aria-hidden="true" />
                  <span>{$translator("revision.viewHistory")}</span>
                </button>
              {/if}
              {#if onReport && !moderationRestricted}
                <button type="button" class="menu-item" onclick={() => runMenuAction(onReport)}>
                  <FlagIcon size={15} strokeWidth={1.8} aria-hidden="true" />
                  <span>{$translator("common.report")}</span>
                </button>
              {/if}
              {#if onDelete}
                <button type="button" class="menu-item menu-item-danger" onclick={() => runMenuAction(onDelete)}>
                  <Trash2Icon size={15} strokeWidth={1.8} aria-hidden="true" />
                  <span>{$translator("common.delete")}</span>
                </button>
              {/if}
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Body -->
    <div class="px-4 py-3 text-sm" style="color: var(--vercel-text-secondary);">
      <ModerationNotice
        status={effectiveModerationStatus}
        reason={moderationQueued ? null : moderationReason}
        reviewNote={moderationReviewNote}
      />
      {#if replyingToUsername}
        <a href={replyingToId ? `#${replyingToId}` : undefined} class="reply-trace">
          <span>{$translator("common.replyingTo", { name: replyingToUsername })}</span>
          {#if replyingToContent}
            <span class="reply-trace-copy">{replyingToContent}</span>
          {/if}
        </a>
      {/if}
      <div class="markdown-body">
        {@html renderMarkdown(displayedContent)}
      </div>
      {#if tags && tags.length > 0}
        <div class="mt-3 flex flex-wrap gap-2">
          {#each tags as tag}
            <span class="badge badge-neutral">{tag}</span>
          {/each}
        </div>
      {/if}
      {#if poll && contentId}
        <PollCard
          postId={contentId}
          {poll}
          onUpdate={onPollUpdate}
          readOnly={moderationRestricted}
          sourceRevisionNumber={revisionNumber}
          {moderationTargetHref}
          onModerationQueued={() => (moderationQueued = true)}
          translationRequested={displayTranslation !== null}
        />
      {/if}
      {#if aiText && !moderationRestricted}
        <PostAiTools
          text={aiText}
          title={aiTitle}
          context={aiContext}
          compact={title === null}
          sourceContentId={contentId}
          sourceRevisionNumber={revisionNumber}
          {moderationTargetHref}
          onModerationQueued={() => (moderationQueued = true)}
          onTranslationChange={handleTranslationChange}
        />
      {/if}
    </div>

    {#if likeCount !== null && replyCount !== null && !moderationRestricted}
      <div class="post-actions" aria-label={$translator("post.actions")}>
        <button
          type="button"
          class:active={liked}
          class="post-action"
          aria-pressed={liked}
          aria-label={$translator(liked ? "common.unlike" : "common.like")}
          disabled={liking}
          onclick={onLike}
        >
          <HeartIcon size={16} strokeWidth={1.8} fill={liked ? "currentColor" : "none"} aria-hidden="true" />
          <span>{$translator("common.like")}</span>
          {#if likeCount > 0}<span class="action-count">{likeCount}</span>{/if}
        </button>
        <button type="button" class="post-action" onclick={onDiscuss}>
          <MessageCircleIcon size={16} strokeWidth={1.8} aria-hidden="true" />
          <span>{$translator("common.reply")}</span>
          {#if replyCount > 0}<span class="action-count">{replyCount}</span>{/if}
        </button>
        <button type="button" class="post-action" onclick={onShare}>
          <Share2Icon size={16} strokeWidth={1.8} aria-hidden="true" />
          <span>{$translator("common.share")}</span>
        </button>
      </div>
    {/if}
  </div>
</div>

<style>
  .timeline-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .timeline-identity {
    display: flex;
    min-width: 0;
    flex: 1;
    align-items: center;
    gap: 0.45rem;
  }

  .timeline-author {
    overflow: hidden;
    min-width: 0;
    color: var(--vercel-text);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  :global(.timeline-time) {
    flex: 0 0 auto;
    color: var(--vercel-text-tertiary);
    white-space: nowrap;
  }

  .edited-marker {
    flex: 0 0 auto;
    padding: 0;
    border: 0;
    color: var(--vercel-text-tertiary);
    background: transparent;
    font-size: 0.68rem;
    text-decoration: underline;
    text-decoration-color: transparent;
    text-underline-offset: 0.16rem;
  }

  .edited-marker:not(:disabled) {
    cursor: pointer;
  }

  .edited-marker:not(:disabled):hover {
    color: var(--vercel-text-secondary);
    text-decoration-color: currentColor;
  }

  .timeline-menu-trigger {
    width: 2rem;
    height: 2rem;
    color: var(--vercel-text-tertiary);
  }

  .timeline-menu-dropdown {
    z-index: var(--z-dropdown);
    min-width: 9.5rem;
  }

  .timeline-menu-dropdown :global(.menu-item) {
    min-height: 2.25rem;
    gap: 0.625rem;
  }

  .timeline-menu-dropdown :global(svg) {
    flex: 0 0 auto;
  }

  .timeline-guild {
    overflow: hidden;
    max-width: 8rem;
    padding: 0.05rem 0.35rem;
    border: 1px solid color-mix(in srgb, var(--vercel-warning) 28%, transparent);
    border-radius: 999px;
    color: var(--vercel-warning);
    background: color-mix(in srgb, var(--vercel-warning) 10%, transparent);
    font-size: 0.56rem;
    font-weight: 700;
    line-height: 1.5;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .post-actions {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    border-top: 1px solid var(--vercel-border);
    padding: 0.25rem;
  }

  .content-node {
    scroll-margin-top: 5rem;
    container-type: inline-size;
  }

  .reply-trace {
    display: block;
    margin-bottom: 0.75rem;
    padding-left: 0.75rem;
    border-left: 2px solid var(--vercel-border-hover);
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
    line-height: 1.45;
  }

  .reply-trace:hover {
    color: var(--vercel-text-secondary);
  }

  .reply-trace-copy {
    display: -webkit-box;
    overflow: hidden;
    margin-top: 0.2rem;
    color: var(--vercel-text-secondary);
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }

  .post-action {
    display: inline-flex;
    min-width: 0;
    min-height: 2.5rem;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    border-radius: 0.375rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.8125rem;
    font-weight: 500;
    transition: color 150ms ease, background 150ms ease;
  }

  .post-action:hover:not(:disabled) {
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .post-action:focus-visible {
    outline: 2px solid var(--vercel-text-secondary);
    outline-offset: -2px;
  }

  .post-action:disabled {
    cursor: wait;
    opacity: 0.55;
  }

  .post-action.active {
    color: var(--vercel-danger);
  }

  .post-action svg {
    width: 1rem;
    height: 1rem;
  }

  .action-count {
    font-variant-numeric: tabular-nums;
  }

  @container (max-width: 22rem) {
    .post-action > span:not(.action-count) {
      display: none;
    }

    .post-action {
      gap: 0.25rem;
    }
  }

  @media (max-width: 30rem) {
    .timeline-identity {
      flex-wrap: wrap;
      row-gap: 0.1rem;
    }

    .timeline-time {
      width: 100%;
    }
  }
</style>
