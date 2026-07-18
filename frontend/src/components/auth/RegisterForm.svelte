<script lang="ts">
  import { register } from "../../stores/auth";
  import { toaster } from "../../stores/toaster";

  let email = "";
  let username = "";
  let password = "";
  let loading = false;

  const ERROR_MAP: Record<string, string> = {
    REGISTER_EMAIL_TAKEN: "邮箱已被注册",
    REGISTER_USERNAME_TAKEN: "用户名已被使用",
    REGISTER_PASSWORD_TOO_SHORT: "密码至少需要 8 个字符",
  };

  async function handleSubmit() {
    loading = true;
    try {
      await register(email, username, password);
      window.location.href = "/";
    } catch (e: any) {
      toaster.error("注册失败", ERROR_MAP[e.code] ?? e.code ?? "请稍后重试");
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
    <span class="text-sm font-medium" style="color: var(--vercel-text-secondary);">用户名</span>
    <input
      type="text"
      bind:value={username}
      class="input"
      placeholder="你的用户名"
      required
      minlength="2"
    />
  </label>

  <label class="flex flex-col gap-1.5">
    <span class="text-sm font-medium" style="color: var(--vercel-text-secondary);">密码</span>
    <input
      type="password"
      bind:value={password}
      class="input"
      placeholder="至少 8 个字符"
      required
      minlength="8"
    />
  </label>

  <button type="submit" class="btn btn-primary" disabled={loading}>
    {loading ? "注册中..." : "注册"}
  </button>

  <p class="text-center text-sm" style="color: var(--vercel-text-tertiary);">
    已有账号？
    <a href="/login" class="font-medium transition-colors" style="color: var(--vercel-text-secondary);" onmouseenter={(e) => e.currentTarget.style.color = 'var(--vercel-text)'} onmouseleave={(e) => e.currentTarget.style.color = 'var(--vercel-text-secondary)'}>登录</a>
  </p>
</form>