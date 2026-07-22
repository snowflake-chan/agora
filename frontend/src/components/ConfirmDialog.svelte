<script lang="ts">
  import { LoaderCircle } from "@lucide/svelte";
  import { translator } from "../lib/i18n";
  import { modal } from "../lib/modal";
  let {
    open = $bindable(false),
    title = "",
    description = "",
    confirmText = "",
    tone = "danger",
    onConfirm = () => {},
  }: {
    open: boolean;
    title: string;
    description: string;
    confirmText: string;
    tone?: "primary" | "danger";
    onConfirm: () => void | Promise<void>;
  } = $props();

  let pending = $state(false);

  async function handleConfirm() {
    if (pending) return;
    pending = true;
    try {
      await onConfirm();
      open = false;
    } catch {
      // The caller owns user-facing error feedback; keep the dialog open for retry.
    } finally {
      pending = false;
    }
  }

  function handleBackdropClick(e: MouseEvent) {
    if (!pending && e.target === e.currentTarget) {
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
    <div
      use:modal={{ onClose: () => { if (!pending) open = false; } }}
      class="dialog-panel-confirm"
      role="alertdialog"
      aria-modal="true"
      aria-busy={pending}
      aria-labelledby="confirm-dialog-title"
      aria-describedby={description ? "confirm-dialog-description" : undefined}
      tabindex="-1"
      onclick={stopPropagation}
    >
      <h3 id="confirm-dialog-title" class="dialog-title">
        {title || $translator("common.confirm")}
      </h3>
      {#if description}
        <p id="confirm-dialog-description" class="dialog-desc">{description}</p>
      {/if}
      <div class="dialog-actions">
        <button class="btn btn-ghost btn-sm" disabled={pending} onclick={() => (open = false)}>{$translator("common.cancel")}</button>
        <button
          data-autofocus
          class="btn btn-sm"
          class:btn-primary={tone === "primary"}
          class:btn-danger={tone === "danger"}
          disabled={pending}
          onclick={handleConfirm}
        >
          {#if pending}<LoaderCircle class="confirm-spinner" size={14} aria-hidden="true" />{/if}
          {confirmText || $translator("common.confirm")}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  :global(.confirm-spinner) {
    animation: confirm-spin 0.8s linear infinite;
  }

  @keyframes confirm-spin {
    to { transform: rotate(360deg); }
  }

  @media (prefers-reduced-motion: reduce) {
    :global(.confirm-spinner) { animation: none; }
  }
</style>
