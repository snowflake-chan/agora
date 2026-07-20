<script lang="ts">
  import type { Guild } from "../../lib/guilds";

  let { guild }: { guild: Guild } = $props();
</script>

<a href="/guilds/{guild.id}" class="card p-4 block no-underline hover-card transition-colors" style="border: 1px solid var(--vercel-border);">
  <div class="flex items-center gap-3">
    <div class="flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center text-xl" style="background: linear-gradient(135deg, var(--vercel-surface-highlight), var(--vercel-surface)); border: 1px solid var(--vercel-border);">
      {guild.logo || guild.name[0].toUpperCase()}
    </div>
    <div class="min-w-0">
      <h3 class="font-semibold truncate" style="color: var(--vercel-text);">{guild.name}</h3>
      {#if guild.description}
        <p class="text-xs truncate mt-0.5" style="color: var(--vercel-text-tertiary);">{guild.description}</p>
      {/if}
      <div class="flex items-center gap-2 mt-1.5 text-xs" style="color: var(--vercel-text-tertiary);">
        <span>Lv.{guild.level}</span>
        <span>·</span>
        <span>{guild.member_count} 成员</span>
        <span>·</span>
        <span>社长 {guild.president_username}</span>
      </div>
    </div>
  </div>
</a>

<style>
  .hover-card {
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .hover-card:hover {
    border-color: rgba(255,255,255,0.15) !important;
    box-shadow: 0 2px 12px rgba(0,0,0,0.2);
  }
</style>
