<script lang="ts">
  import { fade, scale } from "svelte/transition";

  let { show = false, title = "", onclose = () => {}, children }: { show: boolean; title?: string; onclose?: () => void; children?: any } = $props();

  function onKeydown(e: KeyboardEvent) {
    if (e.key === "Escape" && show) onclose();
  }
</script>

<svelte:window onkeydown={onKeydown} />

{#if show}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="modal-backdrop"
    onclick={onclose}
    onkeydown={() => {}}
    transition:fade={{ duration: 180, easing: [0.25, 0.1, 0.25, 1] }}
  >
    <div
      class="modal-panel"
      onclick={(e) => e.stopPropagation()}
      transition:scale={{ start: 0.95, duration: 240, easing: [0.25, 0.1, 0.25, 1] }}
    >
      {#if title}
        <h2 class="modal-title">{title}</h2>
      {/if}
      <div class="modal-body">
        {#if children}
          {@render children()}
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    z-index: 10000;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    padding: 1rem;
  }

  .modal-panel {
    background: rgba(24, 24, 28, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 1.5rem;
    width: 100%;
    max-width: 420px;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
  }

  .modal-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--vercel-text);
    margin-bottom: 1rem;
  }

  .modal-body {
    color: var(--vercel-text-secondary);
    font-size: 0.875rem;
  }
</style>
