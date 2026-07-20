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
    title={$translator("nav.home")}
  >
    <svg class="size-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
    <span class="pill-tooltip">{$translator("nav.home")}</span>
  </button>

  <button
    class="pill-item pill-slot"
    class:is-active={activeKey === "patches"}
    data-key="patches"
    type="button"
    onclick={() => switchView("patches")}
    title={$translator("nav.changes")}
  >
    <svg class="size-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
    </svg>
    <span class="pill-tooltip">{$translator("nav.changes")}</span>
  </button>

  <div class="mx-1 h-5 w-px rounded-full" style="background: var(--vercel-border-hover);" aria-hidden="true"></div>

  <button
    class="pill-item pill-slot"
    class:is-active={activeKey === "post"}
    data-key="post"
    type="button"
    onclick={() => selectAndOpen("post")}
    title={$translator("nav.newPost")}
  >
    <PlusIcon class="size-4.5" />
    <span class="pill-tooltip">{$translator("nav.newPost")}</span>
  </button>

  <button
    class="pill-item pill-slot"
    class:is-active={activeKey === "patch"}
    data-key="patch"
    type="button"
    onclick={() => selectAndOpen("patch")}
    title={$translator("nav.newChange")}
  >
    <GitBranchIcon class="size-4.5" />
    <span class="pill-tooltip">{$translator("nav.newChange")}</span>
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
</style>
