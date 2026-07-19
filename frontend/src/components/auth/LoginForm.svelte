<script lang="ts">
  import { onMount } from "svelte";
  import { translator } from "../../lib/i18n";
  import { safeReturnTo } from "../../lib/returnTo";
  import { login } from "../../stores/auth";
  import { toaster } from "../../stores/toaster";

  let email = "";
  let password = "";
  let loading = false;
  let returnTo = "/";

  onMount(() => {
    returnTo = safeReturnTo(
      new URLSearchParams(window.location.search).get("returnTo") ?? document.referrer,
      window.location.origin,
    );
  });

  async function handleSubmit() {
    loading = true;
    try {
      await login(email, password);
      window.location.href = returnTo;
    } catch (error: any) {
      const message = error?.code === "LOGIN_INVALID_CREDENTIALS"
        ? $translator("auth.invalidCredentials")
        : $translator("auth.error");
      toaster.error($translator("auth.signIn"), message);
    } finally {
      loading = false;
    }
  }
</script>

<form onsubmit={(event) => { event.preventDefault(); handleSubmit(); }} class="flex flex-col gap-4">
  <label class="flex flex-col gap-1.5">
    <span class="text-sm font-medium" style="color: var(--vercel-text-secondary);">{$translator("auth.email")}</span>
    <input type="email" bind:value={email} class="input" placeholder="you@example.com" required />
  </label>
  <label class="flex flex-col gap-1.5">
    <span class="text-sm font-medium" style="color: var(--vercel-text-secondary);">{$translator("auth.password")}</span>
    <input type="password" bind:value={password} class="input" placeholder="••••••••" required />
  </label>
  <button type="submit" class="btn btn-primary" disabled={loading}>
    {loading ? $translator("auth.signingIn") : $translator("auth.signIn")}
  </button>
  <p class="text-center text-sm" style="color: var(--vercel-text-tertiary);">
    {$translator("auth.noAccount")}
    <a href={`/register?returnTo=${encodeURIComponent(safeReturnTo(returnTo))}`} class="auth-link">{$translator("auth.register")}</a>
  </p>
</form>

<style>
  .auth-link { color: var(--vercel-text-secondary); font-weight: 500; transition: color .15s ease; }
  .auth-link:hover { color: var(--vercel-text); }
</style>
