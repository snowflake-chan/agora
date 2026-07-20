<script lang="ts">
  import { GitBranchIcon, PlusIcon, UserIcon } from "@lucide/svelte";
  import { onMount, tick } from "svelte";
  import { translator } from "../lib/i18n";
  import {
    LOGIN_REQUEST_EVENT,
    type LoginRequestDetail,
  } from "../lib/login";
  import { safeReturnTo } from "../lib/returnTo";
  import { currentUser, initAuth } from "../stores/auth";
  import { mainView } from "../stores/nav";
  import LoginDialog from "./auth/LoginDialog.svelte";
  import PatchForm from "./patches/PatchForm.svelte";
  import PostForm from "./posts/PostForm.svelte";

  type ActiveKey = "posts" | "patches" | "post" | "patch" | "user" | null;

  let activeKey = $state<ActiveKey>(null);
  let showPostForm = $state(false);
  let showPatchForm = $state(false);
  let loginOpen = $state(false);
  let loginReturnTo = $state("/");
  let afterLogin = $state<(() => void) | null>(null);
  let authReady = $state(false);
  let trackEl = $state<HTMLDivElement | null>(null);
  let highlightEl = $state<HTMLDivElement | null>(null);

  onMount(async () => {
    await initAuth();
    authReady = true;
  });

  onMount(() => {
    let initial: ActiveKey = routeKey();
    try {
      const saved = localStorage.getItem("agora:initView");
      if (window.location.pathname === "/" && saved === "patches") {
        initial = "patches";
        localStorage.removeItem("agora:initView");
      }
    } catch {}
    activeKey = initial;
    mainView.set(initial === "patches" ? "patches" : "posts");
    requestAnimationFrame(updateHighlight);
  });

  onMount(() => {
    function handleLoginRequest(event: Event) {
      const detail = (event as CustomEvent<LoginRequestDetail>).detail;
      openLogin(detail?.returnTo, detail?.onAuthenticated);
    }

    function handleLoginLink(event: MouseEvent) {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }

      const anchor = (event.target as HTMLElement).closest<HTMLAnchorElement>("a[href]");
      if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download")) return;
      const target = new URL(anchor.href, window.location.origin);
      if (target.origin !== window.location.origin || target.pathname !== "/login") return;

      event.preventDefault();
      openLogin(target.searchParams.get("returnTo"));
    }

    window.addEventListener(LOGIN_REQUEST_EVENT, handleLoginRequest);
    document.addEventListener("click", handleLoginLink);
    return () => {
      window.removeEventListener(LOGIN_REQUEST_EVENT, handleLoginRequest);
      document.removeEventListener("click", handleLoginLink);
    };
  });

  async function updateHighlight() {
    await tick();
    if (!trackEl || !highlightEl) return;
    if (activeKey === null) {
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

  function routeKey(): ActiveKey {
    if (typeof window === "undefined") return "posts";
    const path = window.location.pathname;
    if (path === "/") return $mainView === "patches" ? "patches" : "posts";
    if (path.startsWith("/patches")) return "patches";
    if (path.startsWith("/posts")) return "posts";
    if (path === "/my" || path.startsWith("/users/")) return "user";
    return null;
  }

  function currentLocation() {
    return `${window.location.pathname}${window.location.search}${window.location.hash}`;
  }

  function switchView(key: "posts" | "patches") {
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
      openLogin(currentLocation(), () => selectAndOpen(key));
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

  function openLogin(
    requestedReturnTo?: string | null,
    onAuthenticated?: (() => void) | null,
  ) {
    loginReturnTo = safeReturnTo(
      requestedReturnTo || currentLocation(),
      window.location.origin,
    );
    afterLogin = onAuthenticated ?? null;
    activeKey = null;
    loginOpen = true;
  }

  function closeLogin() {
    activeKey = routeKey();
    afterLogin = null;
  }

  function handleAuthenticated() {
    const continuation = afterLogin;
    const destination = loginReturnTo;
    afterLogin = null;
    if (continuation) {
      continuation();
      return;
    }
    if (destination !== currentLocation()) {
      window.location.assign(destination);
      return;
    }
    activeKey = routeKey();
  }
</script>

<div class="pill-track" bind:this={trackEl}>
  <div class="pill-highlight is-hidden" bind:this={highlightEl}></div>

  <button
    class="pill-item pill-slot"
    class:is-active={activeKey === "posts"}
    data-key="posts"
    type="button"
    onclick={() => switchView("posts")}
    aria-label={$translator("nav.home")}
    title={$translator("nav.home")}
  >
    <svg class="size-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
    <span class="pill-tooltip">{$translator("nav.home")}</span>
    <span class="pill-label">{$translator("nav.home")}</span>
  </button>

  <button
    class="pill-item pill-slot"
    class:is-active={activeKey === "patches"}
    data-key="patches"
    type="button"
    onclick={() => switchView("patches")}
    aria-label={$translator("nav.changes")}
    title={$translator("nav.changes")}
  >
    <svg class="size-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
    </svg>
    <span class="pill-tooltip">{$translator("nav.changes")}</span>
    <span class="pill-label">{$translator("nav.changes")}</span>
  </button>

  <div class="pill-divider" aria-hidden="true"></div>

  <button
    class="pill-item pill-slot pill-create"
    class:is-active={activeKey === "post"}
    data-key="post"
    type="button"
    onclick={() => selectAndOpen("post")}
    aria-label={$translator("nav.newPost")}
    title={$translator("nav.newPost")}
  >
    <PlusIcon class="size-4.5" />
    <span class="pill-tooltip">{$translator("nav.newPost")}</span>
    <span class="pill-label">{$translator("nav.newPost")}</span>
  </button>

  <button
    class="pill-item pill-slot"
    class:is-active={activeKey === "patch"}
    data-key="patch"
    type="button"
    onclick={() => selectAndOpen("patch")}
    aria-label={$translator("nav.newChange")}
    title={$translator("nav.newChange")}
  >
    <GitBranchIcon class="size-4.5" />
    <span class="pill-tooltip">{$translator("nav.newChange")}</span>
    <span class="pill-label">{$translator("nav.newChange")}</span>
  </button>

  <div class="relative">
    {#if $currentUser}
      <a
        href={`/users/${$currentUser.id}`}
        class="pill-item pill-slot"
        class:is-active={activeKey === "user"}
        data-key="user"
        aria-label={$translator("nav.profile")}
        title={$translator("nav.profile")}
      >
        <span class="profile-avatar-chip">
          {($currentUser.nickname ?? $currentUser.username)[0].toUpperCase()}
        </span>
        <span class="pill-tooltip">{$translator("nav.profile")}</span>
        <span class="pill-label">{$translator("nav.profile")}</span>
      </a>
    {:else if authReady}
      <button
        type="button"
        class="pill-item pill-slot"
        data-key="login"
        aria-label={$translator("nav.login")}
        title={$translator("nav.login")}
        onclick={() => openLogin()}
      >
        <UserIcon class="size-4.5" />
        <span class="pill-tooltip">{$translator("nav.login")}</span>
        <span class="pill-label">{$translator("nav.login")}</span>
      </button>
    {:else}
      <span class="pill-item auth-pending" aria-hidden="true"></span>
    {/if}
  </div>
</div>

{#if showPostForm}
  <PostForm on:close={() => closeComposer("post")} />
{/if}
{#if showPatchForm}
  <PatchForm on:close={() => closeComposer("patch")} />
{/if}

<LoginDialog
  bind:open={loginOpen}
  returnTo={loginReturnTo}
  onClose={closeLogin}
  onAuthenticated={handleAuthenticated}
/>

<style>
  .pill-label {
    display: none;
    max-width: 4.5rem;
    overflow: hidden;
    font-size: 0.625rem;
    font-weight: 600;
    letter-spacing: 0;
    line-height: 1;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .pill-divider {
    width: 1px;
    height: 1.25rem;
    margin: 0 0.25rem;
    background: var(--vercel-border-hover);
  }

  .pill-create {
    color: var(--vercel-bg);
    background: var(--vercel-text);
  }

  .pill-create:hover {
    color: var(--vercel-bg);
    background: var(--vercel-text);
    transform: translateY(-1px);
  }

  .profile-avatar-chip {
    display: grid;
    width: 1.2rem;
    height: 1.2rem;
    place-items: center;
    border-radius: 38%;
    color: var(--vercel-bg);
    background: var(--vercel-text);
    font-size: 0.5rem;
    font-weight: 700;
  }

  .auth-pending::after {
    width: 0.85rem;
    height: 0.85rem;
    border: 1px solid var(--vercel-border-hover);
    border-top-color: var(--vercel-text-secondary);
    border-radius: 50%;
    content: "";
    animation: auth-spin 700ms linear infinite;
  }

  @keyframes auth-spin {
    to {
      transform: rotate(360deg);
    }
  }

  @media (max-width: 40rem) {
    .pill-tooltip,
    .pill-divider {
      display: none;
    }

    .pill-label {
      display: block;
    }

    :global(.pill-track) {
      width: 100%;
      justify-content: space-around;
      gap: 0.1rem;
    }

    :global(.pill-item) {
      width: auto;
      min-width: 3.1rem;
      height: 3rem;
      padding: 0.35rem 0.4rem;
      flex-direction: column;
      gap: 0.2rem;
      border-radius: 0.7rem;
    }

    .pill-create {
      min-width: 3.4rem;
      border-radius: 0.85rem;
      box-shadow: 0 0.35rem 1rem rgba(0, 0, 0, 0.28);
      transform: translateY(-0.18rem);
    }

    .pill-create:hover {
      transform: translateY(-0.25rem);
    }
  }
</style>
