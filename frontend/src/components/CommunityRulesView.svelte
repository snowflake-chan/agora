<script lang="ts">
  import { ShieldCheckIcon } from "@lucide/svelte";
  import { translator } from "../lib/i18n";

  const ruleKeys = ["rules.respect", "rules.safety", "rules.privacy", "rules.integrity", "rules.review"];
</script>

<main class="rules-page">
  <section class="rules-card" aria-labelledby="rules-title">
    <div class="rules-icon"><ShieldCheckIcon size={26} strokeWidth={1.8} aria-hidden="true" /></div>
    <h1 id="rules-title">{$translator("rules.title")}</h1>
    <p class="rules-lead">{$translator("rules.lead")}</p>
    <ol>
      {#each ruleKeys as key}
        <li>{$translator(key)}</li>
      {/each}
    </ol>
  </section>
</main>

<style>
  .rules-page { width: min(100% - 2rem, 46rem); margin: 3rem auto; }
  .rules-card { padding: clamp(1.4rem, 4vw, 2.5rem); border: 1px solid var(--vercel-border); border-radius: var(--vercel-radius); background: var(--vercel-surface); }
  .rules-icon { color: var(--vercel-text-secondary); }
  h1 { margin: 0.8rem 0 0; color: var(--vercel-text); font-size: clamp(1.6rem, 4vw, 2.25rem); }
  .rules-lead { margin: 0.8rem 0 1.5rem; color: var(--vercel-text-secondary); font-size: 1rem; line-height: 1.65; }
  ol { display: grid; gap: 0.85rem; margin: 0; padding-left: 1.35rem; color: var(--vercel-text-secondary); line-height: 1.6; }
  li::marker { color: var(--vercel-text); font-weight: 700; }
</style>
