<script lang="ts">
  import { CoinsIcon, RocketIcon } from "@lucide/svelte";
  import { translateError, translator } from "../../lib/i18n";
  import { requestLogin } from "../../lib/login";
  import { boostPost, getTokenParams, sendTip, type BoostTier } from "../../lib/tokens";
  import { currentUser } from "../../stores/auth";
  import { toaster } from "../../stores/toaster";
  import GlassModal from "../GlassModal.svelte";

  let {
    postId,
    canBoost = false,
    compact = false,
    onOpen,
  }: {
    postId: string;
    canBoost?: boolean;
    compact?: boolean;
    onOpen?: (() => void) | null;
  } = $props();

  const t = $derived($translator);

  function openTip() {
    onOpen?.();
    tipOpen = true;
  }

  function openBoost() {
    onOpen?.();
    boostOpen = true;
  }

  let tipOpen = $state(false);
  let tipAmount = $state(5);
  let tipping = $state(false);
  let boostOpen = $state(false);
  let boosting = $state(false);
  let boostPrices = $state<Record<BoostTier, number>>({
    low: 10,
    mid: 30,
    high: 50,
  });
  let loadingPrices = $state(false);

  $effect(() => {
    if (boostOpen && !loadingPrices) {
      loadingPrices = true;
      getTokenParams()
        .then((params) => {
          boostPrices = {
            low: params.boost_price_low,
            mid: params.boost_price_mid,
            high: params.boost_price_high,
          };
        })
        .catch(() => {
          // Keep defaults on error so the UI remains usable.
        })
        .finally(() => {
          loadingPrices = false;
        });
    }
  });

  function requireAuth(action: () => void) {
    if (!$currentUser) {
      requestLogin(window.location.pathname, action);
      return;
    }
    action();
  }

  async function handleTip() {
    if (tipping || tipAmount <= 0) return;
    tipping = true;
    try {
      const result = await sendTip(postId, tipAmount);
      tipOpen = false;
      tipAmount = 5;
      toaster.success(t("tokens.tipSuccess"), `${result.balance_after} AGC`);
    } catch (error) {
      toaster.error(t("tokens.tipFailed"), translateError(error, t, "common.tryAgain"));
    } finally {
      tipping = false;
    }
  }

  async function handleBoost(tier: BoostTier) {
    if (boosting) return;
    boosting = true;
    try {
      await boostPost(postId, tier);
      boostOpen = false;
      toaster.success(t("tokens.boostSuccess"), t("tokens.boostActive"));
    } catch (error) {
      toaster.error(t("tokens.boostFailed"), translateError(error, t, "common.tryAgain"));
    } finally {
      boosting = false;
    }
  }

  const boostTiers: { tier: BoostTier; labelKey: string }[] = [
    { tier: "low", labelKey: "tokens.boostLow" },
    { tier: "mid", labelKey: "tokens.boostMid" },
    { tier: "high", labelKey: "tokens.boostHigh" },
  ];
</script>

