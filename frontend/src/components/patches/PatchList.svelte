<script lang="ts">
  import { onMount } from "svelte";
  import { translator } from "../../lib/i18n";
  import { listPatches, type Patch } from "../../lib/patches";
  import PatchCard from "./PatchCard.svelte";

  let {
    initialStatus = undefined,
    onSelect = null,
    selectedId = null,
    onFirstItem = null,
    onItemsUpdated = null,
    onStateChange = null,
  }: {
    initialStatus?: string;
    onSelect?: ((patch: Patch) => void) | null;
    selectedId?: string | null;
    onFirstItem?: ((patch: Patch) => void) | null;
    onItemsUpdated?: ((patches: Patch[]) => void) | null;
    onStateChange?: ((state: "loading" | "ready" | "empty" | "error") => void) | null;
  } = $props();

  // ---- reactive state (all use $state for Svelte 5 runes mode) ----
  let patches = $state<Patch[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let activeFilter = $state(initialStatus ?? "");

  const FILTERS: { key: string; value: string }[] = [
    { key: "common.all", value: "" },
    { key: "status.voting", value: "voting" },
    { key: "status.merged", value: "merged" },
    { key: "status.rejected", value: "rejected" },
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
    onStateChange?.("loading");

    try {
      patches = await listPatches(1, activeFilter || undefined, abortCtrl.signal);
      onItemsUpdated?.(patches);
      if (patches[0]) onFirstItem?.(patches[0]);
      onStateChange?.(patches.length > 0 ? "ready" : "empty");
    } catch (e: any) {
      if (e?.name === "AbortError") return; // cancelled, leaving previous state
      patches = [];
      onItemsUpdated?.([]);
      error = "PATCH_LOAD_FAILED";
      onStateChange?.("error");
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
<div class="patch-filters" style="border-color: var(--vercel-border);">
  {#each FILTERS as f}
    <button
      class="filter-tab"
      class:active={activeFilter === f.value}
      onclick={() => switchFilter(f.value)}
    >
      {$translator(f.key)}
    </button>
  {/each}
</div>

{#if loading}
  <div class="empty-state">
    <div class="spinner mb-3"></div>
    {$translator("common.loading")}
  </div>
{:else if error}
  <div class="empty-state">
    <p style="color: var(--vercel-danger);">{$translator("patch.loadFailed")}</p>
    <button class="btn btn-ghost btn-sm mt-3" onclick={() => loadPatches()}>{$translator("common.retry")}</button>
  </div>
{:else if patches.length === 0}
  <div class="empty-state">
    <p>{$translator("patch.empty")}</p>
    <a href="/patches/new" class="btn btn-ghost btn-sm mt-3">{$translator("patch.first")}</a>
  </div>
{:else}
  {#each patches as patch (patch.id)}
    <PatchCard
      {patch}
      selected={selectedId === patch.id}
      onSelect={onSelect}
    />
  {/each}
{/if}

<style>
  .patch-filters {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.15rem;
    padding: 0.4rem 0.5rem 0;
    border-bottom: 1px solid var(--vercel-border);
  }

  .patch-filters :global(.filter-tab) {
    min-width: 0;
    padding-inline: 0.25rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
