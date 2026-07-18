<script lang="ts">
  import { onMount } from "svelte";
  import { PlusIcon, GitBranchIcon, LogOutIcon, UserIcon } from "@lucide/svelte";
  import { initAuth, currentUser, logout } from "../stores/auth";
  import PostForm from "./posts/PostForm.svelte";
  import PatchForm from "./patches/PatchForm.svelte";

  let showPostForm = false;
  let showPatchForm = false;
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

<div class="w-px h-5 mx-1 rounded-full" style="background: rgba(255,255,255,0.1);"></div>

<button
  class="pill-item"
  on:click={() => (showPostForm = true)}
  title="发帖"
>
  <PlusIcon class="size-4.5" />
  <span class="pill-tooltip">发帖</span>
</button>

{#if $currentUser}
  <button
    class="pill-item"
    on:click={() => (showPatchForm = true)}
    title="发起变更"
  >
    <GitBranchIcon class="size-4.5" />
    <span class="pill-tooltip">发起变更</span>
  </button>
{/if}

<div class="user-menu relative">
  {#if $currentUser}
    <button class="pill-item" on:click={toggleMenu} title="我的">
      <div class="flex size-4.5 items-center justify-center rounded-full text-[8px] font-bold" style="background: var(--vercel-text); color: var(--vercel-bg);">
        {($currentUser.nickname ?? $currentUser.username)[0].toUpperCase()}
      </div>
      <span class="pill-tooltip">我的</span>
    </button>

    {#if menuOpen}
      <div class="menu-dropdown absolute right-0 bottom-full mb-2 z-50" style="min-width: 12rem;">
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
  {:else}
    <a href="/login" class="pill-item" title="登录">
      <UserIcon class="size-4.5" />
      <span class="pill-tooltip">登录</span>
    </a>
  {/if}
</div>

{#if showPostForm}
  <PostForm on:close={() => (showPostForm = false)} />
{/if}
{#if showPatchForm}
  <PatchForm on:close={() => (showPatchForm = false)} />
{/if}
