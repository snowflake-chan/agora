<script lang="ts">
  import { login } from "../../stores/auth";
  import { toaster } from "../../stores/toaster";

  let email = "";
  let password = "";
  let loading = false;

  const ERROR_MAP: Record<string, string> = {
    LOGIN_INVALID_CREDENTIALS: "邮箱或密码错误",
  };

  async function handleSubmit() {
    loading = true;
    try {
      await login(email, password);
      window.location.href = "/";
    } catch (e: any) {
      toaster.error({
        title: "登录失败",
        description: ERROR_MAP[e.code] ?? e.code ?? "请稍后重试",
      });
    } finally {
      loading = false;
    }
  }
</script>

<form on:submit|preventDefault={handleSubmit} class="flex flex-col gap-5">
  <label class="label">
    <span class="label-text">邮箱</span>
    <input
      type="email"
      bind:value={email}
      class="input placeholder:text-surface-400"
      placeholder="you@example.com"
      required
    />
  </label>

  <label class="label">
    <span class="label-text">密码</span>
    <input
      type="password"
      bind:value={password}
      class="input placeholder:text-surface-400"
      placeholder="••••••••"
      required
    />
  </label>

  <button type="submit" class="btn preset-filled-primary-500" disabled={loading}>
    {#if loading}登录中…{:else}登录{/if}
  </button>

  <p class="text-center text-sm text-surface-500">
    还没有账号？
    <a href="/register" class="font-medium text-primary-600 hover:text-primary-700">注册</a>
  </p>
</form>
