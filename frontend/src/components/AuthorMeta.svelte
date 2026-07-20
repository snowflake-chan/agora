<script lang="ts">
  import { onMount } from "svelte";
  import { getUserGuild, type UserGuildBadge } from "../lib/guilds";
  import { translator } from "../lib/i18n";
  import { timeAgo } from "../lib/utils";

  let { username, userId, createdAt }: { username: string; userId?: string; createdAt: string } = $props();

  let profileHref = $derived(userId ? `/users/${userId}` : "#");
  let guild = $state<UserGuildBadge | null>(null);

  onMount(async () => {
    if (!userId) return;
    try {
      guild = await getUserGuild(userId);
    } catch {
      guild = null;
    }
  });
</script>

<div class="relative z-10 flex shrink-0 items-center gap-1.5 text-xs" style="color: var(--vercel-text-tertiary);">
  <a href={profileHref} class="avatar avatar-sm no-underline hover:opacity-80 transition-opacity" style="cursor: {userId ? 'pointer' : 'default'};">
    {(username ?? "?")[0].toUpperCase()}
  </a>
  <span class="author-identity">
    <a href={profileHref} class="no-underline hover:underline" style="color: var(--vercel-text-secondary); cursor: {userId ? 'pointer' : 'default'};">
      {username ?? $translator("common.anonymous")}
    </a>
    {#if guild}
      <a class="guild-badge" href={`/guilds/${guild.guild_id}`}>
        Lv.{guild.guild_level} {guild.guild_name}
      </a>
    {/if}
  </span>
  <span>·</span>
  <span>{timeAgo(createdAt)}</span>
</div>

<style>
  .author-identity {
    display: inline-flex;
    min-width: 0;
    align-items: center;
    gap: 0.3rem;
  }

  .guild-badge {
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
</style>
