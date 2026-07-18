<script lang="ts">
  import { onMount } from "svelte";
  import { listPatches, type Patch } from "../../lib/patches";
  import PatchCard from "./PatchCard.svelte";

  let { initialStatus = undefined as string | undefined }: { initialStatus?: string } = $props();

  let patches: Patch[] = [];
  let loading = true;
  let activeFilter = initialStatus ?? "";

  const FILTERS: { label: string; value: string }[] = [
    { label: "全部", value: "" },
    { label: "投票中", value: "voting" },
    { label: "已通过", value: "merged" },
    { label: "未通过", value: "rejected" },
  ];

  onMount(async () => {
    await loadPatches();
  });

  async function loadPatches() {
    loading = true;
    try {
      patches = await listPatches(1, activeFilter || undefined);
    } catch {
      patches = [];
    } finally {
      loading = false;
    }
  }

  async function switchFilter(value: string) {
    activeFilter = value;
    await loadPatches();
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