<script lang="ts">
  import { marked } from "marked";
  import { onMount } from "svelte";

  export let content: string;

  let html = "";
  let rendered = false;

  onMount(async () => {
    const result = await marked.parse(content, { breaks: true, gfm: true });
    html = result.toString();
    rendered = true;
  });
</script>

{#if rendered}
  <div class="prose prose-sm prose-surface max-w-none">
    {@html html}
  </div>
{/if}

<style>
  :global(.prose) {
    line-height: 1.7;
    word-wrap: break-word;
  }
  :global(.prose p) {
    margin-bottom: 0.75em;
  }
  :global(.prose h1),
  :global(.prose h2),
  :global(.prose h3),
  :global(.prose h4) {
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    font-weight: 600;
    color: var(--color-surface-900);
  }
  :global(.prose h1) { font-size: 1.5em; }
  :global(.prose h2) { font-size: 1.3em; }
  :global(.prose h3) { font-size: 1.15em; }
  :global(.prose ul),
  :global(.prose ol) {
    padding-left: 1.5em;
    margin-bottom: 0.75em;
  }
  :global(.prose li) {
    margin-bottom: 0.25em;
  }
  :global(.prose blockquote) {
    border-left: 3px solid var(--color-surface-300);
    margin: 0.75em 0;
    padding: 0.25em 1em;
    color: var(--color-surface-600);
  }
  :global(.prose code) {
    background: var(--color-surface-100);
    border-radius: 3px;
    padding: 0.15em 0.4em;
    font-size: 0.875em;
    font-family: ui-monospace, monospace;
  }
  :global(.prose pre) {
    background: var(--color-surface-100);
    border-radius: 6px;
    padding: 1em;
    overflow-x: auto;
    margin-bottom: 0.75em;
  }
  :global(.prose pre code) {
    background: none;
    padding: 0;
    border-radius: 0;
  }
  :global(.prose a) {
    color: var(--color-primary-600);
    text-decoration: underline;
  }
  :global(.prose a:hover) {
    color: var(--color-primary-700);
  }
  :global(.prose img) {
    max-width: 100%;
    border-radius: 6px;
  }
  :global(.prose hr) {
    border: none;
    border-top: 1px solid var(--color-surface-200);
    margin: 1.5em 0;
  }
  :global(.prose table) {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 0.75em;
  }
  :global(.prose th),
  :global(.prose td) {
    border: 1px solid var(--color-surface-200);
    padding: 0.5em;
    text-align: left;
  }
  :global(.prose th) {
    background: var(--color-surface-50);
    font-weight: 600;
  }
</style>
