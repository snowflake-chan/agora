<script lang="ts">
  import { onMount } from "svelte";
  import { getUser, getUserPosts, getUserPatches, type UserPublic } from "../../lib/auth";
  import type { Post } from "../../lib/posts";
  import type { Patch } from "../../lib/patches";
  import { timeAgo } from "../../lib/utils";

  let { userId }: { userId: string } = $props();

  let user = $state<UserPublic | null>(null);
  let posts = $state<Post[]>([]);
  let patches = $state<Patch[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let tab = $state<"posts" | "patches">("posts");

  onMount(async () => {
    try {
      const [u, p, pt] = await Promise.all([
        getUser(userId),
        getUserPosts(userId),
        getUserPatches(userId),
      ]);
      user = u;
      posts = p;
      patches = pt;
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load user";
    } finally {
      loading = false;
    }
  });
</script>

{#if loading}
  <div class="empty-state">
    <div class="spinner mb-3"></div>
    加载中...
  </div>
{:else if error}
  <div class="empty-state">
    <p style="color: var(--vercel-danger);">{error}</p>
  </div>
{:else if user}
  <!-- Profile header -->
  <div class="card p-6 mb-6">
    <div class="flex items-center gap-4">
      <div class="avatar" style="width: 3.5rem; height: 3.5rem; font-size: 1.5rem;">
        {(user.nickname ?? user.username)[0].toUpperCase()}
      </div>
      <div class="min-w-0">
        <h1 class="text-xl font-bold" style="color: var(--vercel-text);">
          {user.nickname ?? user.username}
        </h1>
        <p class="text-sm" style="color: var(--vercel-text-tertiary);">
          @{user.username}
        </p>
        {#if user.bio}
          <p class="mt-2 text-sm leading-relaxed" style="color: var(--vercel-text-secondary);">
            {user.bio}
          </p>
        {/if}
      </div>
    </div>
  </div>

  <!-- Tab switcher -->
  <div class="flex gap-1 mb-4 border-b" style="border-color: var(--vercel-border);">
    <button
      class="filter-tab"
      class:active={tab === "posts"}
      onclick={() => tab = "posts"}
    >
      发布的帖子 ({posts.length})
    </button>
    <button
      class="filter-tab"
      class:active={tab === "patches"}
      onclick={() => tab = "patches"}
    >
      提交的变更 ({patches.length})
    </button>
  </div>

  <!-- Content -->
  {#if tab === "posts"}
    {#if posts.length === 0}
      <div class="empty-state">
        <p>暂无发布的帖子</p>
      </div>
    {:else}
      <div class="card overflow-hidden">
        {#each posts as post (post.id)}
          <a
            href={`/posts/${post.id}`}
            class="block px-4 py-3 border-b transition-colors"
            style="border-color: var(--vercel-border);"
            onmouseenter={(e) => e.currentTarget.style.background = '#141417'}
            onmouseleave={(e) => e.currentTarget.style.background = ''}
          >
            <h3 class="text-sm font-semibold" style="color: var(--vercel-text);">{post.title}</h3>
            <div class="mt-1 flex items-center gap-3 text-xs" style="color: var(--vercel-text-tertiary);">
              <span class="flex items-center gap-1">
                <svg class="size-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
                {post.reply_count}
              </span>
              <span>{timeAgo(post.created_at)}</span>
            </div>
          </a>
        {/each}
      </div>
    {/if}
  {:else}
    {#if patches.length === 0}
      <div class="empty-state">
        <p>暂无提交的变更</p>
      </div>
    {:else}
      <div class="card overflow-hidden">
        {#each patches as patch (patch.id)}
          <a
            href={`/patches/${patch.id}`}
            class="block px-4 py-3 border-b transition-colors"
            style="border-color: var(--vercel-border);"
            onmouseenter={(e) => e.currentTarget.style.background = '#141417'}
            onmouseleave={(e) => e.currentTarget.style.background = ''}
          >
            <h3 class="text-sm font-semibold" style="color: var(--vercel-text);">{patch.title}</h3>
            <div class="mt-1 flex items-center gap-3 text-xs" style="color: var(--vercel-text-tertiary);">
              <span>#{patch.pr_number}</span>
              <span>{timeAgo(patch.created_at)}</span>
            </div>
          </a>
        {/each}
      </div>
    {/if}
  {/if}
{/if}
