<script lang="ts">
  import { onMount } from "svelte";
  import {
    getMonetaryMetrics,
    applyPolicyAdjustment,
    type MonetaryMetrics,
    type PolicyAdjustment,
  } from "../../lib/tokens";
  import { translator, translateError } from "../../lib/i18n";

  let { onAdjusted }: { onAdjusted?: () => void } = $props();

  let metrics = $state<MonetaryMetrics | null>(null);
  let adjustment = $state<PolicyAdjustment | null>(null);
  let loading = $state(true);
  let adjusting = $state(false);
  let applied = $state(false);
  let error = $state("");

  onMount(async () => {
    try {
      const m = await getMonetaryMetrics();
      metrics = m;
      // Fetch dry-run adjustment in parallel
      adjustment = await applyPolicyAdjustment(true);
    } catch (e) {
      error = translateError(e, $translator, "tokens.loadFailed");
    } finally {
      loading = false;
    }
  });

  function statusColor(status: string): string {
    switch (status) {
      case "healthy": return "var(--vercel-success, #22c55e)";
      case "inflating": return "var(--vercel-danger, #ef4444)";
      case "deflating": return "var(--vercel-warning, #f59e0b)";
      default: return "var(--vercel-text-secondary, #9ca3af)";
    }
  }

  function statusLabel(status: string): string {
    switch (status) {
      case "healthy": return $translator("tokens.admin.healthy");
      case "inflating": return $translator("tokens.admin.inflating");
      case "deflating": return $translator("tokens.admin.deflating");
      default: return status;
    }
  }

  async function handleApply() {
    adjusting = true;
    applied = false;
    try {
      const result = await applyPolicyAdjustment(false);
      adjustment = result;
      applied = result.adjusted;
      // Re-fetch metrics
      metrics = await getMonetaryMetrics();
      onAdjusted?.();
    } catch (e) {
      error = translateError(e, $translator, "tokens.loadFailed");
    } finally {
      adjusting = false;
    }
  }
</script>

<div class="monetary-panel">
  {#if loading}
    <div class="empty-state"><div class="spinner"></div></div>
  {:else if error}
    <p class="row-meta">{error}</p>
  {:else if metrics}
    <div class="metrics-grid">
      <!-- Inflation rate -->
      <div class="metric-card">
        <span class="metric-label">{$translator("tokens.admin.inflation30d")}</span>
        <span class="metric-value" style="color: {statusColor(metrics.status)}">
          {metrics.inflation_30d > 0 ? "+" : ""}{metrics.inflation_30d}%
        </span>
        <span class="metric-badge" style="background: {statusColor(metrics.status)}22; color: {statusColor(metrics.status)}; border: 1px solid {statusColor(metrics.status)}44;">
          {statusLabel(metrics.status)}
        </span>
      </div>

      <!-- 7-day -->
      <div class="metric-card">
        <span class="metric-label">{$translator("tokens.admin.inflation7d")}</span>
        <span class="metric-value" class:negative={metrics.inflation_7d < 0}>
          {metrics.inflation_7d > 0 ? "+" : ""}{metrics.inflation_7d}%
        </span>
      </div>

      <!-- Velocity -->
      <div class="metric-card">
        <span class="metric-label">{$translator("tokens.admin.velocity")}</span>
        <span class="metric-value">{metrics.velocity.toFixed(4)}</span>
      </div>

      <!-- Active users -->
      <div class="metric-card">
        <span class="metric-label">{$translator("tokens.admin.activeUsers")}</span>
        <span class="metric-value">{metrics.active_users.toLocaleString()}</span>
      </div>
    </div>

    <!-- Adjustment suggestion / result -->
    {#if adjustment}
      <div class="adjustment-box" class:adjustment-applied={adjustment.adjusted}>
        <p class="adjustment-reason">{adjustment.reason}</p>
        {#if Object.keys(adjustment.adjustments).length > 0}
          <div class="adjustment-params">
            {#each Object.entries(adjustment.adjustments) as [key, value]}
              <span class="param-change">
                {key.replace(/_/g, " ")} → {value.toLocaleString()}
              </span>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Apply button (only if there are adjustments and not already applied) -->
    {#if adjustment && Object.keys(adjustment.adjustments).length > 0 && !adjustment.adjusted}
      <button
        class="btn btn-primary btn-sm"
        onclick={handleApply}
        disabled={adjusting}
      >
        {$translator(adjusting ? "common.saving" : "tokens.admin.autoAdjust")}
      </button>
    {:else if applied}
      <p class="applied-notice">{$translator("tokens.admin.adjustApplied")}</p>
    {/if}
  {/if}
</div>

<style>
  .monetary-panel {
    width: 100%;
  }
  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.75rem;
    margin-bottom: 1rem;
  }
  .metric-card {
    background: var(--vercel-surface, #1e293b);
    border: 1px solid var(--vercel-border, #334155);
    border-radius: var(--vercel-radius, 8px);
    padding: 0.75rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .metric-label {
    font-size: 0.75rem;
    color: var(--vercel-text-tertiary, #64748b);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .metric-value {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--vercel-text, #f1f5f9);
  }
  .metric-value.negative {
    color: var(--vercel-danger, #ef4444);
  }
  .metric-badge {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 500;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
    align-self: flex-start;
    margin-top: 0.25rem;
  }
  .adjustment-box {
    background: var(--vercel-surface, #1e293b);
    border: 1px solid var(--vercel-warning, #f59e0b);
    border-radius: var(--vercel-radius, 8px);
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
  }
  .adjustment-box.adjustment-applied {
    border-color: var(--vercel-success, #22c55e);
  }
  .adjustment-reason {
    font-size: 0.8rem;
    color: var(--vercel-text-secondary, #94a3b8);
    margin: 0 0 0.5rem 0;
    line-height: 1.4;
  }
  .adjustment-params {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .param-change {
    font-size: 0.75rem;
    background: var(--vercel-hover, #2d3a4b);
    color: var(--vercel-text, #f1f5f9);
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    white-space: nowrap;
  }
  .applied-notice {
    font-size: 0.85rem;
    color: var(--vercel-success, #22c55e);
    margin: 0;
  }
  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem 0;
  }
  .spinner {
    width: 24px;
    height: 24px;
    border: 2px solid var(--vercel-border, #334155);
    border-top-color: var(--vercel-accent, #6366f1);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  .row-meta {
    color: var(--vercel-text-tertiary, #64748b);
    font-size: 0.8rem;
    text-align: center;
    padding: 2rem 0;
  }
</style>
