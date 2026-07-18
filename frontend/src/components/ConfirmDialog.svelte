<script lang="ts">
  let {
    open = $bindable(false),
    title = "确认",
    description = "",
    confirmText = "确定",
    onConfirm = () => {},
  }: {
    open: boolean;
    title: string;
    description: string;
    confirmText: string;
    onConfirm: () => void;
  } = $props();

  function handleConfirm() {
    onConfirm();
    open = false;
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      open = false;
    }
  }

  function stopPropagation(e: MouseEvent) {
    e.stopPropagation();
  }
</script>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="dialog-backdrop" onclick={handleBackdropClick}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="dialog-panel-confirm" onclick={stopPropagation}>
      <h3 class="dialog-title">{title}</h3>
      {#if description}
        <p class="dialog-desc">{description}</p>
      {/if}
      <div class="dialog-actions">
        <button class="btn btn-ghost btn-sm" onclick={() => (open = false)}>取消</button>
        <button class="btn btn-danger btn-sm" onclick={handleConfirm}>{confirmText}</button>
      </div>
    </div>
  </div>
{/if}
