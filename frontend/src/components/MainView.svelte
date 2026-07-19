<script lang="ts">
  import { fly, fade } from "svelte/transition";
  import { appleEase } from "../lib/motion";
  import { mainView } from "../stores/nav";
  import FeedList from "./FeedList.svelte";
  import PatchList from "./patches/PatchList.svelte";
  import PostDetail from "./posts/PostDetail.svelte";
  import PatchDetail from "./patches/PatchDetail.svelte";
  import type { FeedItem } from "../lib/posts";

  let selected = $state<FeedItem | null>(null);
  let feedState = $state<"loading" | "ready" | "empty" | "error">("loading");

  function selectItem(item: FeedItem) {
    selected = item;
  }
</script>

<div class="main-view">
  {#if $mainView === "posts"}
    <div
      class="view-pane"
      in:fly={{ y: 12, duration: 320, easing: appleEase }}
      out:fade={{ duration: 140 }}
    >
      <div class="stream-heading">
        <div>
          <p class="view-kicker">Agora</p>
          <h1 class="view-title">最新动态</h1>
        </div>
        <p class="view-description">帖子、变更与讨论，按时间汇集在一起。</p>
      </div>
      <div class="workspace-grid">
        <section class="stream-panel" aria-label="最新动态列表">
          <FeedList onSelect={selectItem} selectedId={selected?.id ?? null} onFirstItem={(item) => selected ??= item} onStateChange={(state) => feedState = state} />
        </section>
        <section class="detail-panel" aria-label="内容详情">
          {#if selected}
            {#key selected.id}
              {#if selected.type === "post"}
                <PostDetail postId={selected.id} embedded />
              {:else}
                <PatchDetail patchId={selected.id} embedded />
              {/if}
            {/key}
          {:else}
            {#if feedState === "loading"}
              <div class="detail-loading" aria-label="正在加载详情" aria-live="polite">
                <span></span><span></span><span></span><span></span>
                <p>正在加载详情</p>
              </div>
            {:else}
              <div class="detail-empty">
                <span class="detail-empty-mark" aria-hidden="true">↗</span>
                <p>{feedState === "empty" ? "还没有动态，发布第一条讨论吧。" : "选择一条动态，在这里阅读完整内容。"}</p>
              </div>
            {/if}
          {/if}
        </section>
      </div>
    </div>
  {:else}
    <div
      class="view-pane"
      in:fly={{ y: 12, duration: 320, easing: appleEase }}
      out:fade={{ duration: 140 }}
    >
      <h1 class="view-title">变更</h1>
      <div class="card overflow-hidden">
        <PatchList />
      </div>
    </div>
  {/if}
</div>

<style>
  .main-view {
    position: relative;
    min-height: 60vh;
  }

  .view-pane {
    position: absolute;
    inset: 0;
    width: 100%;
  }

  .view-title {
    font-size: clamp(1.5rem, 2vw, 2rem);
    font-weight: 650;
    color: var(--vercel-text);
    letter-spacing: -0.04em;
  }

  .stream-heading {
    display: flex;
    align-items: end;
    justify-content: space-between;
    gap: 2rem;
    margin-bottom: 1.25rem;
  }

  .view-kicker {
    margin-bottom: 0.25rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .view-description {
    max-width: 24rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.8125rem;
    line-height: 1.5;
    text-align: right;
  }

  .workspace-grid {
    display: grid;
    grid-template-columns: minmax(19rem, 24rem) minmax(0, 1fr);
    height: min(52rem, calc(100dvh - 11rem));
    min-height: 38rem;
    overflow: hidden;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius-lg);
    background: rgba(18, 18, 20, 0.7);
  }

  .stream-panel {
    min-width: 0;
    overflow-y: auto;
    border-right: 1px solid var(--vercel-border);
    background: rgba(12, 12, 14, 0.72);
  }

  .detail-panel {
    min-width: 0;
    overflow-y: auto;
    padding: clamp(1.25rem, 2.5vw, 2.5rem);
  }

  .detail-empty {
    display: grid;
    min-height: 60vh;
    place-content: center;
    justify-items: center;
    gap: 1rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.875rem;
  }

  .detail-empty-mark {
    display: grid;
    width: 3rem;
    height: 3rem;
    place-items: center;
    border: 1px solid var(--vercel-border);
    border-radius: 0.875rem;
    color: var(--vercel-text-secondary);
    font-size: 1.125rem;
    font-weight: 650;
  }

  .detail-loading { display:grid; min-height:60vh; align-content:center; gap:.75rem; max-width:32rem; margin:auto; color:var(--vercel-text-tertiary); font-size:.75rem; }
  .detail-loading span { display:block; height:.75rem; border-radius:.3rem; background:rgba(255,255,255,.06); animation:pulse 1.4s ease-in-out infinite; }
  .detail-loading span:nth-child(1) { width:42%; height:1.4rem; }
  .detail-loading span:nth-child(2) { width:100%; }
  .detail-loading span:nth-child(3) { width:92%; }
  .detail-loading span:nth-child(4) { width:68%; }
  @keyframes pulse { 50% { opacity:.45; } }

  @media (max-width: 63.99rem) {
    .stream-heading {
      align-items: start;
      flex-direction: column;
      gap: 0.5rem;
    }

    .view-description {
      text-align: left;
    }

    .workspace-grid {
      display: block;
      height: auto;
      min-height: 0;
    }

    .stream-panel {
      overflow: visible;
      border-right: 0;
    }

    .detail-panel {
      display: none;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .view-pane {
      animation: none !important;
      transition: none !important;
    }
  }
</style>
