<script lang="ts">
  import {
    Code2Icon,
    GitBranchIcon,
    MessageCircleIcon,
    PlusIcon,
    ShieldIcon,
    UserIcon,
    UsersRoundIcon,
  } from "@lucide/svelte";
  import { onMount, tick } from "svelte";
  import { translator } from "../lib/i18n";
  import {
    LOGIN_REQUEST_EVENT,
    type LoginRequestDetail,
  } from "../lib/login";
  import { safeReturnTo } from "../lib/returnTo";
  import { avatarInitial } from "../lib/utils";
  import { currentUser, initAuth } from "../stores/auth";
  import { mainView } from "../stores/nav";
  import LoginDialog from "./auth/LoginDialog.svelte";
  import GlassModal from "./GlassModal.svelte";
  import PatchForm from "./patches/PatchForm.svelte";
  import PostForm from "./posts/PostForm.svelte";

  type ActiveKey =
    | "posts"
    | "patches"
    | "post"
    | "patch"
    | "guilds"
    | "admin"
    | "user"
    | null;

  let activeKey = $state<ActiveKey>(null);
  let showPostForm = $state(false);
  let showPatchForm = $state(false);
  let loginOpen = $state(false);
  let loginReturnTo = $state("/");
  let afterLogin = $state<(() => void) | null>(null);
  let authReady = $state(false);
  let bannedPost = $state(false);
  let bannedPatch = $state(false);
  let restrictionKey = $state<"post" | "patch" | null>(null);
  let trackEl = $state<HTMLDivElement | null>(null);
  let highlightEl = $state<HTMLDivElement | null>(null);
  let highlightFrame: number | null = null;
  let layoutObserver: ResizeObserver | null = null;
  let mutationObserver: MutationObserver | null = null;

  onMount(async () => {
    await initAuth();
    await refreshBanTypes();
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
    scheduleHighlight();
  });

  onMount(() => {
    const handleLayoutChange = () => scheduleHighlight();
    window.addEventListener("resize", handleLayoutChange);

    if (trackEl && "ResizeObserver" in window) {
      layoutObserver = new ResizeObserver(handleLayoutChange);
      layoutObserver.observe(trackEl);
    }
    if (trackEl && "MutationObserver" in window) {
      mutationObserver = new MutationObserver(handleLayoutChange);
      mutationObserver.observe(trackEl, {
        childList: true,
        subtree: true,
      });
    }

    return () => {
      window.removeEventListener("resize", handleLayoutChange);
      layoutObserver?.disconnect();
      mutationObserver?.disconnect();
      layoutObserver = null;
      mutationObserver = null;
      if (highlightFrame !== null) {
        cancelAnimationFrame(highlightFrame);
        highlightFrame = null;
      }
    };
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

  function scheduleHighlight() {
    if (typeof window === "undefined" || highlightFrame !== null) return;
    highlightFrame = window.requestAnimationFrame(() => {
      highlightFrame = null;
      void updateHighlight();
    });
  }

  $effect(() => {
    void activeKey;
    void authReady;
    void $currentUser?.id;
    void $currentUser?.role;
    scheduleHighlight();
  });

  function routeKey(): ActiveKey {
    if (typeof window === "undefined") return "posts";
    const path = window.location.pathname;
    if (path === "/") return $mainView === "patches" ? "patches" : "posts";
    if (path.startsWith("/patches")) return "patches";
    if (path.startsWith("/posts")) return "posts";
    if (path.startsWith("/guilds")) return "guilds";
    if (path.startsWith("/admin")) return "admin";
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
    await refreshBanTypes();
    if ((key === "post" && bannedPost) || (key === "patch" && bannedPatch)) {
      restrictionKey = key;
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

  async function refreshBanTypes() {
    if (!$currentUser) {
      bannedPost = false;
      bannedPatch = false;
      return;
    }
    try {
      const response = await fetch("/api/v1/users/me/ban-types", {
        credentials: "include",
      });
      if (!response.ok) return;
      const restrictions = await response.json();
      bannedPost = Boolean(restrictions.ban_user || restrictions.mute_post);
      bannedPatch = Boolean(restrictions.ban_user || restrictions.mute_patch);
    } catch {}
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
      activeKey = routeKey();
      scheduleHighlight();
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
    <MessageCircleIcon class="size-4.5" aria-hidden="true" />
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
    <Code2Icon class="size-4.5" aria-hidden="true" />
    <span class="pill-tooltip">{$translator("nav.changes")}</span>
    <span class="pill-label">{$translator("nav.changes")}</span>
  </button>

  <div class="pill-divider" aria-hidden="true"></div>

  <button
    class="pill-item pill-slot pill-create"
    class:is-active={activeKey === "post"}
    class:is-restricted={bannedPost}
    data-key="post"
    type="button"
    onclick={() => selectAndOpen("post")}
    aria-label={$translator("nav.newPost")}
    aria-disabled={bannedPost}
    title={$translator(bannedPost ? "moderation.mutedPost" : "nav.newPost")}
  >
    <PlusIcon class="size-4.5" />
    <span class="pill-tooltip">{$translator(bannedPost ? "moderation.mutedPost" : "nav.newPost")}</span>
    <span class="pill-label">{$translator("nav.publish")}</span>
  </button>

  <button
    class="pill-item pill-slot"
    class:is-active={activeKey === "patch"}
    class:is-restricted={bannedPatch}
    data-key="patch"
    type="button"
    onclick={() => selectAndOpen("patch")}
    aria-label={$translator("nav.newChange")}
    aria-disabled={bannedPatch}
    title={$translator(bannedPatch ? "moderation.mutedPatch" : "nav.newChange")}
  >
    <GitBranchIcon class="size-4.5" />
    <span class="pill-tooltip">{$translator(bannedPatch ? "moderation.mutedPatch" : "nav.newChange")}</span>
    <span class="pill-label">{$translator("nav.propose")}</span>
  </button>

  <a
    href="/guilds"
    class="pill-item pill-slot"
    class:is-active={activeKey === "guilds"}
    data-key="guilds"
    aria-label={$translator("nav.guilds")}
    title={$translator("nav.guilds")}
  >
    <UsersRoundIcon class="size-4.5" />
    <span class="pill-tooltip">{$translator("nav.guilds")}</span>
    <span class="pill-label">{$translator("nav.guilds")}</span>
  </a>

  {#if $currentUser?.role === "moderator" || $currentUser?.role === "super_admin"}
    <a
      href="/admin"
      class="pill-item pill-slot"
      class:is-active={activeKey === "admin"}
      data-key="admin"
      aria-label={$translator("nav.admin")}
      title={$translator("nav.admin")}
    >
      <ShieldIcon class="size-4.5" />
      <span class="pill-tooltip">{$translator("nav.admin")}</span>
      <span class="pill-label">{$translator("nav.admin")}</span>
    </a>
  {/if}

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
        {avatarInitial($currentUser.nickname, $currentUser.username)}
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

{#if showPostForm}
  <PostForm onClose={() => closeComposer("post")} />
{/if}
{#if showPatchForm}
  <PatchForm onClose={() => closeComposer("patch")} />
{/if}

<LoginDialog
  bind:open={loginOpen}
  returnTo={loginReturnTo}
  onClose={closeLogin}
  onAuthenticated={handleAuthenticated}
/>

<GlassModal
  show={restrictionKey !== null}
  title={$translator("moderation.restrictedTitle")}
  onclose={() => (restrictionKey = null)}
>
  <p>
    {$translator(
      restrictionKey === "patch"
        ? "moderation.mutedPatch"
        : "moderation.mutedPost",
    )}
  </p>
  <p class="restriction-help">{$translator("moderation.contactAdmin")}</p>
  <div class="restriction-actions">
    <button class="btn btn-primary btn-sm" onclick={() => (restrictionKey = null)}>
      {$translator("common.confirm")}
    </button>
  </div>
</GlassModal>

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
    color: var(--vercel-accent-foreground);
    background: var(--vercel-accent);
  }

  .pill-create:hover {
    color: var(--vercel-accent-foreground);
    background: var(--vercel-accent-hover);
    transform: translateY(-1px);
  }

  .pill-item.is-restricted,
  .pill-item.is-restricted:hover {
    color: var(--vercel-danger);
    background: color-mix(in srgb, var(--vercel-danger) 10%, transparent);
  }

  .restriction-help {
    margin-top: 0.5rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
  }

  .restriction-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 1rem;
  }

  .profile-avatar-chip {
    display: grid;
    width: 1.2rem;
    height: 1.2rem;
    place-items: center;
    border-radius: 38%;
    color: var(--vercel-accent-foreground);
    background: var(--vercel-accent);
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
    /* Labels are intentionally not part of the compact navigation layout. */
    .pill-label,
    .pill-tooltip {
      display: none;
    }

    .pill-create {
      border-radius: 0.85rem;
      box-shadow: 0 0.35rem 1rem rgba(0, 0, 0, 0.28);
      transform: none;
    }

    .pill-create:hover {
      transform: none;
    }
  }
</style>
