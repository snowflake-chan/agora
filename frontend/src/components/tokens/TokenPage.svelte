<script lang="ts">
  import { onMount } from "svelte";
  import { CoinsIcon, FlameIcon, GiftIcon, TrendingDownIcon, TrendingUpIcon } from "@lucide/svelte";
  import { locale, translator, translateError } from "../../lib/i18n";
  import { initAuth, currentUser } from "../../stores/auth";
  import { toaster } from "../../stores/toaster";
  import { claimDailyLogin, getBalance, listTransactions, listMyStakes, getMyStakingStats, stakeTokens, unstakeTokens, claimYield, listPools, type TokenBalance, type TokenTransaction, type StakeItem, type StakingStats, type StakePool } from "../../lib/tokens";
  import { timeAgo } from "../../lib/utils";
  import Chart from "chart.js/auto";
  import FinesPanel from "./FinesPanel.svelte";

  let tokenBalance = $state<TokenBalance | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let dailyReward = $state<number | null>(null);
  let dailyStreak = $state(0);
  let dailyClaimed = $state(false);
  let claimingDaily = $state(false);

  let transactions = $state<TokenTransaction[]>([]);
  let transactionPage = $state(1);
  let transactionTotal = $state(0);
  let loadingTransactions = $state(false);

  let todayChange = $state(0);
  let chartPoints = $state<{ label: string; value: number }[]>([]);

  // Staking
  let myStakes = $state<StakeItem[]>([]);
  let stakingStats = $state<StakingStats | null>(null);
  let pools = $state<StakePool[]>([]);
  let stakingLoading = $state(true);
  let showStakeForm = $state(false);
  let stakeAmount = $state(10);
  let stakePool = $state("treasury");
  let stakeSubmitting = $state(false);
  let unstakingId = $state<string | null>(null);
  let claimingId = $state<string | null>(null);

  // Chart.js
  let canvasEl: HTMLCanvasElement | undefined = $state();
  let chartInstance: Chart | null = null;

  onMount(async () => {
    await initAuth();
    if ($currentUser) await loadAll();
    loading = false;
  });

  async function loadAll() {
    loading = true;
    error = null;
    try {
      const [balance, txList, stakes, stats, poolData] = await Promise.all([
        getBalance(),
        listTransactions(1, 50),
        listMyStakes(),
        getMyStakingStats(),
        listPools(),
      ]);
      tokenBalance = balance;
      transactions = txList.items;
      transactionTotal = txList.total;
      transactionPage = 1;
      myStakes = stakes.stakes;
      stakingStats = stats;
      pools = poolData.pools;
      stakingLoading = false;

      // Today's net change
      const now = new Date();
      const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      let change = 0;
      for (const tx of txList.items) {
        if (new Date(tx.created_at) >= todayStart) {
          if (tx.type === "spend") change -= tx.amount;
          else change += tx.amount;
        }
      }
      todayChange = change;

      // Chart data: oldest first, each transaction's balance_after
      const points = txList.items
        .slice()
        .reverse()
        .map((tx) => ({
          label: new Date(tx.created_at).toLocaleDateString([], { month: "short", day: "numeric" }),
          value: tx.balance_after,
        }));
      chartPoints = points;
    } catch (e) {
      error = translateError(e, $translator, "tokens.loadFailed");
    } finally {
      loading = false;
    }
  }

  async function loadMoreTransactions() {
    if (loadingTransactions || transactions.length >= transactionTotal) return;
    loadingTransactions = true;
    try {
      const next = transactionPage + 1;
      const txList = await listTransactions(next, 20);
      transactions = [...transactions, ...txList.items];
      transactionPage = next;
      transactionTotal = txList.total;
    } catch (e) {
      error = translateError(e, $translator, "tokens.loadFailed");
    } finally {
      loadingTransactions = false;
    }
  }

  async function handleClaimDaily() {
    if (claimingDaily || dailyClaimed) return;
    claimingDaily = true;
    try {
      const result = await claimDailyLogin();
      dailyReward = result.reward;
      dailyStreak = result.streak;
      dailyClaimed = result.already_claimed;
      if (tokenBalance) {
        tokenBalance = { ...tokenBalance, balance: result.balance };
      }
      // Refresh data
      const txList = await listTransactions(1, 50);
      transactions = txList.items;
      transactionTotal = txList.total;
      transactionPage = 1;

      const now = new Date();
      const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      let change = 0;
      for (const tx of txList.items) {
        if (new Date(tx.created_at) >= todayStart) {
          if (tx.type === "spend") change -= tx.amount;
          else change += tx.amount;
        }
      }
      todayChange = change;

      chartPoints = txList.items
        .slice()
        .reverse()
        .map((tx) => ({
          label: new Date(tx.created_at).toLocaleDateString([], { month: "short", day: "numeric" }),
          value: tx.balance_after,
        }));
    } catch (e) {
      error = translateError(e, $translator, "tokens.loadFailed");
    } finally {
      claimingDaily = false;
    }
  }

  async function handleStake() {
    if (stakeSubmitting || stakeAmount <= 0) return;
    stakeSubmitting = true;
    try {
      await stakeTokens(stakeAmount, stakePool);
      toaster.success($translator("tokens.staking.stakeSuccess"));
      showStakeForm = false;
      stakeAmount = 10;
      await refreshStaking();
      // Refresh balance too
      tokenBalance = await getBalance();
    } catch (e: any) {
      toaster.error(e.message || $translator("common.operationFailed"));
    } finally {
      stakeSubmitting = false;
    }
  }

  async function handleUnstake(stakeId: string) {
    if (unstakingId) return;
    unstakingId = stakeId;
    try {
      await unstakeTokens(stakeId);
      toaster.success($translator("tokens.staking.unstakeSuccess"));
      await refreshStaking();
      tokenBalance = await getBalance();
    } catch (e: any) {
      toaster.error(e.message || $translator("common.operationFailed"));
    } finally {
      unstakingId = null;
    }
  }

  async function handleClaimYield(stakeId: string) {
    if (claimingId) return;
    claimingId = stakeId;
    try {
      await claimYield(stakeId);
      toaster.success($translator("tokens.staking.claimYieldSuccess"));
      await refreshStaking();
      tokenBalance = await getBalance();
    } catch (e: any) {
      toaster.error(e.message || $translator("common.operationFailed"));
    } finally {
      claimingId = null;
    }
  }

  async function refreshStaking() {
    try {
      const [stakes, stats] = await Promise.all([
        listMyStakes(),
        getMyStakingStats(),
      ]);
      myStakes = stakes.stakes;
      stakingStats = stats;
    } catch {
      // silently fail
    }
  }

  function poolLabel(poolType: string): string {
    switch (poolType) {
      case "treasury": return $translator("tokens.staking.treasury");
      case "guild": return $translator("tokens.staking.guild");
      case "proposal": return $translator("tokens.staking.proposal");
      default: return poolType;
    }
  }

  function formatLockedUntil(lockedUntil: string | null): string {
    if (!lockedUntil) return $translator("tokens.staking.noLock");
    return new Date(lockedUntil).toLocaleDateString($locale, { month: "short", day: "numeric", year: "numeric" });
  }

  function transactionSign(amount: number, type: string): string {
    if (type === "spend") return `-${amount}`;
    if (type === "earn" || type === "receive") return `+${amount}`;
    return String(amount);
  }

  function transactionTypeLabel(source: string): string {
    const labels: Record<string, string> = {
      daily_login: $translator("tokens.dailyLogin"),
      post_liked: $translator("tokens.likeReward"),
      vote_quality: $translator("tokens.voteReward"),
      proposal_pass: $translator("tokens.proposalPass"),
      proposal_deposit_refund: $translator("tokens.depositRefund"),
      proposal_create: $translator("tokens.proposalDeposit"),
      tip_send: $translator("tokens.tip"),
      tip_receive: $translator("tokens.tipReceived"),
      content_boost: $translator("tokens.boost"),
      guild_create: $translator("tokens.guildCreate"),
      admin_mint: $translator("tokens.adminMint"),
    };
    return labels[source] || source;
  }

  // Chart render effect
  $effect(() => {
    const el = canvasEl;
    const pts = chartPoints;
    if (!el || pts.length < 2) {
      if (chartInstance) {
        chartInstance.destroy();
        chartInstance = null;
      }
      return;
    }

    // Cleanup previous instance
    if (chartInstance) {
      try { chartInstance.destroy(); } catch (e) { /* ignore */ }
      chartInstance = null;
    }

    const style = getComputedStyle(document.documentElement);
    const accent = style.getPropertyValue("--vercel-accent").trim() || "#6366f1";
    const textSecondary = style.getPropertyValue("--vercel-text-secondary").trim() || "#9ca3af";
    const gridColor = style.getPropertyValue("--vercel-border").trim() || "#334155";
    const cardBg = style.getPropertyValue("--vercel-card").trim() || "#1e293b";
    const textColor = style.getPropertyValue("--vercel-text").trim() || "#f1f5f9";

    chartInstance = new Chart(el, {
      type: "line",
      data: {
        labels: pts.map((d) => d.label),
        datasets: [
          {
            label: "AGC",
            data: pts.map((d) => d.value),
            borderColor: accent,
            backgroundColor: accent + "20",
            fill: true,
            tension: 0.3,
            pointRadius: 2,
            pointHoverRadius: 5,
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: cardBg,
            titleColor: textColor,
            bodyColor: textSecondary,
            borderColor: gridColor,
            borderWidth: 1,
            cornerRadius: 8,
            padding: 12,
            callbacks: {
              label: (ctx) => `${(ctx.parsed.y as number).toLocaleString()} AGC`,
            },
          },
        },
        scales: {
          x: {
            ticks: { color: textSecondary, maxTicksLimit: 10, font: { size: 10 } },
            grid: { color: gridColor },
          },
          y: {
            ticks: {
              color: textSecondary,
              font: { size: 10 },
              callback: (v) => (v as number).toLocaleString(),
            },
            grid: { color: gridColor },
          },
        },
      },
    });
  });

  $effect(() => {
    return () => {
      if (chartInstance) {
        chartInstance.destroy();
        chartInstance = null;
      }
    };
  });
