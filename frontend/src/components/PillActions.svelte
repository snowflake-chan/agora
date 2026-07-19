<script lang="ts">
  import { onMount, tick } from "svelte";
  import {
    PlusIcon,
    GitBranchIcon,
    LogOutIcon,
    UserIcon,
    ShieldIcon,
  } from "@lucide/svelte";
  import { initAuth, currentUser, logout } from "../stores/auth";
  import { mainView } from "../stores/nav";
  import PostForm from "./posts/PostForm.svelte";
  import PatchForm from "./patches/PatchForm.svelte";
  import GuildBadge from "./guilds/GuildBadge.svelte";
  import GlassModal from "./GlassModal.svelte";

  // 'posts' | 'patches' = in-page view selection
  // 'post'  | 'patch'  = a composer dialog is open (its trigger is selected)
  // null                = nothing selected (e.g. user menu)
  let activeKey = $state<"posts" | "patches" | "post" | "patch" | "guilds" | "admin" | null>(null);
  let showPostForm = $state(false);
  let showPatchForm = $state(false);
  let menuOpen = $state(false);
  let bannedPost = $state(false);
  let bannedPatch = $state(false);

  let trackEl = $state<HTMLDivElement | null>(null);
  let highlightEl = $state<HTMLDivElement | null>(null);

  async function checkBanTypes() {
    try {
      const res = await fetch("/api/v1/users/me/ban-types", { credentials: "include" });
      if (!res.ok) return;
      const data = await res.json();
      bannedPost = data.mute_post || data.ban_user;
      bannedPatch = data.mute_patch || data.ban_user;
    } catch {}
  }

  onMount(() => initAuth());

  onMount(async () => {
    await checkBanTypes();
    let initial: typeof activeKey = "posts";
    const path = window.location.pathname;
    if (path.startsWith("/admin")) {
      initial = "admin";
    } else if (path.startsWith("/guilds")) {
      initial = "guilds";
    } else if (path.startsWith("/patches")) {
      initial = "patches";
    } else {
      try {
        const saved = localStorage.getItem("agora:initView");
        if (saved === "patches") { initial = "patches"; localStorage.removeItem("agora:initView"); }
      } catch (e) {}
    }
    activeKey = initial;
    if (initial === "patches" || initial === "posts") mainView.set(initial);
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

  let muteAlert = $state("");
  async function selectAndOpen(key: "post" | "patch") {
    // Check ban status before opening composer
    try {
      const res = await fetch("/api/v1/users/me/ban-status", { credentials: "include" });
      if (res.status === 403) {
        const data = await res.json();
        muteAlert = data.detail || "你的账号已被封禁";
        return;
      }
    } catch {}
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

  <!-- guilds shortcut (left) -->
  <a
    href="/guilds"
    class="pill-item pill-slot no-underline"
    class:is-active={activeKey === "guilds"}
    data-key="guilds"
    title="社团"
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
        d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
      /></svg
    >
    <span class="pill-tooltip">社团</span>
  </a>

  <div
    class="w-px h-5 mx-0.5 rounded-full"
    style="background: rgba(255,255,255,0.1);"
  ></div>

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
    class:banned={bannedPost}
    data-key="post"
    onclick={() => !bannedPost && selectAndOpen("post")}
    title={bannedPost ? "已被禁止发帖" : "发帖"}
  >
    <PlusIcon class="size-4.5" />
    <span class="pill-tooltip">{bannedPost ? "禁止发帖" : "发帖"}</span>
  </button>

  <!-- Admin -->
  <a
    href="/admin"
    class="pill-item pill-slot no-underline"
    class:is-active={activeKey === "admin"}
    data-key="admin"
    title="管理后台"
  >
    <ShieldIcon class="size-4.5" />
    <span class="pill-tooltip">管理后台</span>
  </a>

  {#if $currentUser}
    <button
      class="pill-item pill-slot"
      class:is-active={activeKey === "patch"}
      class:banned={bannedPatch}
      data-key="patch"
      onclick={() => !bannedPatch && selectAndOpen("patch")}
      title={bannedPatch ? "已被禁止发起变更" : "发起变更"}
    >
      <GitBranchIcon class="size-4.5" />
      <span class="pill-tooltip">{bannedPatch ? "禁止变更" : "发起变更"}</span>
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
            <div class="mb-1">{$currentUser.nickname ?? $currentUser.username}</div>
            <GuildBadge />
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

<GlassModal show={muteAlert !== ""} title="操作被禁止" onclose={() => muteAlert = ""}>
  <p style="color: var(--vercel-danger);">{muteAlert}</p>
  <p class="mt-3 text-xs" style="color: var(--vercel-text-tertiary);">如有疑问请联系管理员</p>
  <div style="display:flex;justify-content:flex-end;margin-top:1rem;">
    <button class="btn btn-ghost btn-sm" onclick={() => muteAlert = ""}>知道了</button>
  </div>
</GlassModal>

<style>
  .pill-slot.banned {
    opacity: 0.35 !important;
    cursor: not-allowed !important;
    pointer-events: none;
  }
  .pill-slot.banned svg {
    color: var(--vercel-danger) !important;
  }
</style>
