<script lang="ts">
  import { onMount } from "svelte";
  import { fade, fly } from "svelte/transition";
  import { Clock3Icon, FlameIcon, SparklesIcon, UsersIcon } from "@lucide/svelte";
  import { appleEase } from "../lib/motion";
  import { translator } from "../lib/i18n";
  import { requestLogin } from "../lib/login";
  import { homeLayout, initPreferences } from "../lib/preferences";
  import { initAuth, currentUser } from "../stores/auth";
  import { mainView } from "../stores/nav";
  import FeedList from "./FeedList.svelte";
  import PatchList from "./patches/PatchList.svelte";
  import PostDetail from "./posts/PostDetail.svelte";
  import PatchDetail from "./patches/PatchDetail.svelte";
  import type { FeedItem, FeedMode } from "../lib/posts";

  let selected = $state<FeedItem | null>(null);
  let selectedPatch = $state<import("../lib/patches").Patch | null>(null);
  let feedState = $state<"loading" | "ready" | "empty" | "error">("loading");
  let patchState = $state<"loading" | "ready" | "empty" | "error">("loading");
  let feedMode = $state<FeedMode>("recommended");
  let authReady = $state(false);
  let desktopSplit = $state(false);
  let splitActive = $derived($homeLayout === "split" && desktopSplit);

  const feedModes: FeedMode[] = ["recommended", "trending", "following", "latest"];
  const modeKeys: Record<FeedMode, { label: string; title: string; description: string }> = {
    recommended: { label: "feed.recommended", title: "feed.recommendedTitle", description: "feed.recommendedDescription" },
    trending: { label: "feed.trending", title: "feed.trendingTitle", description: "feed.trendingDescription" },
    following: { label: "feed.following", title: "feed.followingTitle", description: "feed.followingDescription" },
    latest: { label: "feed.latest", title: "feed.latestTitle", description: "feed.latestDescription" },
  };

  onMount(() => {
    const splitQuery = window.matchMedia("(min-width: 64rem)");
    const syncSplit = () => (desktopSplit = splitQuery.matches);
    syncSplit();
    splitQuery.addEventListener("change", syncSplit);

    return () => splitQuery.removeEventListener("change", syncSplit);
  });

  onMount(async () => {
    initPreferences();
    try {
      const saved = localStorage.getItem("agora:feedMode") as FeedMode | null;
      if (saved && feedModes.includes(saved)) feedMode = saved;
    } catch {}
    const user = await initAuth();
    if (feedMode === "following" && !user) {
      feedMode = "recommended";
      try { localStorage.setItem("agora:feedMode", feedMode); } catch {}
    }
    authReady = true;
  });

  function selectItem(item: FeedItem) {
    selected = item;
  }

  function syncSelection(items: FeedItem[]) {
    if (!selected) {
      if (items[0]) selected = items[0];
      return;
    }
    const updated = items.find((item) => item.id === selected?.id);
    if (updated) selected = updated;
  }

  function syncPatchSelection(items: import("../lib/patches").Patch[]) {
    if (!selectedPatch) {
      if (items[0]) selectedPatch = items[0];
      return;
    }
    const updated = items.find((item) => item.id === selectedPatch?.id);
    selectedPatch = updated ?? items[0] ?? null;
  }

  async function selectMode(next: FeedMode) {
    if (next === "following") {
      const user = authReady ? $currentUser : await initAuth();
      if (!user) {
        requestLogin("/", () => selectMode(next));
        return;
      }
    }
    selected = null;
    feedState = "loading";
    feedMode = next;
    try { localStorage.setItem("agora:feedMode", next); } catch {}
  }
</script>

