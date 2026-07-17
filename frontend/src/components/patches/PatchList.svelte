<script lang="ts">
  import { onMount } from "svelte";
  import { listPatches, type Patch } from "../../lib/patches";
  import PatchCard from "./PatchCard.svelte";

  export let initialStatus: string | undefined = undefined;

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
<div class="flex gap-1 border-b border-surface-200-800/50 px-4 pt-2">
  {#each FILTERS as f}
    <button
      class="px-3 py-2 text-sm transition-colors {activeFilter === f.value
        ? 'border-b-2 border-primary-500 font-medium text-primary-600'
        : 'text-surface-500 hover:text-surface-700'}"
      on:click={() => switchFilter(f.value)}
    >
      {f.label}
    </button>
  {/each}
</div>

{#if loading}
  <div class="flex justify-center py-12 text-sm text-surface-400">加载中…</div>
{:else if patches.length === 0}
  <div class="flex flex-col items-center justify-center py-12 text-sm text-surface-400">
    <p>还没有变更</p>
    <a href="/patches/new" class="mt-2 text-primary-600 hover:text-primary-700">发起第一个</a>
  </div>
{:else}
  {#each patches as patch (patch.id)}
    <PatchCard {patch} />
  {/each}
{/if}
