<script lang="ts">
  import type { Action } from "svelte/action";
  import { fade, scale } from "svelte/transition";
  import { modal } from "../lib/modal";
  import { appleEaseSoft } from "../lib/motion";

  let {
    show = false,
    title = "",
    onclose = () => {},
    children,
  }: {
    show: boolean;
    title?: string;
    onclose?: () => void;
    children?: import("svelte").Snippet;
  } = $props();

  const portal: Action<HTMLElement> = (node) => {
    document.body.appendChild(node);
    return {
      destroy() {
        node.remove();
      },
    };
  };

  function handleBackdropClick(event: MouseEvent) {
    if (event.target === event.currentTarget) onclose();
  }
</script>

{#if show}
  <div
    use:portal
    class="modal-backdrop"
    onclick={handleBackdropClick}
    transition:fade={{ duration: 180, easing: appleEaseSoft }}
  >
    <div
      use:modal={{ onClose: onclose }}
      class="modal-panel"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      tabindex="-1"
      transition:scale={{ start: 0.96, duration: 260, easing: appleEaseSoft }}
    >
      {#if title}
        <h2 class="modal-title">{title}</h2>
      {/if}
      <div class="modal-body">
        {#if children}
          {@render children()}
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    z-index: var(--z-modal);
    display: flex;
    align-items: center;
    justify-content: center;
    background: color-mix(in srgb, #000000 58%, transparent);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    padding: 1rem;
  }

  .modal-panel {
    width: 100%;
    max-width: 420px;
    max-height: min(85dvh, 44rem);
    overflow-y: auto;
    padding: 1.5rem;
    color: var(--vercel-text);
    background: color-mix(in srgb, var(--vercel-card) 94%, transparent);
    border: 1px solid var(--vercel-border);
    border-radius: min(var(--vercel-radius-lg), 12px);
    box-shadow:
      inset 0 1px 0 color-mix(in srgb, #ffffff 8%, transparent),
      0 20px 56px color-mix(in srgb, var(--vercel-bg) 58%, transparent);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    transform-origin: 50% 55%;
  }

  .modal-title {
    margin: 0 0 1rem;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--vercel-text);
    line-height: 1.35;
    text-wrap: balance;
  }

  .modal-body {
    color: var(--vercel-text-secondary);
    font-size: 0.875rem;
  }

  @media (max-width: 36rem) {
    .modal-backdrop {
      align-items: flex-end;
      padding: 0.75rem;
      padding-bottom: max(0.75rem, env(safe-area-inset-bottom));
    }

    .modal-panel {
      max-height: min(82dvh, 42rem);
      padding: 1.25rem;
      transform-origin: 50% 100%;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .modal-backdrop,
    .modal-panel {
      transition: none !important;
    }
  }
</style>
