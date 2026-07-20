<script lang="ts">
  import { XIcon } from "@lucide/svelte";
  import { fade, fly } from "svelte/transition";
  import { translator } from "../../lib/i18n";
  import { modal } from "../../lib/modal";
  import { safeReturnTo } from "../../lib/returnTo";
  import LoginForm from "./LoginForm.svelte";

  let {
    open = $bindable(false),
    returnTo = "/",
    standalone = false,
    onClose = null,
    onAuthenticated = null,
  }: {
    open: boolean;
    returnTo?: string;
    standalone?: boolean;
    onClose?: (() => void) | null;
    onAuthenticated?: (() => void) | null;
  } = $props();

  function close() {
    if (standalone) {
      window.location.assign(safeReturnTo(returnTo, window.location.origin));
      return;
    }
    open = false;
    onClose?.();
  }

  function handleBackdropClick(event: MouseEvent) {
    if (event.target === event.currentTarget) close();
  }

  function handleAuthenticated() {
    if (standalone) {
      window.location.assign(safeReturnTo(returnTo, window.location.origin));
      return;
    }
    open = false;
    onAuthenticated?.();
  }

  function portal(node: HTMLElement) {
    document.body.appendChild(node);
    return {
      destroy() {
        node.remove();
      },
    };
  }
</script>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    use:portal
    class="auth-overlay"
    onclick={handleBackdropClick}
    out:fade={{ duration: 180 }}
  >
    <div
      use:modal={{ onClose: close }}
      class="auth-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="login-dialog-title"
      aria-describedby="login-dialog-description"
      tabindex="-1"
      out:fly={{ y: 16, duration: 180 }}
    >
      <header class="dialog-chrome">
        <a class="dialog-brand" href="/" aria-label="Agora">
          <img src="/favicon.svg" alt="" width="20" height="20" />
          <span>Agora</span>
        </a>
        <button
          class="dialog-close"
          type="button"
          aria-label={$translator("common.close")}
          title={$translator("common.close")}
          onclick={close}
        >
          <XIcon size={17} strokeWidth={1.8} />
        </button>
      </header>

      <div class="dialog-body">
        <div class="dialog-copy">
          <h1 id="login-dialog-title">{$translator("auth.signIn")}</h1>
          <p id="login-dialog-description">{$translator("auth.signInDescription")}</p>
        </div>
        <LoginForm {returnTo} onAuthenticated={handleAuthenticated} />
      </div>
    </div>
  </div>
{/if}

<style>
  .auth-overlay {
    position: fixed;
    inset: 0;
    z-index: var(--z-modal);
    display: grid;
    padding: clamp(1rem, 4vw, 2.5rem);
    place-items: center;
    background: color-mix(in srgb, var(--vercel-bg) 72%, transparent);
    backdrop-filter: blur(14px) saturate(120%);
    -webkit-backdrop-filter: blur(14px) saturate(120%);
    animation: auth-overlay-in 260ms ease both;
  }

  .auth-dialog {
    width: min(100%, 25rem);
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--vercel-text) 12%, transparent);
    border-radius: min(var(--vercel-radius-lg), 12px);
    color: var(--vercel-text);
    background: color-mix(in srgb, var(--vercel-card) 94%, transparent);
    box-shadow:
      inset 0 1px 0 color-mix(in srgb, #ffffff 7%, transparent),
      0 1.5rem 5rem color-mix(in srgb, var(--vercel-bg) 74%, transparent);
    transform-origin: 50% 78%;
    animation: auth-dialog-in 480ms var(--apple-ease-soft) both;
  }

  .dialog-chrome {
    display: flex;
    min-height: 3.35rem;
    padding: 0.65rem 0.75rem 0.65rem 1rem;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--vercel-border);
  }

  .dialog-brand {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    color: var(--vercel-text);
    font-size: 0.875rem;
    font-weight: 650;
  }

  .dialog-brand img {
    width: 1.15rem;
    height: 1.15rem;
  }

  .dialog-close {
    display: grid;
    width: 2rem;
    height: 2rem;
    place-items: center;
    border: 0;
    border-radius: var(--vercel-radius-sm);
    color: var(--vercel-text-tertiary);
    background: transparent;
    cursor: pointer;
    transition: color 180ms ease, background 180ms ease, transform 180ms ease;
  }

  .dialog-close:hover {
    color: var(--vercel-text);
    background: var(--vercel-hover-strong);
  }

  .dialog-close:active {
    transform: scale(0.92);
  }

  .dialog-body {
    display: grid;
    gap: 1.55rem;
    padding: 1.65rem 1.65rem 1.5rem;
  }

  .dialog-copy {
    display: grid;
    gap: 0.4rem;
    animation: auth-content-in 420ms 80ms var(--apple-ease-soft) both;
  }

  .dialog-copy h1 {
    font-size: 1.45rem;
    font-weight: 650;
    letter-spacing: 0;
    line-height: 1.2;
  }

  .dialog-copy p {
    max-width: 32ch;
    color: var(--vercel-text-tertiary);
    font-size: 0.8rem;
    line-height: 1.55;
  }

  .dialog-body :global(.login-form) {
    animation: auth-content-in 460ms 140ms var(--apple-ease-soft) both;
  }

  @keyframes auth-overlay-in {
    from {
      opacity: 0;
      backdrop-filter: blur(0);
      -webkit-backdrop-filter: blur(0);
    }
  }

  @keyframes auth-dialog-in {
    from {
      opacity: 0;
      transform: translate3d(0, 1.5rem, 0) scale(0.94);
    }
  }

  @keyframes auth-content-in {
    from {
      opacity: 0;
      transform: translateY(0.5rem);
    }
  }

  @media (max-width: 30rem) {
    .auth-overlay {
      align-items: end;
      padding: 0.65rem;
    }

    .auth-dialog {
      width: 100%;
      border-radius: min(var(--vercel-radius-lg), 12px);
      transform-origin: 50% 100%;
    }

    .dialog-body {
      padding: 1.4rem 1.2rem max(1.25rem, env(safe-area-inset-bottom));
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .auth-overlay,
    .auth-dialog,
    .dialog-copy,
    .dialog-body :global(.login-form) {
      animation: none;
    }
  }
</style>
