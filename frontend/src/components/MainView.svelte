<script lang="ts">
  import { fly, fade } from "svelte/transition";
  import { appleEase } from "../lib/motion";
  import { mainView } from "../stores/nav";
  import FeedList from "./FeedList.svelte";
  import PatchList from "./patches/PatchList.svelte";
</script>

<div class="main-view">
  {#if $mainView === "posts"}
    <div
      class="view-pane"
      in:fly={{ y: 12, duration: 320, easing: appleEase }}
      out:fade={{ duration: 140 }}
    >
      <h1 class="view-title">最新动态</h1>
      <div class="card overflow-hidden">
        <FeedList />
      </div>
    </div>
  {:else}
    <div
      class="view-pane"
      in:fly={{ y: 12, duration: 320, easing: appleEase }}
      out:fade={{ duration: 140 }}
    >
      <div class="mb-6 flex items-center justify-between">
        <h1 class="view-title">变更</h1>
        <a href="/patches/new" class="btn btn-primary btn-sm">发起变更</a>
      </div>
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
    margin-bottom: 1.5rem;
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--vercel-text);
  }

  @media (prefers-reduced-motion: reduce) {
    .view-pane {
      animation: none !important;
      transition: none !important;
    }
  }
</style>
