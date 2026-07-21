<script lang="ts">
  import { HeartIcon, MessageCircleIcon } from "@lucide/svelte";
  import type { Post } from "../../lib/posts";
  import type { DisplayTranslation } from "../../lib/ai";
  import { translator } from "../../lib/i18n";
  import { stripMarkdown } from "../../lib/utils";
  import AuthorMeta from "../AuthorMeta.svelte";
  import PollCard from "./PollCard.svelte";
  import ModerationNotice from "./ModerationNotice.svelte";
  import PostAiTools from "./PostAiTools.svelte";
  import { hasModerationNotice, isModerationRestricted } from "../../lib/moderation";

  let { post }: { post: Post } = $props();

  let displayTranslation = $state<DisplayTranslation | null>(null);
  let displayTitle = $derived(displayTranslation?.title ?? post.title);
  let snippet = $derived(stripMarkdown(displayTranslation?.body ?? post.content));
  let moderationQueued = $state(false);
  let effectiveModerationStatus = $derived(
    moderationQueued ? "pending_review" : post.moderation_status,
  );
  let moderationRestricted = $derived(isModerationRestricted(effectiveModerationStatus));
  let moderationVisible = $derived(hasModerationNotice(effectiveModerationStatus));

  $effect(() => {
    post.id;
    post.revision_number;
    displayTranslation = null;
  });

  $effect(() => {
    const nextStatus = post.moderation_status;
    if (nextStatus !== "published") moderationQueued = false;
  });
</script>

<article
  class="post-card relative px-4 py-4 border-b"
  style="border-color: var(--vercel-border);"
>
  {#if moderationVisible}
    <div class="post-card-topline">
      <ModerationNotice
        status={effectiveModerationStatus}
        reason={moderationQueued ? null : post.moderation_reason}
        compact
      />
    </div>
  {/if}
  <h2 class="text-base font-semibold">
    <a class="card-link" href={`/posts/${post.id}`} style="color: var(--vercel-text);">
      {displayTitle}
    </a>
  </h2>

  <p class="mt-1 line-clamp-2 text-sm" style="color: var(--vercel-text-secondary);">
    {snippet}
  </p>

  {#if !moderationRestricted}
    <div class="post-card-translation">
      <PostAiTools
        text={post.content}
        title={post.title}
        context="post"
        compact
        translationOnly
        sourceContentId={post.id}
        sourceRevisionNumber={post.revision_number}
        moderationTargetHref={`/posts/${post.id}`}
        onModerationQueued={() => (moderationQueued = true)}
        onTranslationChange={(translation) => (displayTranslation = translation)}
      />
    </div>
  {/if}

  {#if post.poll}
    <PollCard
      postId={post.id}
      poll={post.poll}
      compact
      readOnly={moderationRestricted}
      sourceRevisionNumber={post.revision_number}
      moderationTargetHref={`/posts/${post.id}`}
      onModerationQueued={() => (moderationQueued = true)}
      translationRequested={displayTranslation !== null}
    />
  {/if}

  <div class="mt-2 flex items-center justify-between gap-2">
    <div class="flex items-center gap-3 text-xs" style="color: var(--vercel-text-tertiary);">
      {#if post.tags && post.tags.length > 0 && !moderationRestricted}
        <span>{post.tags.join(", ")}</span>
      {/if}
      {#if !moderationRestricted}
        <span class="flex items-center gap-1">
          <HeartIcon size={14} strokeWidth={1.8} aria-hidden="true" />
          {post.like_count}
        </span>
        <span class="flex items-center gap-1">
          <MessageCircleIcon size={14} strokeWidth={1.8} aria-hidden="true" />
          {post.reply_count}
        </span>
      {/if}
    </div>

    <AuthorMeta username={post.author_username ?? $translator("common.anonymous")} userId={post.author_id} createdAt={post.created_at} />
  </div>
</article>

<style>
  .card-link::after {
    content: "";
    position: absolute;
    inset: 0;
  }

  .post-card-topline {
    position: relative;
    z-index: 1;
    margin-bottom: 0.45rem;
  }

  .post-card-translation {
    position: relative;
    z-index: 1;
  }

  .post-card {
    transition: background-color 150ms ease, border-color 150ms ease;
  }

  .post-card:hover {
    background: var(--vercel-hover);
  }

  .post-card:has(.card-link:focus-visible) {
    outline: 2px solid var(--vercel-text);
    outline-offset: -2px;
  }

  .card-link:focus-visible {
    outline: none;
  }
</style>
