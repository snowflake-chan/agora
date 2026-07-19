<script lang="ts">
  import { onMount, tick } from "svelte";
  import {
    GitBranchIcon,
    LogOutIcon,
    PlusIcon,
    SettingsIcon,
    UserIcon,
  } from "@lucide/svelte";
  import { translator } from "../lib/i18n";
  import { initAuth, currentUser, logout } from "../stores/auth";
  import { mainView } from "../stores/nav";
  import PostForm from "./posts/PostForm.svelte";
  import PatchForm from "./patches/PatchForm.svelte";

  type ActiveKey = "posts" | "patches" | "post" | "patch" | "user" | null;
  let activeKey = $state<ActiveKey>(null);
  let showPostForm = $state(false);
  let showPatchForm = $state(false);
  let menuOpen = $state(false);
  let authReady = $state(false);
  let trackEl = $state<HTMLDivElement | null>(null);
  let highlightEl = $state<HTMLDivElement | null>(null);

  onMount(async () => {
    await initAuth();
    authReady = true;
  });

  onMount(() => {
    let initial: "posts" | "patches" = "posts";
    try {
      const saved = localStorage.getItem("agora:initView");
      if (saved === "patches") {
        initial = "patches";
        localStorage.removeItem("agora:initView");
      }
    } catch {}
    activeKey = initial;
    mainView.set(initial);
    requestAnimationFrame(updateHighlight);
  });

  async function updateHighlight() {
    await tick();
    if (!trackEl || !highlightEl) return;
    if (activeKey === null || activeKey === "user") {
      highlightEl.classList.add("is-hidden");
      return;
    }
    const slot = trackEl.querySelector<HTMLElement>(`[data-key="${activeKey}"]`);
    if (!slot) {
      highlightEl.classList.add("is-hidden");
      return;
    }
    const trackRect = trackEl.getBoundingClientRect();
    const slotRect = slot.getBoundingClientRect();
    highlightEl.style.width = `${slotRect.width}px`;
    highlightEl.style.transform = `translateX(${slotRect.left - trackRect.left}px)`;
    highlightEl.classList.remove("is-hidden");
  }

  $effect(() => {
    void activeKey;
    updateHighlight();
  });

  function routeKey(): "posts" | "patches" {
    return $mainView === "patches" ? "patches" : "posts";
  }

  function switchView(key: "posts" | "patches") {
    menuOpen = false;
    showPostForm = false;
    showPatchForm = false;
    activeKey = key;
    mainView.set(key);
    if (window.location.pathname !== "/" && window.location.pathname !== "") {
      try {
        localStorage.setItem("agora:initView", key);
      } catch {}
      window.location.href = "/";
    }
  }

  async function selectAndOpen(key: "post" | "patch") {
    if (!authReady) {
      await initAuth();
      authReady = true;
    }
    if (!$currentUser) {
      const returnTo = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      window.location.href = `/login?returnTo=${encodeURIComponent(returnTo)}`;
      return;
    }
    activeKey = key;
    if (key === "post") showPostForm = true;
    else showPatchForm = true;
  }

  function closeComposer(key: "post" | "patch") {
    if (key === "post") showPostForm = false;
    else showPatchForm = false;
    activeKey = routeKey();
  }

  function toggleMenu() {
    menuOpen = !menuOpen;
    activeKey = menuOpen ? "user" : routeKey();
  }

  async function handleLogout() {
    await logout();
    window.location.href = "/";
  }

  function handleClickOutside(e: MouseEvent) {
    if (!(e.target as HTMLElement).closest(".user-menu") && menuOpen) {
      menuOpen = false;
      activeKey = routeKey();
    }
  }
</script>

<svelte:window onclick={handleClickOutside} />

<div class="pill-track" bind:this={trackEl}>
  <div class="pill-highlight is-hidden" bind:this={highlightEl}></div>

  <button class="pill-item pill-slot" class:is-active={activeKey === "posts"} data-key="posts" type="button" onclick={() => switchView("posts")} title={$translator("nav.home")}>
    <svg class="size-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
    <span class="pill-tooltip">{$translator("nav.home")}</span>
  </button>

  <button class="pill-item pill-slot" class:is-active={activeKey === "patches"} data-key="patches" type="button" onclick={() => switchView("patches")} title={$translator("nav.changes")}>
    <svg class="size-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
    </svg>
    <span class="pill-tooltip">{$translator("nav.changes")}</span>
  </button>

  <div class="mx-1 h-5 w-px rounded-full" style="background: rgba(255,255,255,0.1);" aria-hidden="true"></div>

  <button class="pill-item pill-slot" class:is-active={activeKey === "post"} data-key="post" type="button" onclick={() => selectAndOpen("post")} title={$translator("nav.newPost")}>
    <PlusIcon class="size-4.5" />
    <span class="pill-tooltip">{$translator("nav.newPost")}</span>
  </button>

  <button class="pill-item pill-slot" class:is-active={activeKey === "patch"} data-key="patch" type="button" onclick={() => selectAndOpen("patch")} title={$translator("nav.newChange")}>
    <GitBranchIcon class="size-4.5" />
    <span class="pill-tooltip">{$translator("nav.newChange")}</span>
  </button>

  <div class="user-menu relative">
    {#if $currentUser}
      <button class="pill-item pill-slot" class:is-active={activeKey === "user"} data-key="user" type="button" onclick={toggleMenu} title={$translator("nav.profile")}>
        <div class="flex size-4.5 items-center justify-center rounded-full text-[8px] font-bold" style="background: var(--vercel-text); color: var(--vercel-bg);">
          {($currentUser.nickname ?? $currentUser.username)[0].toUpperCase()}
        </div>
        <span class="pill-tooltip">{$translator("nav.profile")}</span>
      </button>

      {#if menuOpen}
        <div class="menu-dropdown absolute bottom-full right-0 z-50 mb-2" style="min-width: 12rem;">
          <div class="px-3 py-2 text-xs" style="color: var(--vercel-text-tertiary);">{$currentUser.nickname ?? $currentUser.username}</div>
          <div class="divider"></div>
          <a href="/my" class="menu-item"><UserIcon class="size-3.5" />{$translator("nav.profile")}</a>
          <a href="/settings" class="menu-item"><SettingsIcon class="size-3.5" />{$translator("common.settings")}</a>
          <button class="menu-item" onclick={handleLogout}><LogOutIcon class="size-3.5" />{$translator("common.logout")}</button>
        </div>
      {/if}
    {:else}
      <a href="/login" class="pill-item pill-slot" data-key="login" title={$translator("nav.login")}>
        <UserIcon class="size-4.5" />
        <span class="pill-tooltip">{$translator("nav.login")}</span>
      </a>
    {/if}
  </div>
</div>

{#if showPostForm}
  <PostForm on:close={() => closeComposer("post")} />
{/if}
{#if showPatchForm}
  <PatchForm on:close={() => closeComposer("patch")} />
{/if}
