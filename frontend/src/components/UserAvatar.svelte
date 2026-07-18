<script lang="ts">
  import { onMount } from "svelte";
  import { LogOutIcon } from "@lucide/svelte";
  import { initAuth, currentUser, logout } from "../stores/auth";

  let menuOpen = false;

  onMount(() => initAuth());

  function toggleMenu() { menuOpen = !menuOpen; }

  async function handleLogout() {
    await logout();
    window.location.href = "/";
  }

  function handleClickOutside(e: MouseEvent) {
    if (!(e.target as HTMLElement).closest(".user-menu")) {
      menuOpen = false;
    }
  }
</script>

<svelte:window on:click={handleClickOutside} />

{#if $currentUser}
  <div class="user-menu relative">
    <button
      class="avatar"
      style="width: 1.75rem; height: 1.75rem; font-size: 0.6875rem;"
      on:click={toggleMenu}
    >
      {($currentUser.nickname ?? $currentUser.username)[0].toUpperCase()}
    </button>
    {#if menuOpen}
      <div class="menu-dropdown absolute right-0 top-full mt-2 z-50" style="min-width: 12rem;">
        <div class="px-3 py-2 text-xs" style="color: var(--vercel-text-tertiary);">
          {$currentUser.nickname ?? $currentUser.username}
        </div>
        <div class="divider"></div>
        <button class="menu-item" on:click={handleLogout}>
          <LogOutIcon class="size-3.5" />
          退出登录
        </button>
      </div>
    {/if}
  </div>
{:else}
  <a href="/login" class="btn btn-primary btn-sm">登录</a>
{/if}
