<script lang="ts">
  import { onMount } from "svelte";
  import { CoinsIcon } from "@lucide/svelte";
  import { translator } from "../lib/i18n";
  import { getBalance } from "../lib/tokens";
  import { currentUser } from "../stores/auth";

  const t = $derived($translator);
  let balance = $state<number | null>(null);
  let loading = $state(true);

  async function refresh() {
    if (!$currentUser) {
      balance = null;
      loading = false;
      return;
    }
    try {
      const data = await getBalance();
      balance = data.balance;
    } catch {
      balance = null;
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    void refresh();
    const interval = setInterval(refresh, 60_000);
    return () => clearInterval(interval);
  });

  $effect(() => {
    if ($currentUser?.id) {
      void refresh();
    } else {
      balance = null;
      loading = false;
    }
  });
</script>

{#if $currentUser}
  <a
    href="/tokens"
    class="token-balance"
    title={t("tokens.title")}
    aria-label={t("tokens.title")}
  >
    <CoinsIcon class="size-3.5" aria-hidden="true" />
    <span class="token-amount">
      {#if loading}
        —
      {:else}
        {balance?.toLocaleString() ?? 0}
      {/if}
    </span>
  </a>
{/if}

<style>
  .token-balance {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--vercel-text-secondary);
    background: var(--vercel-surface-raised);
    border: 1px solid var(--vercel-border);
    text-decoration: none;
    transition: background 0.15s ease, color 0.15s ease;
  }

  .token-balance:hover {
    color: var(--vercel-text);
    background: var(--vercel-hover-strong);
  }

  .token-amount {
    min-width: 1.5rem;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
</style>
