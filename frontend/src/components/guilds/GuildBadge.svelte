<script lang="ts">
  import { onMount } from "svelte";
  import { getMyGuild, type UserGuildBadge } from "../../lib/guilds";
  import { currentUser } from "../../stores/auth";

  let badge = $state<UserGuildBadge | null>(null);

  const LEVEL_LABELS = ["", "heiker", "black客", "黑色的客人", "黑客", "Natriumchlorid"];
  const LEVEL_COLORS = ["", "#cd7f32", "#c0c0c0", "#ffd700", "#b9f2ff", "#ff4500"];

  onMount(async () => {
    if ($currentUser) {
      try { badge = await getMyGuild(); } catch {}
    }
  });

  // Re-fetch when user changes
  $effect(() => {
    if ($currentUser) {
      getMyGuild().then((b) => badge = b).catch(() => badge = null);
    } else {
      badge = null;
    }
  });
</script>

{#if badge}
  <a
    href="/guilds/{badge.guild_id}"
    class="no-underline inline-flex items-center"
    style="font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 99px; line-height: 1.4; color: {LEVEL_COLORS[badge.guild_level] || '#888'}; background: {(LEVEL_COLORS[badge.guild_level] || '#888')}18; border: 1px solid {(LEVEL_COLORS[badge.guild_level] || '#888')}44; white-space: nowrap;"
  >
    Lv.{badge.guild_level} {LEVEL_LABELS[badge.guild_level] || ''} · {badge.guild_name}
  </a>
{/if}
