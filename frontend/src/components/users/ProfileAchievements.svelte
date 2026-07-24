<script lang="ts">
  import { onMount } from "svelte";
  import { AwardIcon, MedalIcon, ShieldIcon, StarIcon } from "@lucide/svelte";
  import { translator, locale } from "../../lib/i18n";
  import { getUserAchievements, type AchievementData, type AchievementItem } from "../../lib/tokens";

  let { userId }: { userId: string } = $props();

  let data = $state<AchievementData | null>(null);
  let loading = $state(true);
  let error = $state(false);

  const tierIcons = [null, ShieldIcon, MedalIcon, StarIcon, AwardIcon];
  const tierColors = ["", "var(--vercel-amber, #d97706)", "var(--vercel-text-tertiary, #9ca3af)", "var(--vercel-warning, #f59e0b)", "var(--vercel-accent, #6366f1)"];

  async function load() {
    loading = true;
    error = false;
    try {
      data = await getUserAchievements(userId);
    } catch {
      error = true;
    } finally {
      loading = false;
    }
  }

  // Localize a category label, falling back to the backend snapshot.
  function categoryLabel(cat: { key: string; label: string }): string {
    const t = $translator;
    const k = `ach.category.${cat.key}`;
    const v = t(k);
    return v === k ? cat.label : v;
  }

  // Localize an achievement name, falling back to the backend snapshot.
  function achievementName(ach: { key: string; name: string }): string {
    const t = $translator;
    const k = `ach.name.${ach.key}`;
    const v = t(k);
    return v === k ? ach.name : v;
  }

  // Localize a tier label, falling back to the backend snapshot.
  function achievementTier(ach: { tier_label: string }): string {
    if (!ach.tier_label) return "—";
    const t = $translator;
    const k = `ach.tier.${ach.tier_label}`;
    const v = t(k);
    return v === k ? ach.tier_label : v;
  }

  onMount(() => {
    load();
    let initialized = false;
    return locale.subscribe(() => {
      // Skip the immediate synchronous emit so we don't double-fetch on mount.
      if (!initialized) {
        initialized = true;
        return;
      }
      load();
    });
  });
</script>

{#if loading}
  <div class="ach-loading"><div class="spinner"></div></div>
{:else if error}
  <div class="ach-error">
    <p>{$translator("common.loadFailed")}</p>
    <button class="btn btn-primary btn-xs" onclick={load}>{$translator("common.retry")}</button>
  </div>
{:else if data && data.categories.length > 0}
  <div class="ach-grid">
    {#each data.categories as cat}
      <div class="ach-category">
        <h4 class="ach-cat-title">{categoryLabel(cat)}</h4>
        <div class="ach-items">
          {#each cat.achievements as ach}
            {@const Icon = ach.tier > 0 ? tierIcons[ach.tier] : null}
            <div class="ach-item" class:ach-earned={ach.tier > 0}>
              {#if Icon}
                <Icon size={14} style="color: {tierColors[ach.tier]}" aria-hidden="true" />
              {:else}
                <span class="ach-empty-icon"></span>
              {/if}
              <div class="ach-info">
                <span class="ach-name">{achievementName(ach)}</span>
                <span class="ach-score">
                  {ach.score.toLocaleString()} / {ach.thresholds[ach.tier + 1] ?? ach.thresholds[ach.tier]?.toLocaleString() ?? "?"}
                </span>
              </div>
              <span class="ach-tier" class:ach-tier-bronze={ach.tier === 1} class:ach-tier-silver={ach.tier === 2} class:ach-tier-gold={ach.tier === 3} class:ach-tier-platinum={ach.tier === 4}>
                {achievementTier(ach)}
              </span>
            </div>
          {/each}
        </div>
      </div>
    {/each}
  </div>
{:else}
  <p class="ach-empty">{$translator("common.noData")}</p>
{/if}

<style>
  .ach-loading { display: flex; justify-content: center; padding: 1.5rem 0; }
  .spinner {
    width: 20px; height: 20px; border: 2px solid var(--vercel-border);
    border-top-color: var(--vercel-accent); border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .ach-grid { display: grid; gap: 1rem; }
  .ach-category { border: 1px solid var(--vercel-border); border-radius: var(--vercel-radius); padding: 0.75rem 1rem; background: var(--vercel-card); }
  .ach-cat-title { margin: 0 0 0.5rem; font-size: 0.75rem; font-weight: 600; color: var(--vercel-text-secondary); text-transform: uppercase; letter-spacing: 0.05em; }
  .ach-items { display: grid; gap: 0.4rem; }
  .ach-item { display: flex; align-items: center; gap: 0.5rem; padding: 0.3rem 0; }
  .ach-empty-icon { width: 14px; height: 14px; border-radius: 50%; border: 1px dashed var(--vercel-border-hover); }
  .ach-info { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .ach-name { font-size: 0.78rem; color: var(--vercel-text-secondary); }
  .ach-earned .ach-name { color: var(--vercel-text); }
  .ach-score { font-size: 0.65rem; color: var(--vercel-text-tertiary); font-variant-numeric: tabular-nums; }
  .ach-tier { font-size: 0.62rem; font-weight: 600; text-transform: uppercase; padding: 0.1rem 0.4rem; border-radius: 999px; color: var(--vercel-text-tertiary); background: var(--vercel-surface-muted); }
  .ach-tier-bronze { color: #d97706; background: #d9770618; }
  .ach-tier-silver { color: #9ca3af; background: #9ca3af18; }
  .ach-tier-gold { color: #f59e0b; background: #f59e0b18; }
  .ach-tier-platinum { color: #6366f1; background: #6366f118; }
  .ach-error { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 1.5rem 0; }
  .ach-error p { margin: 0; font-size: 0.75rem; color: var(--vercel-text-tertiary); }
  .ach-empty { text-align: center; color: var(--vercel-text-tertiary); font-size: 0.75rem; padding: 1rem 0; }
</style>