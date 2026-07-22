<script lang="ts">
  import { ShieldCheckIcon } from "@lucide/svelte";
  import { translator } from "../../lib/i18n";
</script>

<aside class="rules-notice" aria-label={$translator("auth.rulesTitle")}>
  <div class="rules-heading">
    <ShieldCheckIcon size={16} strokeWidth={1.9} aria-hidden="true" />
    <strong>{$translator("auth.rulesTitle")}</strong>
  </div>
  <ul>
    <li>{$translator("rules.respect")}</li>
    <li>{$translator("rules.safety")}</li>
    <li>{$translator("rules.privacy")}</li>
  </ul>
  <p>
    {$translator("auth.rulesAgreement")}
    <a href="/rules">{$translator("rules.readMore")}</a>
  </p>
</aside>

<style>
  .rules-notice {
    display: grid;
    gap: 0.55rem;
    padding: 0.8rem;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius);
    color: var(--vercel-text-secondary);
    background: color-mix(in srgb, var(--vercel-surface) 82%, transparent);
    font-size: 0.78rem;
    line-height: 1.45;
  }

  .rules-heading { display: flex; align-items: center; gap: 0.42rem; color: var(--vercel-text); }
  ul { display: grid; gap: 0.28rem; margin: 0; padding-left: 1.1rem; }
  p { margin: 0; }
  a { margin-left: 0.25rem; color: var(--vercel-text); font-weight: 650; }
</style>
