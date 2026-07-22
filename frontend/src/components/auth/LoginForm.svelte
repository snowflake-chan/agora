<script lang="ts">
  import { EyeIcon, EyeOffIcon } from "@lucide/svelte";
  import { onMount } from "svelte";
  import { translator } from "../../lib/i18n";
  import { safeReturnTo } from "../../lib/returnTo";
  import { login } from "../../stores/auth";
  import CommunityRulesNotice from "./CommunityRulesNotice.svelte";

  let {
    returnTo = "",
    onAuthenticated = null,
  }: {
    returnTo?: string;
    onAuthenticated?: (() => void) | null;
  } = $props();

  let email = $state("");
  let password = $state("");
  let loading = $state(false);
  let passwordVisible = $state(false);
  let errorMessage = $state("");
  let destination = $state("/");
  let mounted = $state(false);

  onMount(() => {
    mounted = true;
  });

  $effect(() => {
    void returnTo;
    if (!mounted) return;
    destination = safeReturnTo(
      returnTo ||
        new URLSearchParams(window.location.search).get("returnTo") ||
        document.referrer,
      window.location.origin,
    );
  });

  async function handleSubmit() {
    if (loading) return;
    loading = true;
    errorMessage = "";
    try {
      await login(email, password);
      if (onAuthenticated) {
        onAuthenticated();
      } else {
        window.location.assign(destination);
      }
    } catch (error: any) {
      errorMessage = error?.code === "LOGIN_INVALID_CREDENTIALS"
        ? $translator("auth.invalidCredentials")
        : $translator("auth.error");
    } finally {
      loading = false;
    }
  }
</script>

<form
  class="login-form"
  aria-busy={loading}
  onsubmit={(event) => {
    event.preventDefault();
    handleSubmit();
  }}
>
  <label class="field-group">
    <span>{$translator("auth.email")}</span>
    <input
      data-autofocus
      type="email"
      bind:value={email}
      class="input auth-input"
      placeholder="name@example.com"
      autocomplete="email"
      inputmode="email"
      aria-invalid={errorMessage ? "true" : undefined}
      aria-describedby={errorMessage ? "login-error" : undefined}
      oninput={() => (errorMessage = "")}
      required
    />
  </label>

  <label class="field-group">
    <span>{$translator("auth.password")}</span>
    <span class="password-field">
      <input
        type={passwordVisible ? "text" : "password"}
        bind:value={password}
        class="input auth-input"
        autocomplete="current-password"
        aria-invalid={errorMessage ? "true" : undefined}
        aria-describedby={errorMessage ? "login-error" : undefined}
        oninput={() => (errorMessage = "")}
        required
      />
      <button
        type="button"
        class="password-toggle"
        aria-label={$translator(passwordVisible ? "auth.hidePassword" : "auth.showPassword")}
        title={$translator(passwordVisible ? "auth.hidePassword" : "auth.showPassword")}
        onclick={() => (passwordVisible = !passwordVisible)}
      >
        {#if passwordVisible}
          <EyeOffIcon size={16} strokeWidth={1.8} />
        {:else}
          <EyeIcon size={16} strokeWidth={1.8} />
        {/if}
      </button>
    </span>
  </label>

  <div class="message-slot" aria-live="polite">
    {#if errorMessage}
      <p id="login-error" class="form-error">{errorMessage}</p>
    {/if}
  </div>

  <CommunityRulesNotice />

  <button type="submit" class="btn btn-primary submit-button" disabled={loading}>
    {#if loading}<span class="button-spinner" aria-hidden="true"></span>{/if}
    <span>{loading ? $translator("auth.signingIn") : $translator("auth.signIn")}</span>
  </button>

  <p class="register-prompt">
    {$translator("auth.noAccount")}
    <a href={`/register?returnTo=${encodeURIComponent(destination)}`} class="auth-link">
      {$translator("auth.register")}
    </a>
  </p>
</form>

<style>
  .login-form {
    display: grid;
    gap: 1rem;
  }

  .field-group {
    display: grid;
    gap: 0.45rem;
  }

  .field-group > span:first-child {
    color: var(--vercel-text-secondary);
    font-size: 0.75rem;
    font-weight: 600;
  }

  .auth-input {
    min-height: 2.75rem;
    padding-inline: 0.85rem;
    background: color-mix(in srgb, var(--vercel-surface) 76%, transparent);
  }

  .auth-input[aria-invalid="true"] {
    border-color: color-mix(in srgb, var(--vercel-danger) 62%, var(--vercel-border));
  }

  .auth-input:focus-visible {
    outline: none;
  }

  .password-field {
    position: relative;
    display: block;
  }

  .password-field .auth-input {
    padding-right: 2.8rem;
  }

  .password-toggle {
    position: absolute;
    top: 50%;
    right: 0.45rem;
    display: grid;
    width: 2rem;
    height: 2rem;
    place-items: center;
    border: 0;
    border-radius: var(--vercel-radius-sm);
    color: var(--vercel-text-tertiary);
    background: transparent;
    cursor: pointer;
    transform: translateY(-50%);
    transition: color 180ms ease, background 180ms ease, transform 180ms ease;
  }

  .password-toggle:hover {
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .password-toggle:active {
    transform: translateY(-50%) scale(0.94);
  }

  .message-slot {
    min-height: 1.25rem;
    margin-top: -0.25rem;
  }

  .form-error {
    color: var(--vercel-danger);
    font-size: 0.75rem;
    line-height: 1.5;
  }

  .submit-button {
    min-height: 2.75rem;
    transition:
      transform 220ms var(--apple-ease),
      background 180ms ease,
      border-color 180ms ease,
      opacity 180ms ease;
  }

  .submit-button:not(:disabled):active {
    transform: scale(0.985);
  }

  .button-spinner {
    width: 0.9rem;
    height: 0.9rem;
    border: 1.5px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;
    animation: button-spin 650ms linear infinite;
  }

  .register-prompt {
    color: var(--vercel-text-tertiary);
    font-size: 0.78rem;
    text-align: center;
  }

  .auth-link {
    margin-left: 0.25rem;
    color: var(--vercel-text);
    font-weight: 600;
    transition: opacity 180ms ease;
  }

  .auth-link:hover {
    opacity: 0.72;
  }

  @keyframes button-spin {
    to {
      transform: rotate(360deg);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .button-spinner {
      animation-duration: 1.2s;
    }
  }
</style>
