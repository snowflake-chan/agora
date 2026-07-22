<script lang="ts">
  import { BracesIcon, RssIcon } from "@lucide/svelte";
  import { API_BASE } from "../lib/config";
  import { translator } from "../lib/i18n";

  let open = $state(false);

  function closeOutside(event: MouseEvent) {
    if (!(event.target as HTMLElement).closest(".public-feeds")) open = false;
  }
</script>

<svelte:window onclick={closeOutside} />

<div class="public-feeds">
  <button
    type="button"
    class="feed-button"
    title={$translator("public.feeds")}
    aria-label={$translator("public.feeds")}
    aria-expanded={open}
    onclick={() => open = !open}
  >
    <RssIcon size={17} strokeWidth={1.8} aria-hidden="true" />
  </button>
  {#if open}
    <div class="feed-menu">
      <a href={`${API_BASE}/public/rss.xml`} rel="alternate" type="application/rss+xml">
        <RssIcon size={15} strokeWidth={1.8} aria-hidden="true" />
        <span>{$translator("public.rss")}</span>
      </a>
      <a href={`${API_BASE}/public/feed.json`} rel="alternate" type="application/feed+json">
        <BracesIcon size={15} strokeWidth={1.8} aria-hidden="true" />
        <span>{$translator("public.jsonFeed")}</span>
      </a>
    </div>
  {/if}
</div>

<style>
  .public-feeds { position: relative; }
  .feed-button { display:grid; width:2.25rem; height:2.25rem; place-items:center; border:0; border-radius:var(--vercel-radius-sm); color:var(--vercel-text-secondary); background:transparent; cursor:pointer; transition:color 150ms ease,background 150ms ease; }
  .feed-button:hover { color:var(--vercel-text); background:var(--vercel-hover); }
  .feed-button:focus-visible { outline:2px solid var(--vercel-ring); outline-offset:2px; }
  .feed-menu { position:absolute; z-index:var(--z-dropdown); top:calc(100% + .3rem); right:0; display:grid; width:11rem; overflow:hidden; padding:.3rem; border:1px solid var(--vercel-border); border-radius:var(--vercel-radius); background:var(--vercel-surface-raised); box-shadow:0 10px 30px var(--vercel-shadow); }
  .feed-menu a { display:flex; min-height:2.25rem; align-items:center; gap:.55rem; padding:.4rem .55rem; border-radius:var(--vercel-radius-sm); color:var(--vercel-text-secondary); font-size:.75rem; text-decoration:none; }
  .feed-menu a:hover { color:var(--vercel-text); background:var(--vercel-hover); }
</style>
