<script lang="ts">
  import { onMount, tick } from "svelte";
  import {
    PlusIcon,
    GitBranchIcon,
    LogOutIcon,
    UserIcon,
  } from "@lucide/svelte";
  import { initAuth, currentUser, logout } from "../stores/auth";
  import { mainView } from "../stores/nav";
  import PostForm from "./posts/PostForm.svelte";
  import PatchForm from "./patches/PatchForm.svelte";

  // 'posts' | 'patches' = in-page view selection
  // 'post'  | 'patch'  = a composer dialog is open (its trigger is selected)
  // null                = nothing selected (e.g. user menu)
  let activeKey = $state<"posts" | "patches" | "post" | "patch" | null>(null);
  let showPostForm = $state(false);
  let showPatchForm = $state(false);
  let menuOpen = $state(false);

  let trackEl = $state<HTMLDivElement | null>(null);
  let highlightEl = $state<HTMLDivElement | null>(null);

  onMount(() => initAuth());

  onMount(() => {
    let initial: "posts" | "patches" = "posts";
    try {
      const saved = localStorage.getItem("agora:initView");
      if (saved === "patches") { initial = "patches"; localStorage.removeItem("agora:initView"); }
    } catch (e) {}
    activeKey = initial;
    mainView.set(initial);
    requestAnimationFrame(updateHighlight);
  });

  // Slide the highlight pill to the active slot with an Apple-style curve.
  async function updateHighlight() {
    await tick();
    if (!trackEl || !highlightEl) return;

    if (activeKey === null || activeKey === "user") {
      highlightEl.classList.add("is-hidden");
      return;
    }

    const slot = trackEl.querySelector<HTMLElement>(
      `[data-key="${activeKey}"]`,
    );
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

  // Reactively re-position whenever the selection changes.
  $effect(() => {
    // reading activeKey registers a dependency
    void activeKey;
    updateHighlight();
  });

  function routeKey(): "posts" | "patches" {
    return $mainView === "patches" ? "patches" : "posts";
  }

  function switchView(key: "posts" | "patches") {
    if (menuOpen) menuOpen = false;
    if (showPostForm) showPostForm = false;
    if (showPatchForm) showPatchForm = false;
    activeKey = key;
    mainView.set(key);
    // On non-home pages there is no MainView listening, so navigate to /
    const path = window.location.pathname;
    if (path !== '/' && path !== '') {
      try { localStorage.setItem("agora:initView", key); } catch (e) {}
      window.location.href = '/';
    }
  }

  function selectAndOpen(key: "post" | "patch") {
    activeKey = key;
    if (key === "post") showPostForm = true;
    else showPatchForm = true;
  }

  function closeComposer(key: "post" | "patch") {
    if (key === "post") showPostForm = false;
    else showPatchForm = false;
    // back to the current in-page view selection
    activeKey = routeKey();
  }

  function toggleMenu() {
    menuOpen = !menuOpen;
    activeKey = menuOpen ? null : routeKey();
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
  <!-- sliding selection indicator -->
  <div class="pill-highlight is-hidden" bind:this={highlightEl}></div>

  <!-- primary nav (in-page view switch) -->
  <button
    type="button"
    class="pill-item pill-slot"
    class:is-active={activeKey === "posts"}
    data-key="posts"
    onclick={() => switchView("posts")}
    title="帖子"
  >
    <svg
      class="size-4.5"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      ><path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
      /></svg
    >
    <span class="pill-tooltip">帖子</span>
  </button>

  <button
    type="button"
    class="pill-item pill-slot"
    class:is-active={activeKey === "patches"}
    data-key="patches"
    onclick={() => switchView("patches")}
    title="变更"
  >
    <svg
      class="size-4.5"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      ><path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
      /></svg
    >
    <span class="pill-tooltip">变更</span>
  </button>

  <div
    class="w-px h-5 mx-1 rounded-full"
    style="background: rgba(255,255,255,0.1);"
  ></div>

  <!-- composer triggers -->
  <button
    class="pill-item pill-slot"
    class:is-active={activeKey === "post"}
    data-key="post"
    onclick={() => selectAndOpen("post")}
    title="发帖"
  >
    <PlusIcon class="size-4.5" />
    <span class="pill-tooltip">发帖</span>
  </button>

  {#if $currentUser}
    <button
      class="pill-item pill-slot"
      class:is-active={activeKey === "patch"}
      data-key="patch"
      onclick={() => selectAndOpen("patch")}
      title="发起变更"
    >
      <GitBranchIcon class="size-4.5" />
      <span class="pill-tooltip">发起变更</span>
    </button>
  {/if}

  <div class="user-menu relative">
    {#if $currentUser}
      <button
        class="pill-item pill-slot"
        class:is-active={activeKey === "user"}
        data-key="user"
        onclick={toggleMenu}
        title="我的"
      >
        <div
          class="flex size-4.5 items-center justify-center rounded-full text-[8px] font-bold"
          style="background: var(--vercel-text); color: var(--vercel-bg);"
        >
          {($currentUser.nickname ?? $currentUser.username)[0].toUpperCase()}
        </div>
        <span class="pill-tooltip">我的</span>
      </button>

      {#if menuOpen}
        <div
          class="menu-dropdown absolute right-0 bottom-full mb-2 z-50"
          style="min-width: 12rem;"
        >
          <div
            class="px-3 py-2 text-xs"
            style="color: var(--vercel-text-tertiary);"
          >
            {$currentUser.nickname ?? $currentUser.username}
          </div>
          <div class="divider"></div>
          <a href="/my" class="menu-item">
            <UserIcon class="size-3.5" />
            我的资料
          </a>
          <button class="menu-item" onclick={handleLogout}>
            <LogOutIcon class="size-3.5" />
            退出登录
          </button>
        </div>
      {/if}
    {:else}
      <a
        href="/login"
        class="pill-item pill-slot"
        data-key="login"
        title="登录"
      >
        <UserIcon class="size-4.5" />
        <span class="pill-tooltip">登录</span>
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
