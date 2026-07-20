<script lang="ts">
  import { onMount } from "svelte";
  import { listGuilds, type Guild } from "../../lib/guilds";
  import { currentUser, initAuth } from "../../stores/auth";
  import GuildCard from "./GuildCard.svelte";

  let guilds = $state<Guild[]>([]);
  let loading = $state(true);

  const LEVELS = [
    { label: "heiker", color: "#cd7f32", min: 1 },
    { label: "black客", color: "#c0c0c0", min: 2 },
    { label: "黑色的客人", color: "#ffd700", min: 3 },
    { label: "黑客", color: "#b9f2ff", min: 4 },
    { label: "Natriumchlorid", color: "#ff4500", min: 5 },
  ];

  onMount(async () => {
    await initAuth();
    try {
      guilds = await listGuilds();
    } catch {}
    loading = false;
  });

  function grouped() {
    const map: Record<number, Guild[]> = {};
    for (const g of guilds) {
      const lv = g.level || 1;
      if (!map[lv]) map[lv] = [];
      map[lv].push(g);
    }
    return LEVELS.filter((l) => map[l.min]).map((l) => ({ ...l, guilds: map[l.min] }));
  }
</script>

{#if loading}
  <div class="empty-state"><div class="spinner mb-3"></div>加载中...</div>
{:else if guilds.length === 0}
  <div class="empty-state">
    <p>还没有社团</p>
    {#if $currentUser}
      <a href="/guilds/new" class="btn btn-primary btn-sm mt-4">创建第一个社团</a>
    {/if}
  </div>
{:else}
  <div class="flex items-center justify-between mb-4">
    <h1 class="view-title">社团</h1>
    {#if $currentUser}
      <a href="/guilds/new" class="btn btn-primary btn-sm">创建社团</a>
    {/if}
  </div>

  {#each grouped() as tier, i (tier.label)}
    <div class="mb-6">
      <div class="flex items-center gap-2 mb-3">
        <span class="text-xs font-bold px-2 py-0.5 rounded-full" style="background: {tier.color}22; color: {tier.color}; border: 1px solid {tier.color}44;">
          {tier.label}
        </span>
        <span class="text-xs" style="color: var(--vercel-text-tertiary);">Lv.{tier.min}</span>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {#each tier.guilds as g (g.id)}
          <GuildCard guild={g} />
        {/each}
      </div>
    </div>
    {#if i < grouped().length - 1}
      <div class="h-px mb-5" style="background: linear-gradient(90deg, transparent, var(--vercel-border), transparent);"></div>
    {/if}
  {/each}
{/if}