<div class="main-view">
  {#if $mainView === "posts"}
    <div class="view-pane" in:fly={{ y: 12, duration: 320, easing: appleEase }} out:fade={{ duration: 140 }}>
      <div class="stream-heading">
        <div>
          <p class="view-kicker">{$translator("home.kicker")}</p>
          <h1 class="view-title">{$translator(modeKeys[feedMode].title)}</h1>
        </div>
        <p class="view-description">{$translator(modeKeys[feedMode].description)}</p>
      </div>
      <div class="workspace-shell" class:page-layout={$homeLayout === "pages"}>
        <div class="feed-toolbar">
          <div class="feed-tabs" role="tablist" aria-label={$translator("feed.sorting")}>
            {#each feedModes as mode}
              <button
                type="button"
                class:active={feedMode === mode}
                role="tab"
                aria-selected={feedMode === mode}
                title={$translator(modeKeys[mode].description)}
                onclick={() => selectMode(mode)}
              >
                {#if mode === "recommended"}
                  <SparklesIcon size={15} strokeWidth={1.8} />
                {:else if mode === "trending"}
                  <FlameIcon size={15} strokeWidth={1.8} />
                {:else if mode === "following"}
                  <UsersIcon size={15} strokeWidth={1.8} />
                {:else}
                  <Clock3Icon size={15} strokeWidth={1.8} />
                {/if}
                <span>{$translator(modeKeys[mode].label)}</span>
              </button>
            {/each}
          </div>
        </div>
        <div class="workspace-grid">
          <section class="stream-panel" aria-label={$translator("home.activity")}>
            {#if authReady}
              {#key feedMode}
                <FeedList
                  mode={feedMode}
                  onSelect={splitActive ? selectItem : null}
                  selectedId={splitActive ? selected?.id ?? null : null}
                  onFirstItem={splitActive ? (item) => selected ??= item : null}
                  onItemsUpdated={splitActive ? syncSelection : null}
                  onStateChange={(state) => feedState = state}
                />
              {/key}
            {:else}
              <div class="empty-state"><div class="spinner mb-3"></div>{$translator("feed.loading")}</div>
            {/if}
          </section>
          {#if $homeLayout === "split"}
            <section class="detail-panel" aria-label={$translator("home.select")}>
            {#if splitActive && selected}
              {#key `${selected.id}:v${selected.revision_number}:${selected.reply_count}:${selected.like_count}:${selected.for_count}:${selected.against_count}:${selected.status}:${selected.moderation_status ?? ""}:${selected.moderation_reason ?? ""}:${selected.poll?.total_votes ?? 0}:${selected.poll?.selected_option_id ?? ""}:${selected.poll?.is_closed ? 1 : 0}`}
                {#if selected.type === "post"}
                  <PostDetail postId={selected.id} embedded />
                {:else}
                  <PatchDetail patchId={selected.id} embedded />
                {/if}
              {/key}
            {:else if !splitActive || feedState === "loading"}
              <div class="detail-loading" aria-label={$translator("home.loading")} aria-live="polite">
                <span></span><span></span><span></span><span></span>
                <p>{$translator("home.loading")}</p>
              </div>
            {:else}
              <div class="detail-empty">
                <span class="detail-empty-mark" aria-hidden="true">→</span>
                <p>{feedState === "empty" ? $translator("home.empty") : $translator("home.select")}</p>
              </div>
            {/if}
            </section>
          {/if}
        </div>
      </div>
    </div>
  {:else}
    <div class="view-pane" in:fly={{ y: 12, duration: 320, easing: appleEase }} out:fade={{ duration: 140 }}>
      <div class="stream-heading">
        <div>
          <p class="view-kicker">{$translator("home.kicker")}</p>
          <h1 class="view-title">{$translator("nav.changes")}</h1>
        </div>
        <p class="view-description">{$translator("patch.pageDescription")}</p>
      </div>
      <div class="workspace-shell" class:page-layout={$homeLayout === "pages"}>
        <div class="workspace-grid">
          <section class="stream-panel" aria-label={$translator("nav.changes")}>
            <PatchList
              onSelect={splitActive ? (patch) => selectedPatch = patch : null}
              selectedId={splitActive ? selectedPatch?.id ?? null : null}
              onFirstItem={splitActive ? (patch) => selectedPatch ??= patch : null}
              onItemsUpdated={splitActive ? syncPatchSelection : null}
              onStateChange={(state) => patchState = state}
            />
          </section>
          {#if $homeLayout === "split"}
            <section class="detail-panel" aria-label={$translator("home.select")}>
              {#if patchState === "loading"}
                <div class="detail-loading" aria-label={$translator("home.loading")} aria-live="polite">
                  <span></span><span></span><span></span><span></span>
                  <p>{$translator("home.loading")}</p>
                </div>
              {:else if splitActive && selectedPatch}
                {#key `${selectedPatch.id}:v${selectedPatch.revision_number}:${selectedPatch.status}:${selectedPatch.for_count}:${selectedPatch.against_count}:${selectedPatch.comment_count}`}
                  <PatchDetail patchId={selectedPatch.id} embedded />
                {/key}
              {:else}
                <div class="detail-empty">
                  <span class="detail-empty-mark" aria-hidden="true">#</span>
                  <p>{patchState === "empty" ? $translator("patch.empty") : $translator("home.select")}</p>
                </div>
              {/if}
            </section>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .main-view { position: relative; min-height: 60vh; }
  .view-pane { position: absolute; inset: 0; width: 100%; }
  .view-title { color: var(--vercel-text); font-size: clamp(1.5rem, 2vw, 2rem); font-weight: 650; letter-spacing: 0; }
  .stream-heading { display: flex; align-items: end; justify-content: space-between; gap: 2rem; margin-bottom: 1.25rem; }
  .feed-toolbar { display: flex; min-height: 3rem; padding: .45rem .55rem; align-items: center; justify-content: flex-start; border-bottom: 1px solid var(--vercel-border); background: color-mix(in srgb, var(--vercel-surface) 72%, transparent); }
  .feed-tabs { display: inline-flex; align-items: center; gap: .2rem; padding: .2rem; border-radius: var(--vercel-radius-sm); background: var(--vercel-surface-muted); }
  .feed-tabs button { display: inline-flex; min-height: 2rem; padding: .35rem .7rem; align-items: center; gap: .4rem; border: 0; border-radius: var(--vercel-radius-sm); background: transparent; color: var(--vercel-text-tertiary); cursor: pointer; font: inherit; font-size: .75rem; font-weight: 600; white-space: nowrap; transition: color .18s ease, background-color .18s ease, box-shadow .18s ease; }
  .feed-tabs button:hover { color: var(--vercel-text); background: var(--vercel-hover); }
  .feed-tabs button.active { color: var(--vercel-text); background: var(--vercel-hover-strong); box-shadow: inset 0 0 0 1px var(--vercel-border); }
  .view-kicker { margin-bottom: .25rem; color: var(--vercel-text-tertiary); font-size: .6875rem; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
  .view-description { max-width: 24rem; color: var(--vercel-text-tertiary); font-size: .8125rem; line-height: 1.5; text-align: right; }
  .workspace-shell { display:flex; height:min(52rem,calc(100dvh - 15rem)); min-height:32rem; overflow:hidden; flex-direction:column; border:1px solid var(--vercel-border); border-radius:var(--vercel-radius-lg); background:color-mix(in srgb,var(--vercel-card) 86%,transparent); box-shadow:0 1.25rem 4rem color-mix(in srgb,var(--vercel-bg) 48%,transparent); }
  .workspace-grid { display:grid; min-height:0; flex:1; grid-template-columns:minmax(19rem,24rem) minmax(0,1fr); overflow:hidden; }
  .workspace-shell.page-layout { width:100%; max-width:52rem; height:auto; min-height:0; margin-right:auto; overflow:visible; }
  .workspace-shell.page-layout .workspace-grid { grid-template-columns:minmax(0,1fr); overflow:visible; }
  .workspace-shell.page-layout .stream-panel { overflow:visible; border-right:0; }
  .stream-panel { min-width: 0; overflow-y: auto; border-right: 1px solid var(--vercel-border); background: color-mix(in srgb, var(--vercel-bg) 72%, transparent); }
  .detail-panel { min-width: 0; overflow-y: auto; padding: clamp(1.25rem, 2.5vw, 2.5rem); }
  .detail-empty { display: grid; min-height: 60vh; place-content: center; justify-items: center; gap: 1rem; color: var(--vercel-text-tertiary); font-size: .875rem; text-align: center; }
  .detail-empty-mark { display: grid; width: 3rem; height: 3rem; place-items: center; border: 1px solid var(--vercel-border); border-radius: var(--vercel-radius); color: var(--vercel-text-secondary); font-size: 1.125rem; font-weight: 650; }
  .detail-loading { display: grid; max-width: 32rem; min-height: 60vh; margin: auto; align-content: center; gap: .75rem; color: var(--vercel-text-tertiary); font-size: .75rem; }
  .detail-loading span { display: block; height: .75rem; border-radius: var(--vercel-radius-sm); background: var(--vercel-surface-muted); animation: pulse 1.4s ease-in-out infinite; }
  .detail-loading span:nth-child(1) { width: 42%; height: 1.4rem; }
  .detail-loading span:nth-child(2) { width: 100%; }
  .detail-loading span:nth-child(3) { width: 92%; }
  .detail-loading span:nth-child(4) { width: 68%; }
  @keyframes pulse { 50% { opacity: .45; } }
  @media (max-width: 63.99rem) {
    .stream-heading { align-items: start; flex-direction: column; gap: .5rem; }
    .view-description { text-align: left; }
    .feed-toolbar { overflow: hidden; }
    .feed-tabs { display: grid; width: 100%; grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .feed-tabs button { min-width: 0; padding-inline: .15rem; justify-content: center; gap: .25rem; font-size: .6875rem; }
    .workspace-shell { height:auto; min-height:0; overflow:visible; }
    .workspace-grid { display:block; overflow:visible; }
    .stream-panel { overflow: visible; border-right: 0; }
    .detail-panel { display: none; }
  }

  @media (max-width: 22.5rem) {
    .feed-tabs button :global(svg) { display: none; }
  }
</style>
