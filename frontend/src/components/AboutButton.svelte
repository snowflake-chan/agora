<script lang="ts">
  import { Info } from "@lucide/svelte";
  import { translator } from "../lib/i18n";
</script>

<a
  class="about-button"
  href="/about"
  aria-label={$translator("nav.about")}
  title={$translator("nav.about")}
>
  <Info class="size-4.5" />
</a>

<style>
  .about-button {
    display: inline-flex;
    width: 2.25rem;
    height: 2.25rem;
    align-items: center;
    justify-content: center;
    border-radius: var(--vercel-radius-sm);
    color: var(--vercel-text-secondary);
    transition: color 150ms ease, background 150ms ease, transform 150ms ease;
  }

  .about-button:hover {
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .about-button:active {
    transform: translateY(1px);
  }

  .about-button:focus-visible {
    outline: 2px solid var(--vercel-ring);
    outline-offset: 2px;
  }
</style>
