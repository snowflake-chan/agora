<script lang="ts">
  import { translator } from "../../lib/i18n";
  import type { GuildMember } from "../../lib/guilds";

  let { member }: { member: GuildMember } = $props();

  const ROLE_COLORS: Record<string, string> = {
    president: "#d7a928",
    vice_president: "#73a9b8",
    member: "",
  };

  function roleLabel(role: string) {
    return $translator(`guild.role.${role}`);
  }
</script>

<a
  href="/users/{member.user_id}"
  class="card p-4 flex items-center gap-3 block no-underline hover:border-gray-500 transition-colors"
  style="border: 1px solid var(--vercel-border); position: relative; overflow: hidden;"
>
  <div class="avatar-sm flex-shrink-0" style="width: 2.5rem; height: 2.5rem; font-size: 1rem;">
    {(member.nickname ?? member.username)[0].toUpperCase()}
  </div>
  <div class="min-w-0">
    <p class="text-sm font-medium truncate" style="color: var(--vercel-text);">{member.nickname ?? member.username}</p>
    <p class="text-xs truncate" style="color: var(--vercel-text-tertiary);">@{member.username}</p>
  </div>
  {#if member.role !== "member"}
    <span
      class="absolute top-2 right-2 text-[10px] font-bold px-1.5 py-0.5 rounded"
      style="background: {ROLE_COLORS[member.role]}22; color: {ROLE_COLORS[member.role]}; border: 1px solid {ROLE_COLORS[member.role]}44;"
    >
      {roleLabel(member.role)}
    </span>
  {/if}
</a>
