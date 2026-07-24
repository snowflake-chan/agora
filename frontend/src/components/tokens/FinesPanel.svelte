<script lang="ts">
  import { onMount } from "svelte";
  import { CoinsIcon, CircleAlertIcon, CircleCheckIcon, LoaderCircleIcon } from "@lucide/svelte";
  import { locale, translator, translateError } from "../../lib/i18n";
  import { getMyFines, payFine, type FineItem } from "../../lib/tokens";
  import { toaster } from "../../stores/toaster";

  let fines = $state<FineItem[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let payingId = $state<string | null>(null);
  let sectionEl: HTMLElement | undefined = $state();

  let unpaidFines = $derived(fines.filter((f) => f.status === "pending"));
  let paidFines = $derived(fines.filter((f) => f.status !== "pending"));

  onMount(async () => {
    await loadFines();
    // Land users redirected from the post composer (unpaid-fines block) on
    // this section so they can pay immediately.
    try {
      if (new URLSearchParams(window.location.search).get("fines") === "1" && sectionEl) {
        sectionEl.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } catch {
      // ignore malformed query string
    }
  });

  async function loadFines() {
    loading = true;
    error = null;
    try {
      const result = await getMyFines(1, 50);
      fines = result.items;
    } catch (e) {
      error = translateError(e, $translator, "tokens.fines.payFailed");
    } finally {
      loading = false;
    }
  }

  async function handlePay(fineId: string) {
    if (payingId) return;
    payingId = fineId;
    try {
      await payFine(fineId);
      toaster.success($translator("tokens.fines.paySuccess"));
      await loadFines();
    } catch (e) {
      toaster.error($translator("tokens.fines.payFailed"), translateError(e, $translator, "common.operationFailed"));
    } finally {
      payingId = null;
    }
  }

  function statusLabel(status: string): string {
    switch (status) {
      case "pending": return $translator("tokens.fines.pending");
      case "paid": return $translator("tokens.fines.paid");
      case "cancelled": return $translator("tokens.fines.cancelled");
      default: return status;
    }
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString($locale, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  function issuerName(fine: FineItem): string {
    return fine.issued_by?.username ?? "—";
  }
</script>

<section class="card fines-section" bind:this={sectionEl} aria-labelledby="fines-title">
  <div class="fines-header">
    <h2 id="fines-title" class="section-title">
      <CoinsIcon size={16} aria-hidden="true" />
      {$translator("tokens.fines.title")}
    </h2>
    {#if unpaidFines.length > 0}
      <span class="fines-badge">
        <CircleAlertIcon size={13} aria-hidden="true" />
        {$translator("tokens.fines.unpaid")}
      </span>
    {/if}
  </div>

  {#if loading}
    <div class="fines-state">
      <LoaderCircleIcon class="spinner-icon" size={20} aria-hidden="true" />
    </div>
  {:else if error}
    <div class="error-banner" role="alert">{error}</div>
    <button type="button" class="btn btn-ghost btn-xs retry" onclick={loadFines}>
      {$translator("common.tryAgain")}
    </button>
  {:else if fines.length === 0}
    <div class="fines-state empty">
      <CircleCheckIcon size={18} aria-hidden="true" />
      <span>{$translator("tokens.fines.empty")}</span>
    </div>
  {:else}
    {#if unpaidFines.length > 0}
      <div class="fines-list">
        {#each unpaidFines as fine (fine.id)}
          <article class="fine-row fine-unpaid">
            <div class="fine-info">
              <span class="fine-amount">{fine.amount.toLocaleString()} AGC</span>
              <span class="fine-reason">{fine.reason}</span>
              <span class="fine-meta">
                {$translator("tokens.fines.issuedAt")}: {formatDate(fine.issued_at)}
                · {$translator("tokens.fines.issuedBy")}: {issuerName(fine)}
              </span>
            </div>
            <button
              type="button"
              class="btn btn-primary btn-xs"
              disabled={payingId === fine.id}
              onclick={() => handlePay(fine.id)}
            >
              {payingId === fine.id
                ? $translator("common.processing")
                : $translator("tokens.fines.payNow")}
            </button>
          </article>
        {/each}
      </div>
    {/if}

    {#if paidFines.length > 0}
      <div class="fines-history" class:has-unpaid={unpaidFines.length > 0}>
        <h3 class="fines-subtitle">{$translator("tokens.fines.status")}</h3>
        <div class="fines-list">
          {#each paidFines as fine (fine.id)}
            <article class="fine-row fine-history">
              <div class="fine-info">
                <span class="fine-amount">{fine.amount.toLocaleString()} AGC</span>
                <span class="fine-reason">{fine.reason}</span>
                <span class="fine-meta">
                  {$translator("tokens.fines.issuedAt")}: {formatDate(fine.issued_at)}
                  · {$translator("tokens.fines.issuedBy")}: {issuerName(fine)}
                </span>
              </div>
              <span
                class="fine-status-badge"
                class:status-paid={fine.status === "paid"}
                class:status-cancelled={fine.status === "cancelled"}
              >
                {statusLabel(fine.status)}
              </span>
            </article>
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</section>

<style>
  .fines-section {
    margin-bottom: 1rem;
    background: color-mix(in srgb, var(--vercel-card) 88%, transparent);
    backdrop-filter: blur(20px) saturate(160%);
    -webkit-backdrop-filter: blur(20px) saturate(160%);
  }

  .fines-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.85rem;
  }

  .section-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--vercel-text);
  }

  .fines-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.25rem 0.55rem;
    border-radius: 9999px;
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--vercel-warning);
    background: color-mix(in srgb, var(--vercel-warning) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--vercel-warning) 35%, transparent);
  }

  .fines-state {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 1.75rem 0;
    color: var(--vercel-text-tertiary);
    font-size: 0.8125rem;
  }

  .fines-state.empty {
    color: var(--vercel-text-tertiary);
  }

  .spinner-icon {
    animation: fines-spin 0.7s linear infinite;
  }

  @keyframes fines-spin {
    to { transform: rotate(360deg); }
  }

  .error-banner {
    padding: 0.75rem 1rem;
    color: var(--vercel-danger);
    background: color-mix(in srgb, var(--vercel-danger) 9%, transparent);
    border-left: 3px solid var(--vercel-danger);
    border-radius: 4px;
    font-size: 0.8125rem;
    margin-bottom: 0.75rem;
  }

  .retry {
    margin-top: 0.25rem;
  }

  .fines-list {
    display: grid;
    gap: 0.5rem;
  }

  .fine-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.65rem 0.75rem;
    background: var(--vercel-surface, #1e293b);
    border: 1px solid var(--vercel-border, #334155);
    border-radius: 6px;
  }

  .fine-unpaid {
    border-left: 3px solid var(--vercel-warning);
  }

  .fine-history {
    opacity: 0.85;
  }

  .fine-info {
    display: grid;
    gap: 0.15rem;
    min-width: 0;
    flex: 1;
  }

  .fine-amount {
    font-size: 0.85rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--vercel-text);
  }

  .fine-reason {
    font-size: 0.78rem;
    color: var(--vercel-text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .fine-meta {
    font-size: 0.68rem;
    color: var(--vercel-text-tertiary);
  }

  .fines-history {
    margin-top: 0.5rem;
  }

  .fines-history.has-unpaid {
    margin-top: 1rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--vercel-border);
  }

  .fines-subtitle {
    margin: 0 0 0.5rem;
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--vercel-text-tertiary);
  }

  .fine-status-badge {
    flex: 0 0 auto;
    padding: 0.2rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.68rem;
    font-weight: 600;
    color: var(--vercel-text-tertiary);
    background: var(--vercel-hover);
  }

  .fine-status-badge.status-paid {
    color: var(--vercel-success);
    background: color-mix(in srgb, var(--vercel-success) 14%, transparent);
  }

  .fine-status-badge.status-cancelled {
    color: var(--vercel-text-tertiary);
    background: var(--vercel-hover);
  }

  @media (max-width: 30rem) {
    .fine-row {
      flex-direction: column;
      align-items: stretch;
    }

    .fine-row > button,
    .fine-status-badge {
      align-self: flex-end;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .spinner-icon { animation: none; }
  }

  :global(html[data-motion="reduced"]) .spinner-icon { animation: none; }
</style>
