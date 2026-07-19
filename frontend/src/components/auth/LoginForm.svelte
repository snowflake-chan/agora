<script lang="ts">
  import { onMount } from "svelte";
  import { login } from "../../stores/auth";
  import { toaster } from "../../stores/toaster";
  import { safeReturnTo } from "../../lib/returnTo";

  let email = "";
  let password = "";
  let loading = false;
  let returnTo = "/";

  onMount(() => {
    returnTo = safeReturnTo(
      new URLSearchParams(window.location.search).get("returnTo")
        ?? document.referrer,
      window.location.origin,
    );
  });

  const ERROR_MAP: Record<string, string> = {
    LOGIN_INVALID_CREDENTIALS: "邮箱或密码错误",
  };

  async function handleSubmit() {
    loading = true;
    try {
      await login(email, password);
      window.location.href = returnTo;
    } catch (e: any) {
      toaster.error("登录失败", ERROR_MAP[e.code] ?? e.code ?? "请稍后重试");
    } finally {
      loading = false;
    }
  }
</script>

<form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="flex flex-col gap-4">
  <label class="flex flex-col gap-1.5">
    <span class="text-sm font-medium" style="color: var(--vercel-text-secondary);">邮箱</span>
    <input
      type="email"
      bind:value={email}
      class="input"
      placeholder="you@example.com"
      required
    />
  </label>

  <label class="flex flex-col gap-1.5">
    <span class="text-sm font-medium" style="color: var(--vercel-text-secondary);">密码</span>
    <input
      type="password"
      bind:value={password}
      class="input"
      placeholder="••••••••"
      required
    />
  </label>

  <button type="submit" class="btn btn-primary" disabled={loading}>
    {loading ? "登录中..." : "登录"}
  </button>

  <p class="text-center text-sm" style="color: var(--vercel-text-tertiary);">
    还没有账号？
    <a href={`/register?returnTo=${encodeURIComponent(safeReturnTo(returnTo))}`} class="auth-link">注册</a>
  </p>
</form>

<style>
  .auth-link { color:var(--vercel-text-secondary); font-weight:500; transition:color .15s ease; }
  .auth-link:hover { color:var(--vercel-text); }
</style>
