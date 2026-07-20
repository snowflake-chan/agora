<script lang="ts">
  import { onMount } from "svelte";
  import { translator } from "../../lib/i18n";
  import { listGuilds, type Guild } from "../../lib/guilds";
  import { guildLevelColor, guildLevelKey } from "../../lib/guildPresentation";
  import { currentUser, initAuth } from "../../stores/auth";
  import GuildCard from "./GuildCard.svelte";

  let guilds = $state<Guild[]>([]);
  let loading = $state(true);
  let error = $state(false);

  const LEVELS = [1, 2, 3, 4, 5];

  onMount(async () => {
    await initAuth();
    await loadGuilds();
  });

  async function loadGuilds() {
    loading = true;
    error = false;
    try {
      guilds = await listGuilds();
    } catch {
      error = true;
    } finally {
      loading = false;
    }
  }

  function grouped() {
    const map: Record<number, Guild[]> = {};
    for (const g of guilds) {
      const lv = g.level >= 1 && g.level <= 5 ? g.level : 1;
      if (!map[lv]) map[lv] = [];
      map[lv].push(g);
    }
    return LEVELS.filter((level) => map[level]).map((level) => ({
      level,
      color: guildLevelColor(level),
      guilds: map[level],
    }));
  }
</script>

{#if loading}
  <div class="empty-state"><div class="spinner mb-3"></div>{$translator("guild.loading")}</div>
{:else if error}
  <div class="empty-state">
    <p>{$translator("guild.loadFailed")}</p>
    <button class="btn btn-secondary btn-sm mt-4" onclick={loadGuilds}>
      {$translator("common.retry")}
    </button>
  </div>
{:else if guilds.length === 0}
  <div class="empty-state">
    <p>{$translator("guild.empty")}</p>
    {#if $currentUser}
      <a href="/guilds/new" class="btn btn-primary btn-sm mt-4">{$translator("guild.createFirst")}</a>
    {/if}
  </div>
{:else}
  <div class="guild-list-heading flex items-center justify-between mb-4">
    <h1 class="view-title">{$translator("guild.title")}</h1>
    {#if $currentUser}
      <a href="/guilds/new" class="btn btn-primary btn-sm">{$translator("guild.create")}</a>
    {/if}
  </div>

  {#each grouped() as tier, i (tier.level)}
    <div class="mb-6">
      <div class="flex items-center gap-2 mb-3">
        <span class="text-xs font-bold px-2 py-0.5 rounded-full" style="background: {tier.color}22; color: {tier.color}; border: 1px solid {tier.color}44;">
          {$translator(guildLevelKey(tier.level))}
        </span>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {#each tier.guilds as g (g.id)}
          <GuildCard guild={g} />
        {/each}
      </div>
    </div>
    {#if i < grouped().length - 1}
      <div class="h-px mb-5" style="background: var(--vercel-border);"></div>
    {/if}
  {/each}
{/if}

<style>
  .guild-list-heading {
    gap: 0.75rem;
  }

  .guild-list-heading :global(.view-title) {
    min-width: 0;
  }

  @media (max-width: 34rem) {
    .guild-list-heading {
      align-items: flex-start;
      flex-wrap: wrap;
    }
  }
</style>
