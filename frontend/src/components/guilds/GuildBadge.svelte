<script lang="ts">
  import { getMyGuild, type UserGuildBadge } from "../../lib/guilds";
  import { guildLevelColor, guildLevelKey } from "../../lib/guildPresentation";
  import { translator } from "../../lib/i18n";
  import { currentUser } from "../../stores/auth";

  let badge = $state<UserGuildBadge | null>(null);
  let requestId = 0;

  // Re-fetch only when the authenticated identity changes.
  $effect(() => {
    const userId = $currentUser?.id;
    const currentRequest = ++requestId;
    if (userId) {
      getMyGuild()
        .then((value) => {
          if (currentRequest === requestId) badge = value;
        })
        .catch(() => {
          if (currentRequest === requestId) badge = null;
        });
    } else {
      badge = null;
    }
  });
</script>

{#if badge}
  <a
    href="/guilds/{badge.guild_id}"
    class="no-underline inline-flex items-center"
    style="font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 99px; line-height: 1.4; color: {guildLevelColor(badge.guild_level)}; background: color-mix(in srgb, {guildLevelColor(badge.guild_level)} 10%, transparent); border: 1px solid color-mix(in srgb, {guildLevelColor(badge.guild_level)} 28%, transparent); white-space: nowrap;"
  >
    {$translator(guildLevelKey(badge.guild_level))} · {badge.guild_name}
  </a>
{/if}
