<script lang="ts">
  import { translator } from "../../lib/i18n";
  import type { GuildMember } from "../../lib/guilds";
  import { avatarInitial, displayName } from "../../lib/utils";

  let { member }: { member: GuildMember } = $props();

  const ROLE_COLORS: Record<string, string> = {
    president: "var(--vercel-warning)",
    vice_president: "var(--vercel-info)",
  };

  function roleLabel(role: string) {
    return $translator(`guild.role.${role}`);
  }
</script>

<a
  href="/users/{member.user_id}"
  class="guild-member-card card p-4 flex items-center gap-3 block no-underline hover:border-gray-500 transition-colors"
  class:has-role={member.role !== "member"}
  style="border: 1px solid var(--vercel-border); position: relative; overflow: hidden;"
>
  <div class="avatar avatar-sm" style="width: 2.5rem; height: 2.5rem; font-size: 1rem;">
    {avatarInitial(member.nickname, member.username)}
  </div>
  <div class="member-copy min-w-0">
    <p class="text-sm font-medium truncate" style="color: var(--vercel-text);">{displayName(member.nickname, member.username)}</p>
    <p class="text-xs truncate" style="color: var(--vercel-text-tertiary);">@{member.username}</p>
  </div>
  {#if member.role !== "member"}
    <span
      class="absolute top-2 right-2 text-[10px] font-bold px-1.5 py-0.5 rounded"
      style="background: color-mix(in srgb, {ROLE_COLORS[member.role]} 10%, transparent); color: {ROLE_COLORS[member.role]}; border: 1px solid color-mix(in srgb, {ROLE_COLORS[member.role]} 28%, transparent);"
    >
      {roleLabel(member.role)}
    </span>
  {/if}
</a>

<style>
  .guild-member-card.has-role .member-copy {
    padding-right: 4.75rem;
  }
</style>
