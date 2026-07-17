<script lang="ts">
  export let open = false;
  export let title = "确认";
  export let description = "";
  export let confirmText = "确定";
  export let onConfirm: () => void = () => {};

  function handleConfirm() {
    onConfirm();
    open = false;
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      open = false;
    }
  }
</script>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    on:click={handleBackdropClick}
  >
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="max-w-sm rounded-lg border border-surface-200-800 bg-surface p-6 shadow-xl"
      on:click|stopPropagation
    >
      <h3 class="text-base font-semibold text-surface-900-100">{title}</h3>
      {#if description}
        <p class="mt-2 text-sm text-surface-500">{description}</p>
      {/if}
      <div class="mt-5 flex justify-end gap-2">
        <button class="btn preset-tonal text-sm" on:click={() => (open = false)}>取消</button>
        <button class="btn preset-filled-error-500 text-sm" on:click={handleConfirm}>{confirmText}</button>
      </div>
    </div>
  </div>
{/if}
