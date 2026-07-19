<script lang="ts">
  import { translateError, translator } from "../../lib/i18n";
  import { register } from "../../stores/auth";
  import { toaster } from "../../stores/toaster";

  let email = "";
  let username = "";
  let password = "";
  let loading = false;

  async function handleSubmit() {
    loading = true;
    try {
      await register(email, username, password);
      window.location.href = "/";
    } catch (error) {
      toaster.error(
        $translator("auth.register"),
        translateError(error, $translator, "auth.registerError"),
      );
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
    <span class="text-sm font-medium" style="color: var(--vercel-text-secondary);">{$translator("auth.username")}</span>
    <input type="text" bind:value={username} class="input" placeholder={$translator("auth.username")} required minlength="2" />
  </label>
  <label class="flex flex-col gap-1.5">
    <span class="text-sm font-medium" style="color: var(--vercel-text-secondary);">{$translator("auth.password")}</span>
    <input type="password" bind:value={password} class="input" placeholder="8+ characters" required minlength="8" />
  </label>
  <button type="submit" class="btn btn-primary" disabled={loading}>
    {loading ? $translator("auth.creatingAccount") : $translator("auth.register")}
  </button>
  <p class="text-center text-sm" style="color: var(--vercel-text-tertiary);">
    {$translator("auth.haveAccount")}
    <a href="/login" class="font-medium transition-colors" style="color: var(--vercel-text-secondary);">{$translator("auth.signIn")}</a>
  </p>
</form>
