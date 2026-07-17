<script lang="ts">
  import { register } from "../../stores/auth";
  import { toaster } from "../../stores/toaster";

  let email = "";
  let username = "";
  let password = "";
  let confirmPassword = "";
  let loading = false;

  const ERROR_MAP: Record<string, string> = {
    REGISTER_EMAIL_TAKEN: "该邮箱已被注册",
    REGISTER_USERNAME_TAKEN: "该用户名已被使用",
    REGISTER_PASSWORD_TOO_SHORT: "密码至少需要 8 位",
  };

  async function handleSubmit() {
    if (password !== confirmPassword) {
      toaster.error({ title: "注册失败", description: "两次密码不一致" });
      return;
    }
    loading = true;
    try {
      await register(email, username, password);
      window.location.href = "/";
    } catch (e: any) {
      toaster.error({
        title: "注册失败",
        description: ERROR_MAP[e.code] ?? e.code ?? "请稍后重试",
      });
    } finally {
      loading = false;
    }
  }
</script>

<form on:submit|preventDefault={handleSubmit} class="flex flex-col gap-5">
  <label class="label">
    <span class="label-text">用户名</span>
    <input
      type="text"
      bind:value={username}
      class="input placeholder:text-surface-400"
      placeholder="your_username"
      required
      minlength={3}
    />
  </label>

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
      placeholder="至少 8 位"
      required
      minlength={8}
    />
  </label>

  <label class="label">
    <span class="label-text">确认密码</span>
    <input
      type="password"
      bind:value={confirmPassword}
      class="input placeholder:text-surface-400"
      placeholder="再次输入密码"
      required
      minlength={8}
    />
  </label>

  <button type="submit" class="btn preset-filled-primary-500" disabled={loading}>
    {#if loading}注册中…{:else}注册{/if}
  </button>

  <p class="text-center text-sm text-surface-500">
    已有账号？
    <a href="/login" class="font-medium text-primary-600 hover:text-primary-700">登录</a>
  </p>
</form>