{#if compact}
  <span class="token-actions compact">
    <button
      type="button"
      class="token-action compact"
      aria-label={t("tokens.tip")}
      title={t("tokens.tip")}
      onclick={() => requireAuth(openTip)}
    >
      <CoinsIcon size={14} strokeWidth={1.8} aria-hidden="true" />
    </button>
    {#if canBoost}
      <button
        type="button"
        class="token-action compact"
        aria-label={t("tokens.boost")}
        title={t("tokens.boost")}
        onclick={() => requireAuth(openBoost)}
      >
        <RocketIcon size={14} strokeWidth={1.8} aria-hidden="true" />
      </button>
    {/if}
  </span>
{:else}
  <span class="token-actions">
    <button
      type="button"
      class="post-action"
      aria-label={t("tokens.tip")}
      title={t("tokens.tip")}
      onclick={() => requireAuth(openTip)}
    >
      <CoinsIcon size={16} strokeWidth={1.8} aria-hidden="true" />
      <span>{t("tokens.tip")}</span>
    </button>
    {#if canBoost}
      <button
        type="button"
        class="post-action"
        aria-label={t("tokens.boost")}
        title={t("tokens.boost")}
        onclick={() => requireAuth(openBoost)}
      >
        <RocketIcon size={16} strokeWidth={1.8} aria-hidden="true" />
        <span>{t("tokens.boost")}</span>
      </button>
    {/if}
  </span>
{/if}

<GlassModal
  show={tipOpen}
  title={t("tokens.tip")}
  onclose={() => {
    if (!tipping) tipOpen = false;
  }}
>
  <div class="tip-form">
    <label>
      <span>{t("tokens.tipAmount")} (AGC)</span>
      <input
        class="input"
        type="number"
        min="1"
        step="1"
        bind:value={tipAmount}
        disabled={tipping}
      />
    </label>
    <div class="tip-actions">
      <button class="btn btn-ghost btn-sm" disabled={tipping} onclick={() => (tipOpen = false)}>
        {t("common.cancel")}
      </button>
      <button
        class="btn btn-primary btn-sm"
        disabled={tipping || tipAmount <= 0}
        onclick={handleTip}
      >
        {tipping ? t("common.sending") : t("tokens.tipSend")}
      </button>
    </div>
  </div>
</GlassModal>

<GlassModal
  show={boostOpen}
  title={t("tokens.boostTitle")}
  onclose={() => {
    if (!boosting) boostOpen = false;
  }}
>
  <p class="boost-copy">{t("tokens.boostTitle")}</p>
  <div class="boost-tiers">
    {#each boostTiers as { tier, labelKey } (tier)}
      <button
        type="button"
        class="boost-tier"
        disabled={boosting}
        onclick={() => handleBoost(tier)}
      >
        <span class="boost-tier-name">{t(labelKey)}</span>
        <span class="boost-tier-price">{t("tokens.boostPrice", { amount: boostPrices[tier] })}</span>
      </button>
    {/each}
  </div>
  <div class="boost-actions">
    <button class="btn btn-ghost btn-sm" disabled={boosting} onclick={() => (boostOpen = false)}>
      {t("common.cancel")}
    </button>
  </div>
</GlassModal>

<style>
  .token-actions {
    display: inline-flex;
    align-items: center;
  }

  .token-actions.compact {
    gap: 0.25rem;
  }

  .token-action,
  :global(.post-action) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    border-radius: 0.375rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.8125rem;
    font-weight: 500;
    transition: color 150ms ease, background 150ms ease;
  }

  .token-action:hover:not(:disabled),
  :global(.post-action:hover:not(:disabled)) {
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .token-action:focus-visible,
  :global(.post-action:focus-visible) {
    outline: 2px solid var(--vercel-text-secondary);
    outline-offset: -2px;
  }

  .token-action:disabled,
  :global(.post-action:disabled) {
    cursor: wait;
    opacity: 0.55;
  }

  .token-action.compact {
    width: 1.75rem;
    height: 1.75rem;
  }

  .token-action svg,
  :global(.post-action svg) {
    width: 1rem;
    height: 1rem;
  }

  .tip-form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .tip-form label {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    color: var(--vercel-text-secondary);
    font-size: 0.75rem;
    font-weight: 550;
  }

  .tip-form input {
    width: 100%;
  }

  .tip-actions,
  .boost-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
  }

  .boost-copy {
    margin: 0 0 0.75rem;
    color: var(--vercel-text-secondary);
    font-size: 0.8125rem;
  }

  .boost-tiers {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.5rem;
    margin-bottom: 1rem;
  }

  .boost-tier {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.35rem;
    padding: 0.75rem;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius);
    background: var(--vercel-card);
    color: var(--vercel-text);
    transition: background 150ms ease, border-color 150ms ease;
  }

  .boost-tier:hover:not(:disabled) {
    background: var(--vercel-hover);
    border-color: var(--vercel-border-hover);
  }

  .boost-tier:disabled {
    cursor: wait;
    opacity: 0.55;
  }

  .boost-tier-name {
    font-size: 0.75rem;
    font-weight: 550;
    color: var(--vercel-text-secondary);
  }

  .boost-tier-price {
    font-size: 1rem;
    font-weight: 700;
  }

  @media (max-width: 30rem) {
    .boost-tiers {
      grid-template-columns: 1fr;
    }
  }
</style>
