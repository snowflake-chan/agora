<script lang="ts">
  import { onMount } from "svelte";
  import { currentUser, initAuth } from "../stores/auth";
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
        reason = data.detail || "你的账号已被封禁";
        banned = true;
      }
    } catch {}
  });
</script>

{#if banned}
  <GlassModal show={true} title="账号已封禁">
    <p style="color:var(--vercel-danger);">{reason}</p>
    <p class="mt-3 text-xs" style="color:var(--vercel-text-tertiary);">如有疑问请联系管理员 3121601311@qq.com</p>
  </GlassModal>
{/if}
