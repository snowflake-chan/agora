<script lang="ts">
  import { translator } from "../../lib/i18n";
  import { guildLevelKey, isGuildLogoImage } from "../../lib/guildPresentation";
  import type { Guild } from "../../lib/guilds";
  import { avatarInitial } from "../../lib/utils";

  let { guild }: { guild: Guild } = $props();
</script>

<a href="/guilds/{guild.id}" class="guild-card card p-4 block no-underline">
  <div class="flex items-center gap-3">
    <div class="guild-mark flex-shrink-0 w-12 h-12 flex items-center justify-center text-xl">
      {#if isGuildLogoImage(guild.logo)}
        <img src={guild.logo!} alt="" class="guild-logo-image" loading="lazy" />
      {:else}
        {guild.logo || avatarInitial(guild.name)}
      {/if}
    </div>
    <div class="min-w-0">
      <h3 class="font-semibold truncate" style="color: var(--vercel-text);">{guild.name}</h3>
      {#if guild.description}
        <p class="text-xs truncate mt-0.5" style="color: var(--vercel-text-tertiary);">{guild.description}</p>
      {/if}
      <div class="guild-meta flex items-center gap-2 mt-1.5 text-xs" style="color: var(--vercel-text-tertiary);">
        <span>{$translator(guildLevelKey(guild.level))}</span>
        <span>{$translator("guild.membersCount", { count: guild.member_count })}</span>
        <span
          class="guild-president"
          title={$translator("guild.presidentName", { name: guild.president_username })}
        >{$translator("guild.presidentName", { name: guild.president_username })}</span>
      </div>
    </div>
  </div>
</a>

<style>
  .guild-card {
    border: 1px solid var(--vercel-border);
    transition:
      border-color 220ms var(--apple-ease),
      background 220ms var(--apple-ease),
      transform 220ms var(--apple-ease);
  }

  .guild-card:hover {
    border-color: var(--vercel-border-hover);
    background: var(--vercel-hover);
    transform: translateY(-1px);
  }

  .guild-card:active {
    transform: translateY(0) scale(0.99);
  }

  .guild-mark {
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius);
    background: var(--vercel-surface);
  }

  .guild-logo-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: inherit;
  }

  .guild-meta {
    gap: 0.25rem 0.625rem;
    flex-wrap: wrap;
  }

  .guild-meta span {
    white-space: nowrap;
  }

  .guild-president {
    min-width: 0;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
