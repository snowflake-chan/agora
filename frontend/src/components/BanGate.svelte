<script lang="ts">
  import { onMount } from "svelte";
  import { translator, translateError } from "../lib/i18n";
  import { currentUser, initAuth, logout } from "../stores/auth";
  import GlassModal from "./GlassModal.svelte";

  let banned = $state(false);
  let reason = $state("");

  onMount(async () => {
    await initAuth();
    if (!$currentUser) return;
    try {
      const res = await fetch("/api/v1/users/me/ban-status", { credentials: "include" });
      if (res.status === 403) {
        const data = await res.json();
        reason = translateError(
          { code: data.detail },
          $translator,
          "moderation.accountBanned",
        );
        banned = true;
      }
    } catch {}
  });
</script>

{#if banned}
  <GlassModal show={true} title={$translator("moderation.accountBannedTitle")}>
    <p style="color:var(--vercel-danger);">{reason}</p>
    <p class="mt-3 text-xs" style="color:var(--vercel-text-tertiary);">
      {$translator("moderation.contactAdmin")}
    </p>
    <div class="mt-5 flex justify-end">
      <button
        class="btn btn-secondary btn-sm"
        onclick={async () => {
          await logout();
          banned = false;
        }}
      >
        {$translator("common.logout")}
      </button>
    </div>
  </GlassModal>
{/if}
