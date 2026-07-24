<script lang="ts">
  import { onMount } from "svelte";
  import Chart from "chart.js/auto";
  import { getSupplyHistory } from "../../lib/tokens";
  import { translator, translateError } from "../../lib/i18n";

  let { title = "" }: { title?: string } = $props();

	let canvasEl: HTMLCanvasElement | undefined = $state();
	  let chartInstance: Chart | null = null;
	  let loading = $state(true);
	  let error = $state("");
	  let data = $state<any[] | null>(null);

  onMount(async () => {
    try {
      data = await getSupplyHistory(90);
      if (!data || data.length === 0) {
        loading = false;
        return;
      }

      const dates = data.map((d) => {
        const parts = d.date.split("-");
        return parts[1] + "/" + parts[2];
      });

      // Read CSS variable colors from the document
      const style = getComputedStyle(document.documentElement);
      const accent = style.getPropertyValue("--vercel-accent").trim() || "#6366f1";
      const success = style.getPropertyValue("--vercel-success").trim() || "#22c55e";
      const warning = style.getPropertyValue("--vercel-warning").trim() || "#f59e0b";
      const textSecondary = style.getPropertyValue("--vercel-text-secondary").trim() || "#9ca3af";
      const gridColor = style.getPropertyValue("--vercel-border").trim() || "#334155";

      if (canvasEl) {
        chartInstance = new Chart(canvasEl, {
          type: "line",
          data: {
            labels: dates,
            datasets: [
              {
                label: $translator("tokens.admin.circulating"),
                data: data.map((d) => d.circulating_supply),
                borderColor: accent,
                backgroundColor: accent + "20",
                fill: true,
                tension: 0.3,
                pointRadius: 2,
                pointHoverRadius: 5,
              },
              {
                label: $translator("tokens.admin.totalIssued"),
                data: data.map((d) => d.total_issued),
                borderColor: success,
                backgroundColor: success + "20",
                fill: true,
                tension: 0.3,
                pointRadius: 2,
                pointHoverRadius: 5,
              },
              {
                label: $translator("tokens.admin.totalBurned"),
                data: data.map((d) => d.total_burned),
                borderColor: warning,
                backgroundColor: warning + "20",
                fill: true,
                tension: 0.3,
                pointRadius: 2,
                pointHoverRadius: 5,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
              legend: {
                labels: {
                  color: textSecondary,
                  boxWidth: 12,
                  padding: 16,
                },
              },
              tooltip: {
                backgroundColor: style.getPropertyValue("--vercel-card")?.trim() || "#1e293b",
                titleColor: style.getPropertyValue("--vercel-text")?.trim() || "#f1f5f9",
                bodyColor: textSecondary,
                borderColor: gridColor,
                borderWidth: 1,
                cornerRadius: 8,
                padding: 12,
              },
            },
            scales: {
              x: {
                ticks: { color: textSecondary, maxTicksLimit: 15 },
                grid: { color: gridColor },
              },
              y: {
                ticks: {
                  color: textSecondary,
                  callback: (v) => (v as number).toLocaleString(),
                },
                grid: { color: gridColor },
              },
            },
          },
        });
      }
    } catch (e) {
      error = translateError(e, $translator, "tokens.loadFailed");
    } finally {
      loading = false;
    }
  });

  $effect(() => {
    // Cleanup on destroy
    return () => {
      if (chartInstance) {
        chartInstance.destroy();
        chartInstance = null;
      }
    };
  });
</script>

<div class="chart-wrapper">
  {#if title}
    <h4 class="chart-title">{title}</h4>
  {/if}

  {#if loading}
    <div class="empty-state"><div class="spinner"></div></div>
  {:else if error}
    <p class="row-meta">{error}</p>
  {:else if data.length === 0}
    <p class="row-meta">{$translator("tokens.admin.supplyTrendEmpty")}</p>
  {:else}
    <div class="chart-container">
      <canvas bind:this={canvasEl}></canvas>
    </div>
  {/if}
</div>

<style>
  .chart-wrapper {
    width: 100%;
  }
  .chart-title {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--vercel-text, #f1f5f9);
    margin: 0 0 0.75rem 0;
  }
  .chart-container {
    position: relative;
    height: 260px;
    width: 100%;
  }
  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 120px;
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
