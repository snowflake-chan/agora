<script lang="ts">
  import { onMount } from "svelte";
  import { timeAgo } from "../lib/utils";
  import { getUserGuild, type UserGuildBadge } from "../lib/guilds";

  let { username, userId, createdAt }: { username: string; userId?: string; createdAt: string } = $props();

  let profileHref = $derived(userId ? `/users/${userId}` : "#");
  let badge = $state<UserGuildBadge | null>(null);

  // Simple in-memory cache per user so repeated renders don't re-fetch
  const _cache: Record<string, UserGuildBadge | null> = {};

  onMount(async () => {
    if (!userId) return;
    if (userId in _cache) { badge = _cache[userId]; return; }
    try {
      badge = await getUserGuild(userId);
      _cache[userId] = badge;
    } catch {
      _cache[userId] = null;
    }
  });
</script>

<div class="relative z-10 flex shrink-0 items-center gap-1.5 text-xs" style="color: var(--vercel-text-tertiary);">
  <a href={profileHref} class="avatar avatar-sm no-underline hover:opacity-80 transition-opacity" style="cursor: {userId ? 'pointer' : 'default'};">
    {(username ?? "?")[0].toUpperCase()}
  </a>
  <div class="flex items-center gap-1">
    <a href={profileHref} class="no-underline hover:underline" style="color: var(--vercel-text-secondary); cursor: {userId ? 'pointer' : 'default'};">
      {username ?? "匿名"}
    </a>
    {#if badge}
      <a href="/guilds/{badge.guild_id}" class="no-underline" style="
        font-size: 9px;
        font-weight: 700;
        padding: 0 5px;
        border-radius: 99px;
        line-height: 1.6;
        color: var(--vercel-warning);
        background: rgba(245,158,11,0.12);
        border: 1px solid rgba(245,158,11,0.3);
        white-space: nowrap;
        display: inline-block;
        vertical-align: middle;
      ">Lv.{badge.guild_level} {badge.guild_name}</a>
    {/if}
  </div>
  <span>·</span>
  <span>{timeAgo(createdAt)}</span>
</div>