</script>

{#if loading}
  <div class="empty-state"><div class="spinner"></div></div>
{:else if !$currentUser}
  <div class="empty-state signed-out">
    <p>{$translator("profile.signInRequired")}</p>
    <a href="/login?returnTo=%2Ftokens" class="btn btn-primary btn-sm mt-3">
      {$translator("profile.goSignIn")}
    </a>
  </div>
{:else if error}
  <div class="error-banner" role="alert">{error}</div>
{:else}
  <!-- Top heading -->
  <header class="heading">
    <div class="heading-left">
      <CoinsIcon size={20} aria-hidden="true" />
      <div>
        <h1>{$translator("tokens.pageTitle")}</h1>
        <p>{$translator("tokens.description")}</p>
      </div>
    </div>
  </header>

  <!-- Balance stats -->
  <div class="stats-row">
    <div class="stat-card stat-card-primary">
      <span class="stat-label">{$translator("tokens.balance")}</span>
      <span class="stat-value">{tokenBalance?.balance?.toLocaleString() ?? 0}</span>
      <span class="stat-unit">AGC</span>
    </div>
    <div class="stat-card" class:stat-positive={todayChange > 0} class:stat-negative={todayChange < 0}>
      <span class="stat-label">{$translator("tokens.today")}</span>
      <span class="stat-value-icon">
        {#if todayChange > 0}
          <TrendingUpIcon size={16} aria-hidden="true" />
        {:else if todayChange < 0}
          <TrendingDownIcon size={16} aria-hidden="true" />
        {/if}
        {todayChange > 0 ? "+" : ""}{todayChange.toLocaleString()}
      </span>
      <span class="stat-unit">AGC</span>
    </div>
    <div class="stat-card">
      <span class="stat-label">{$translator("tokens.earned")}</span>
      <span class="stat-value stat-positive">{tokenBalance?.total_earned?.toLocaleString() ?? 0}</span>
      <span class="stat-unit">AGC</span>
    </div>
    <div class="stat-card">
      <span class="stat-label">{$translator("tokens.spent")}</span>
      <span class="stat-value stat-negative">{tokenBalance?.total_spent?.toLocaleString() ?? 0}</span>
      <span class="stat-unit">AGC</span>
    </div>
  </div>

  <!-- Trend chart -->
  {#if chartPoints.length >= 2}
    <section class="card chart-section">
      <h2 class="section-title">{$translator("tokens.balanceTrend")}</h2>
      <div class="chart-container">
        <canvas bind:this={canvasEl}></canvas>
      </div>
    </section>
  {/if}

  <!-- Daily login -->
  <section class="card daily-section">
    <div class="daily-left">
      <GiftIcon size={18} aria-hidden="true" />
      <div>
        <strong>{$translator("tokens.dailyLogin")}</strong>
        {#if dailyStreak > 0}
          <small>
            <FlameIcon size={13} aria-hidden="true" />
            {$translator("tokens.streak", { count: dailyStreak })}
          </small>
        {/if}
      </div>
    </div>
    <button
      type="button"
      class="btn btn-primary btn-sm"
      disabled={claimingDaily || dailyClaimed}
      onclick={handleClaimDaily}
    >
      {#if claimingDaily}
        {$translator("common.processing")}
      {:else if dailyClaimed}
        {$translator("tokens.dailyLoginClaimed")}
      {:else}
        {$translator("tokens.claimDailyLogin")}
      {/if}
    </button>
  </section>

  <!-- Staking -->
  <section class="card stake-section">
    <div class="stake-header">
      <h2 class="section-title">{$translator("tokens.staking.title")}</h2>
      {#if !stakingLoading}
        <button class="btn btn-primary btn-xs" onclick={() => (showStakeForm = !showStakeForm)}>
          {showStakeForm ? $translator("common.cancel") : $translator("tokens.staking.stake")}
        </button>
      {/if}
    </div>

    {#if stakingStats}
      <div class="stake-stats-row">
        <div class="stake-stat">
          <span class="stake-stat-label">{$translator("tokens.staking.totalStaked")}</span>
          <span class="stake-stat-value">{stakingStats.total_staked.toLocaleString()} AGC</span>
        </div>
        <div class="stake-stat">
          <span class="stake-stat-label">{$translator("tokens.staking.pendingYield")}</span>
          <span class="stake-stat-value">{stakingStats.total_pending_yield.toLocaleString()} AGC</span>
        </div>
        <div class="stake-stat">
          <span class="stake-stat-label">{$translator("tokens.staking.activeStakes")}</span>
          <span class="stake-stat-value">{stakingStats.active_stakes}</span>
        </div>
      </div>
    {/if}

    {#if showStakeForm}
      <div class="stake-form">
        <div class="stake-form-row">
          <label>
            <span>{$translator("tokens.staking.poolType")}</span>
            <select class="input" bind:value={stakePool}>
              {#each pools as pool}
                <option value={pool.type}>{pool.name} ({pool.base_apy}% APY)</option>
              {/each}
            </select>
          </label>
          <label>
            <span>{$translator("tokens.staking.amount")}</span>
            <input class="input" type="number" min="1" bind:value={stakeAmount} />
          </label>
        </div>
        <button class="btn btn-primary btn-sm" onclick={handleStake} disabled={stakeSubmitting}>
          {stakeSubmitting ? $translator("common.processing") : $translator("tokens.staking.stake")}
        </button>
      </div>
    {/if}

    {#if myStakes.length > 0}
      <div class="stake-list">
        {#each myStakes as s (s.id)}
          <div class="stake-row">
            <div class="stake-info">
              <span class="stake-pool">{poolLabel(s.pool_type)}</span>
              <span class="stake-meta">
                {s.amount.toLocaleString()} AGC · {s.apy}% APY
              </span>
              <span class="stake-meta">
                {$translator("tokens.staking.lockedUntil")}: {formatLockedUntil(s.locked_until)}
                {#if s.pending_yield > 0}
                  · {$translator("tokens.staking.pendingYield")}: {s.pending_yield.toLocaleString()} AGC
                {/if}
              </span>
            </div>
            <div class="stake-actions">
              {#if s.pending_yield > 0}
                <button
                  class="btn btn-ghost btn-xs"
                  onclick={() => handleClaimYield(s.id)}
                  disabled={claimingId === s.id}
                >
                  {claimingId === s.id ? $translator("common.processing") : $translator("tokens.staking.claimYield")}
                </button>
              {/if}
              <button
                class="btn btn-danger-ghost btn-xs"
                onclick={() => handleUnstake(s.id)}
                disabled={unstakingId === s.id}
              >
                {unstakingId === s.id ? $translator("common.processing") : $translator("tokens.staking.unstake")}
              </button>
            </div>
          </div>
        {/each}
      </div>
    {:else if !showStakeForm && !stakingLoading}
      <p class="empty-meta">{$translator("tokens.staking.noStakes")}</p>
    {/if}
  </section>

  <!-- Fines -->
  <FinesPanel />

  <!-- Transactions -->
  <section class="card tx-section">
    <h2 class="section-title">{$translator("tokens.transactions")}</h2>
    {#if transactions.length === 0}
      <p class="empty-meta">{$translator("tokens.emptyTransactions")}</p>
    {:else}
      <div class="tx-list">
        {#each transactions as tx (tx.id)}
          <div class="tx-row">
            <div class="tx-info">
              <span class="tx-source">{transactionTypeLabel(tx.source)}</span>
              <span class="tx-meta">{timeAgo(tx.created_at)}</span>
            </div>
            <div class="tx-amount-wrap">
              <span
                class="tx-amount"
                class:positive={tx.type !== "spend"}
                class:negative={tx.type === "spend"}
              >
                {transactionSign(tx.amount, tx.type)} AGC
              </span>
            </div>
          </div>
        {/each}
      </div>
      {#if transactions.length < transactionTotal}
        <div class="load-more-wrap">
          <button
            type="button"
            class="btn btn-ghost btn-sm"
            disabled={loadingTransactions}
            onclick={loadMoreTransactions}
          >
            {loadingTransactions ? $translator("common.loading") : $translator("common.loadMore")}
          </button>
        </div>
      {/if}
    {/if}
  </section>
{/if}

<style>
  .heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.5rem;
  }

  .heading-left {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    color: var(--vercel-text);
  }

  .heading-left h1 {
    margin: 0;
    font-size: 1.25rem;
    line-height: 1.3;
  }

  .heading-left p {
    margin: 0.1rem 0 0;
    color: var(--vercel-text-tertiary);
    font-size: 0.8125rem;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 1rem;
    color: var(--vercel-text-tertiary);
  }

  .signed-out p {
    font-size: 0.9375rem;
    margin-bottom: 1rem;
  }

  .spinner {
    width: 24px;
    height: 24px;
    border: 2px solid var(--vercel-border);
    border-top-color: var(--vercel-accent);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .error-banner {
    padding: 0.75rem 1rem;
    color: var(--vercel-danger);
    background: color-mix(in srgb, var(--vercel-danger) 9%, transparent);
    border-left: 3px solid var(--vercel-danger);
    font-size: 0.8125rem;
    margin-bottom: 1rem;
  }

  .stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.75rem;
    margin-bottom: 1.25rem;
  }

  .stat-card {
    display: grid;
    gap: 0.15rem;
    padding: 1rem;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius);
    background: var(--vercel-card);
  }

  .stat-card-primary .stat-value {
    color: var(--vercel-accent);
  }

  .stat-label {
    color: var(--vercel-text-tertiary);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
  }

  .stat-value {
    font-size: 1.4rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--vercel-text);
    line-height: 1.1;
  }

  .stat-value-icon {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 1.1rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--vercel-text);
    line-height: 1.1;
  }

  .stat-positive { color: var(--vercel-success); }
  .stat-negative { color: var(--vercel-danger); }
  .stat-positive .stat-value { color: var(--vercel-success); }
  .stat-negative .stat-value { color: var(--vercel-danger); }

  .stat-unit {
    color: var(--vercel-text-tertiary);
    font-size: 0.68rem;
    font-weight: 500;
  }

  .card {
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius);
    background: var(--vercel-card);
    padding: 1.25rem;
  }

  .section-title {
    margin: 0 0 0.85rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--vercel-text);
  }

  .chart-section {
    margin-bottom: 1rem;
  }

  .chart-container {
    position: relative;
    height: 240px;
    width: 100%;
  }

  .daily-section {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .stake-section {
    margin-bottom: 1rem;
  }

  .stake-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
  }

  .stake-stats-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  .stake-stat {
    background: var(--vercel-surface, #1e293b);
    border: 1px solid var(--vercel-border, #334155);
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
  }

  .stake-stat-label {
    display: block;
    font-size: 0.65rem;
    color: var(--vercel-text-tertiary, #64748b);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
  }

  .stake-stat-value {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--vercel-text, #f1f5f9);
    font-variant-numeric: tabular-nums;
  }

  .stake-form {
    background: var(--vercel-surface, #1e293b);
    border: 1px solid var(--vercel-border, #334155);
    border-radius: 6px;
    padding: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .stake-form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .stake-form-row label {
    display: grid;
    gap: 0.25rem;
  }

  .stake-form-row label span {
    font-size: 0.7rem;
    color: var(--vercel-text-tertiary, #64748b);
  }

  .stake-list {
    display: grid;
    gap: 0.5rem;
  }

  .stake-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.6rem 0.75rem;
    background: var(--vercel-surface, #1e293b);
    border: 1px solid var(--vercel-border, #334155);
    border-radius: 6px;
  }

  .stake-info {
    display: grid;
    gap: 0.1rem;
    min-width: 0;
    flex: 1;
  }

  .stake-pool {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--vercel-text, #f1f5f9);
  }

  .stake-meta {
    font-size: 0.65rem;
    color: var(--vercel-text-tertiary, #64748b);
  }

  .stake-actions {
    display: flex;
    gap: 0.35rem;
    flex-shrink: 0;
  }

  .daily-left {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    color: var(--vercel-text-secondary);
  }

  .daily-left strong {
    display: block;
    color: var(--vercel-text);
    font-size: 0.875rem;
  }

  .daily-left small {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    margin-top: 0.15rem;
    color: var(--vercel-warning);
    font-size: 0.75rem;
  }

  .tx-section {
    margin-bottom: 2rem;
  }

  .empty-meta {
    color: var(--vercel-text-tertiary);
    font-size: 0.8125rem;
    text-align: center;
    padding: 1.5rem 0;
  }

  .tx-list {
    display: grid;
  }

  .tx-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.75rem 0;
    border-top: 1px solid var(--vercel-border);
  }

  .tx-row:first-child {
    border-top: 0;
    padding-top: 0;
  }

  .tx-info {
    display: grid;
    gap: 0.1rem;
    min-width: 0;
  }

  .tx-source {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--vercel-text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tx-meta {
    font-size: 0.7rem;
    color: var(--vercel-text-tertiary);
  }

  .tx-amount-wrap {
    flex: 0 0 auto;
    text-align: right;
  }

  .tx-amount {
    font-size: 0.875rem;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .tx-amount.positive { color: var(--vercel-success); }
  .tx-amount.negative { color: var(--vercel-danger); }

  .load-more-wrap {
    display: flex;
    justify-content: center;
    padding-top: 0.75rem;
  }

  @media (max-width: 42rem) {
    .stats-row {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (max-width: 28rem) {
    .stats-row {
      grid-template-columns: 1fr 1fr;
    }

    .daily-section {
      flex-direction: column;
      align-items: stretch;
      text-align: center;
    }

    .daily-left {
      justify-content: center;
    }
  }
</style>
