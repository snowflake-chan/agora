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
  <div class="dialog-backdrop" on:click={handleBackdropClick}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="dialog-panel" on:click|stopPropagation>
      <h3 class="dialog-title">{title}</h3>
      {#if description}
        <p class="dialog-desc">{description}</p>
      {/if}
      <div class="dialog-actions">
        <button class="btn btn-ghost btn-sm" on:click={() => (open = false)}>取消</button>
        <button class="btn btn-danger btn-sm" on:click={handleConfirm}>{confirmText}</button>
      </div>
    </div>
  </div>
{/if}