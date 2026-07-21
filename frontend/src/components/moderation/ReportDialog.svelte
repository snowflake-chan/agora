<script lang="ts">
  import { translator } from "../../lib/i18n";
  import GlassModal from "../GlassModal.svelte";

  let {
    open = $bindable(false),
    reason = $bindable(""),
    submitting = false,
    onsubmit = () => {},
  }: {
    open: boolean;
    reason: string;
    submitting?: boolean;
    onsubmit?: (reason: string) => void | Promise<void>;
  } = $props();

  const MAX_REASON_LENGTH = 500;

  function close() {
    if (!submitting) open = false;
  }

  function submit(event: SubmitEvent) {
    event.preventDefault();
    const normalizedReason = reason.trim();
    if (!normalizedReason || submitting) return;
    void onsubmit(normalizedReason);
  }
</script>

<GlassModal
  show={open}
  title={$translator("moderation.reportTitle")}
  onclose={close}
>
  <form class="report-form" aria-busy={submitting} onsubmit={submit}>
    <textarea
      data-autofocus
      class="input report-reason"
      rows="4"
      bind:value={reason}
      maxlength={MAX_REASON_LENGTH}
      disabled={submitting}
      aria-label={$translator("moderation.reportReasonPlaceholder")}
      placeholder={$translator("moderation.reportReasonPlaceholder")}
    ></textarea>

    <div class="report-meta" aria-live="polite">
      <span>{reason.length}/{MAX_REASON_LENGTH}</span>
    </div>

    <div class="report-actions">
      <button
        type="button"
        class="btn btn-ghost btn-sm"
        disabled={submitting}
        onclick={close}
      >
        {$translator("common.cancel")}
      </button>
      <button
        type="submit"
        class="btn btn-primary btn-sm"
        disabled={submitting || !reason.trim()}
      >
        {$translator(submitting ? "moderation.reporting" : "moderation.reportSubmit")}
      </button>
    </div>
  </form>
</GlassModal>

<style>
  .report-form {
    display: flex;
    flex-direction: column;
  }

  .report-reason {
    min-height: 7.5rem;
    resize: vertical;
  }

  .report-meta {
    display: flex;
    justify-content: flex-end;
    margin-top: 0.35rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
    font-variant-numeric: tabular-nums;
    line-height: 1.35;
  }

  .report-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    margin-top: 1rem;
  }

  @media (max-width: 24rem) {
    .report-actions > button {
      min-width: 0;
      flex: 1;
    }
  }
</style>
