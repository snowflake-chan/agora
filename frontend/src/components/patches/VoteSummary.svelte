<script lang="ts">
  import { translator } from "../../lib/i18n";

  let {
    forCount = 0,
    againstCount = 0,
    abstainCount = 0,
    ariaLabel = "",
  }: {
    forCount?: number;
    againstCount?: number;
    abstainCount?: number;
    ariaLabel?: string;
  } = $props();
</script>

<dl class="vote-summary" aria-label={ariaLabel || $translator("patch.governance")}>
  <div class="vote-summary-item is-for">
    <dt>{$translator("patch.for")}</dt>
    <dd>{forCount}</dd>
  </div>
  <div class="vote-summary-item is-against">
    <dt>{$translator("patch.against")}</dt>
    <dd>{againstCount}</dd>
  </div>
  <div class="vote-summary-item">
    <dt>{$translator("patch.abstain")}</dt>
    <dd>{abstainCount}</dd>
  </div>
</dl>

<style>
  .vote-summary {
    display: flex;
    min-width: 0;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.3rem 0.75rem;
    margin: 0;
    color: var(--vercel-text-tertiary);
    font-size: 0.72rem;
    line-height: 1.35;
  }

  .vote-summary-item {
    display: inline-flex;
    min-width: 0;
    align-items: baseline;
    gap: 0.25rem;
  }

  .vote-summary dt,
  .vote-summary dd {
    margin: 0;
  }

  .vote-summary dd {
    color: var(--vercel-text-secondary);
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }

  .vote-summary-item.is-for dd {
    color: var(--vercel-success);
  }

  .vote-summary-item.is-against dd {
    color: var(--vercel-danger);
  }
</style>
