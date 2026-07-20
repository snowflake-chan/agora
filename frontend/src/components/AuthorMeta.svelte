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

<div class="author-meta relative z-10 text-xs" style="color: var(--vercel-text-tertiary);">
  <a href={profileHref} class="avatar avatar-sm no-underline hover:opacity-80 transition-opacity" style="cursor: {userId ? 'pointer' : 'default'};">
    {(username ?? "?")[0].toUpperCase()}
  </a>
  <span class="author-identity">
    <a href={profileHref} class="author-name no-underline hover:underline" style="color: var(--vercel-text-secondary); cursor: {userId ? 'pointer' : 'default'};">
      {username ?? $translator("common.anonymous")}
    </a>
    {#if guild}
      <a class="guild-badge" href={`/guilds/${guild.guild_id}`}>
        Lv.{guild.guild_level} {guild.guild_name}
      </a>
    {/if}
  </span>
  <span class="author-separator" aria-hidden="true">&middot;</span>
  <span class="author-time">{timeAgo(createdAt)}</span>
</div>

<style>
  .author-meta {
    display: flex;
    min-width: 0;
    max-width: 100%;
    flex: 0 1 auto;
    align-items: center;
    gap: 0.375rem;
  }

  .author-meta > .avatar {
    flex: 0 0 auto;
  }

  .author-identity {
    display: inline-flex;
    min-width: 0;
    align-items: center;
    gap: 0.3rem;
    overflow: hidden;
  }

  .author-name {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .author-separator,
  .author-time {
    flex: 0 0 auto;
  }

  .author-time {
    white-space: nowrap;
  }

  .guild-badge {
    min-width: 0;
    overflow: hidden;
    max-width: 8rem;
    flex: 0 1 auto;
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

  @media (max-width: 640px) {
    .author-meta {
      display: grid;
      grid-template-columns: 1.5rem minmax(0, 1fr);
      grid-template-rows: auto auto;
      flex: 1 1 7rem;
      column-gap: 0.375rem;
      row-gap: 0.1rem;
    }

    .author-meta > .avatar {
      grid-column: 1;
      grid-row: 1 / 3;
    }

    .author-identity {
      grid-column: 2;
      grid-row: 1;
    }

    .author-separator {
      display: none;
    }

    .author-time {
      grid-column: 2;
      grid-row: 2;
      font-size: 0.65rem;
    }

    .guild-badge {
      max-width: 55%;
    }
  }
</style>
