<script lang="ts">
  import { MessageCircleIcon, GitBranchIcon, PlusIcon, LogOutIcon, UserIcon } from "@lucide/svelte";
  import { onMount } from "svelte";
  import { initAuth, currentUser, logout } from "../stores/auth";
  import PostForm from "./posts/PostForm.svelte";
  import PatchForm from "./patches/PatchForm.svelte";

  let menuOpen = false;
  let currentPath = "";
  let showPostForm = false;
  let showPatchForm = false;

  onMount(() => {
    initAuth();
    currentPath = window.location.pathname;
  });

  function toggleMenu() {
    menuOpen = !menuOpen;
  }

  async function handleLogout() {
    await logout();
    window.location.href = "/";
  }

  function handleClickOutside(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest(".user-menu")) {
      menuOpen = false;
    }
  }

  function isActive(path: string) {
    if (path === "/") return currentPath === "/" || currentPath.startsWith("/posts");
    return currentPath.startsWith(path);
  }
</script>

<svelte:window on:click={handleClickOutside} />

<!-- Top header -->
<header class="sticky top-0 z-50 border-b" style="border-color: rgba(255,255,255,0.06); background: rgba(12, 12, 14, 0.78); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);">
  <div class="flex h-12 items-center justify-between px-4">
    <a href="/" class="flex items-center gap-2">
      <img src="/favicon.svg" alt="" width="22" height="22" class="size-[22px]" />
      <span class="text-lg font-bold tracking-tight" style="color: var(--vercel-text);">Agora</span>
    </a>

    <div class="flex items-center gap-2">
      <button class="btn btn-primary btn-sm" on:click={() => (showPostForm = true)}>
        <PlusIcon class="size-4" />
        发帖
      </button>

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
    </div>
  </div>
</header>

<!-- Floating pill navigation bar -->
<nav
  id="pill-bar"
  class="fixed bottom-4 left-1/2 z-40 -translate-x-1/2"
  style="
    background: rgba(20, 20, 22, 0.85);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 9999px;
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    box-shadow: 0 2px 16px rgba(0,0,0,0.3), 0 0 0 1px rgba(255,255,255,0.03);
  "
>
  <div class="flex items-center h-11 px-1.5 gap-0.5">
    <a
      href="/"
      class="pill-item"
      class:active={isActive('/')}
      title="帖子"
    >
      <MessageCircleIcon class="size-4.5" />
      <span class="pill-tooltip">帖子</span>
    </a>

    <a
      href="/patches"
      class="pill-item"
      class:active={isActive('/patches')}
      title="变更"
    >
      <GitBranchIcon class="size-4.5" />
      <span class="pill-tooltip">变更</span>
    </a>

    <div class="w-px h-5 mx-1 rounded-full" style="background: rgba(255,255,255,0.1);"></div>

    <button
      class="pill-item bg-transparent border-0"
      on:click={() => (showPostForm = true)}
      title="发帖"
      style="font-family: inherit;"
    >
      <PlusIcon class="size-4.5" />
      <span class="pill-tooltip">发帖</span>
    </button>

    {#if $currentUser}
      <button
        class="pill-item bg-transparent border-0"
        on:click={toggleMenu}
        title="我的"
        style="font-family: inherit;"
      >
        <UserIcon class="size-4.5" />
        <span class="pill-tooltip">我的</span>
      </button>
    {:else}
      <a
        href="/login"
        class="pill-item"
        title="登录"
      >
        <UserIcon class="size-4.5" />
        <span class="pill-tooltip">登录</span>
      </a>
    {/if}
  </div>
</nav>

<!-- Modals -->
{#if showPostForm}
  <PostForm on:close={() => (showPostForm = false)} />
{/if}
{#if showPatchForm}
  <PatchForm on:close={() => (showPatchForm = false)} />
{/if}

<style>
  .pill-item {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.25rem;
    height: 2.25rem;
    border-radius: 9999px;
    color: #fff;
    transition: all 0.15s ease;
    cursor: pointer;
    text-decoration: none;
  }

  .pill-item:hover {
    color: #fff;
    background: rgba(255, 255, 255, 0.12);
  }

  .pill-item.active {
    color: #fff;
    background: rgba(255, 255, 255, 0.15);
  }

  .pill-tooltip {
    position: absolute;
    bottom: calc(100% + 6px);
    left: 50%;
    transform: translateX(-50%) translateY(2px);
    padding: 0.25rem 0.5rem;
    font-size: 0.6875rem;
    font-weight: 500;
    color: var(--vercel-text);
    background: rgba(30, 30, 30, 0.95);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 4px;
    white-space: nowrap;
    pointer-events: none;
    opacity: 0;
    transition: all 0.15s ease;
  }

  .pill-item:hover .pill-tooltip {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
</style>