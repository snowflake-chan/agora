<script lang="ts">
  import { Settings } from "@lucide/svelte";
  import { translator } from "../lib/i18n";
</script>

<a class="settings-button" href="/settings" aria-label={$translator("common.settings")} title={$translator("common.settings")}>
  <Settings class="size-4.5" />
</a>

<style>
  .settings-button {
    display: inline-flex;
    width: 2.25rem;
    height: 2.25rem;
    align-items: center;
    justify-content: center;
    border-radius: var(--vercel-radius-sm);
    color: var(--vercel-text-secondary);
    transition: color 150ms ease, background 150ms ease, transform 150ms ease;
  }

  .settings-button:hover {
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .settings-button:active {
    transform: translateY(1px);
  }
</style>
