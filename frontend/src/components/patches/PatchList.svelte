<script lang="ts">
  import { onMount } from "svelte";
  import { listPatches, type Patch } from "../../lib/patches";
  import PatchCard from "./PatchCard.svelte";

  let { initialStatus = undefined as string | undefined }: { initialStatus?: string } = $props();

  // ---- reactive state (all use $state for Svelte 5 runes mode) ----
  let patches = $state<Patch[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let activeFilter = $state(initialStatus ?? "");

  const FILTERS: { label: string; value: string }[] = [
    { label: "全部", value: "" },
    { label: "投票中", value: "voting" },
    { label: "已通过", value: "merged" },
    { label: "未通过", value: "rejected" },
  ];

  // ---- data loading ----
  let abortCtrl: AbortController | null = null;

  onMount(() => {
    loadPatches();
  });

  async function loadPatches() {
    // Cancel any in-flight request so rapid filter switching works correctly.
    abortCtrl?.abort();
    abortCtrl = new AbortController();

    loading = true;
    error = null;

    try {
      patches = await listPatches(1, activeFilter || undefined, abortCtrl.signal);
    } catch (e: any) {
      if (e?.name === "AbortError") return; // cancelled, leaving previous state
      patches = [];
      error = e instanceof Error ? e.message : "加载失败，请确认后端服务已启动";
    } finally {
      // Only clear loading if this is still the active controller.
      if (abortCtrl && !abortCtrl.signal.aborted) {
        loading = false;
      }
    }
  }

  function switchFilter(value: string) {
    activeFilter = value;
    loadPatches();
  }
</script>

<!-- Filter tabs -->
<div class="flex gap-1 px-4 pt-2 border-b" style="border-color: var(--vercel-border);">
  {#each FILTERS as f}
    <button
      class="filter-tab"
      class:active={activeFilter === f.value}
      onclick={() => switchFilter(f.value)}
    >
      {f.label}
    </button>
  {/each}
</div>

{#if loading}
  <div class="empty-state">
    <div class="spinner mb-3"></div>
    加载中...
  </div>
{:else if error}
  <div class="empty-state">
    <p style="color: var(--vercel-danger);">{error}</p>
    <button class="btn btn-ghost btn-sm mt-3" onclick={() => loadPatches()}>重试</button>
  </div>
{:else if patches.length === 0}
  <div class="empty-state">
    <p>还没有变更</p>
    <a href="/patches/new" class="btn btn-ghost btn-sm mt-3">发起第一个</a>
  </div>
{:else}
  {#each patches as patch (patch.id)}
    <PatchCard {patch} />
  {/each}
{/if}
