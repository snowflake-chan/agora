<script lang="ts">
  import { onMount } from "svelte";
  import { ExternalLinkIcon, LockKeyholeIcon, LogOutIcon, StarIcon, UserRoundIcon } from "@lucide/svelte";
  import { initAuth, currentUser, updateProfile, logout } from "../../stores/auth";
  import type { UserUpdateData } from "../../lib/auth";

  let saving = $state(false);
  let message = $state<{ type: "success" | "error"; text: string } | null>(null);
  let editForm = $state<UserUpdateData>({});
  let newPassword = $state("");
  let confirmPassword = $state("");

  onMount(() => initAuth());

  $effect(() => {
    if ($currentUser) {
      editForm = {
        username: $currentUser.username,
        nickname: $currentUser.nickname ?? "",
        bio: $currentUser.bio ?? "",
        email: $currentUser.email,
      };
    }
  });

  async function handleSave() {
    saving = true;
    message = null;
    const data: UserUpdateData = {};

    if (editForm.username && editForm.username !== $currentUser?.username) data.username = editForm.username;
    if ((editForm.nickname ?? "") !== ($currentUser?.nickname ?? "")) data.nickname = editForm.nickname || null;
    if ((editForm.bio ?? "") !== ($currentUser?.bio ?? "")) data.bio = editForm.bio || null;
    if (editForm.email && editForm.email !== $currentUser?.email) data.email = editForm.email;

    if (newPassword) {
      if (newPassword.length < 8) {
        message = { type: "error", text: "密码至少需要 8 位" };
        saving = false;
        return;
      }
      if (newPassword !== confirmPassword) {
        message = { type: "error", text: "两次输入的密码不一致" };
        saving = false;
        return;
      }
      data.password = newPassword;
    }

    if (Object.keys(data).length === 0) {
      message = { type: "error", text: "当前没有需要保存的修改" };
      saving = false;
      return;
    }

    try {
      await updateProfile(data);
      if (data.password) {
        // Password change invalidates current session — force re-login.
        message = { type: "success", text: "密码已更新，即将退出登录..." };
        saving = false;
        setTimeout(() => {
          logout();
          window.location.href = "/login";
        }, 1500);
        return;
      }
      message = { type: "success", text: "设置已保存" };
      newPassword = "";
      confirmPassword = "";
    } catch (error: any) {
      message = { type: "error", text: error?.message ?? "保存失败，请稍后重试" };
    } finally {
      saving = false;
    }
  }

  async function handleLogout() {
    await logout();
    window.location.href = "/";
  }
</script>

{#if !$currentUser}
  <div class="empty-state settings-signed-out">
    <p>登录后才能管理账户设置。</p>
    <a href="/login?returnTo=%2Fmy" class="btn btn-primary btn-sm mt-3">前往登录</a>
  </div>
{:else}
  <form class="settings-shell" onsubmit={(event) => { event.preventDefault(); handleSave(); }}>
    <header class="settings-heading">
      <div class="identity-avatar" aria-hidden="true">
        {($currentUser.nickname ?? $currentUser.username)[0].toUpperCase()}
      </div>
      <div>
        <p class="settings-kicker">账户</p>
        <h1>个人设置</h1>
        <p>管理公开身份、登录邮箱和账户安全。</p>
        <div class="points-badge">
          <StarIcon size={14} />
          <span>{$currentUser.points ?? 0} 积分</span>
        </div>
      </div>
      <a class="public-profile-link" href="/users/{$currentUser.id}">
        查看公开主页
        <ExternalLinkIcon size={14} strokeWidth={1.8} />
      </a>
    </header>

    {#if message}
      <div class:success={message.type === "success"} class:error={message.type === "error"} class="settings-message" role="status">
        {message.text}
      </div>
    {/if}

    <div class="settings-layout">
      <nav class="settings-index" aria-label="设置分区">
        <a href="#identity"><UserRoundIcon size={16} />公开身份</a>
        <a href="#security"><LockKeyholeIcon size={16} />账户安全</a>
        <a href="#session"><LogOutIcon size={16} />登录状态</a>
      </nav>

      <div class="settings-content">
        <section id="identity" class="settings-section">
          <div class="section-copy">
            <p class="section-number">01</p>
            <div>
              <h2>公开身份</h2>
              <p>这些信息会显示在帖子、回复和个人主页中。</p>
            </div>
          </div>
          <div class="field-grid">
            <label>
              <span>用户名</span>
              <input class="input" type="text" bind:value={editForm.username} autocomplete="username" required />
              <small>用于个人主页地址和站内识别。</small>
            </label>
            <label>
              <span>显示昵称</span>
              <input class="input" type="text" bind:value={editForm.nickname} placeholder="其他人看到的名字" />
              <small>留空时显示用户名。</small>
            </label>
            <label class="field-wide">
              <span>个人简介</span>
              <textarea class="input bio-input" rows="4" bind:value={editForm.bio} placeholder="介绍你的关注方向和参与领域" maxlength="500"></textarea>
              <small class="character-count">{(editForm.bio ?? "").length} / 500</small>
            </label>
          </div>
        </section>

        <section id="security" class="settings-section">
          <div class="section-copy">
            <p class="section-number">02</p>
            <div>
              <h2>账户安全</h2>
              <p>邮箱用于登录；只有在需要更换密码时才填写密码区域。</p>
            </div>
          </div>
          <div class="field-grid">
            <label class="field-wide">
              <span>登录邮箱</span>
              <input class="input" type="email" bind:value={editForm.email} autocomplete="email" required />
            </label>
            <label>
              <span>新密码 <em>可选</em></span>
              <input class="input" type="password" bind:value={newPassword} placeholder="至少 8 位" autocomplete="new-password" minlength="8" />
            </label>
            <label>
              <span>确认新密码</span>
              <input class="input" type="password" bind:value={confirmPassword} placeholder="再次输入" autocomplete="new-password" />
            </label>
          </div>
        </section>

        <section id="session" class="settings-section session-section">
          <div class="section-copy">
            <p class="section-number">03</p>
            <div>
              <h2>登录状态</h2>
              <p>退出当前设备上的 Agora 账户。</p>
            </div>
          </div>
          <button type="button" class="logout-action" onclick={handleLogout}>
            <LogOutIcon size={16} strokeWidth={1.8} />
            退出登录
          </button>
        </section>
      </div>
    </div>

    <footer class="save-bar">
      <p>修改仅在点击保存后生效。</p>
      <button class="btn btn-primary" type="submit" disabled={saving}>
        {saving ? "保存中…" : "保存设置"}
      </button>
    </footer>
  </form>
{/if}

<style>
  .settings-shell { --settings-line:rgba(255,255,255,.075); padding-bottom:7rem; }
  .settings-heading { display:grid; grid-template-columns:auto minmax(0,1fr) auto; align-items:center; gap:1rem; padding:1.5rem 0 2.25rem; border-bottom:1px solid var(--settings-line); }
  .identity-avatar { display:grid; width:3.5rem; height:3.5rem; place-items:center; border-radius:1rem; background:var(--vercel-text); color:var(--vercel-bg); font-size:1.25rem; font-weight:700; }
  .settings-kicker,.section-number { color:var(--vercel-text-tertiary); font-size:.6875rem; font-weight:650; letter-spacing:.12em; }
  .settings-heading h1 { margin:.15rem 0 .2rem; color:var(--vercel-text); font-size:clamp(1.65rem,3vw,2.25rem); font-weight:650; letter-spacing:-.045em; line-height:1; }
  .settings-heading > div > p:last-child,.section-copy p:last-child { color:var(--vercel-text-tertiary); font-size:.8125rem; line-height:1.5; }
  .points-badge { display:inline-flex; align-items:center; gap:.35rem; margin-top:.35rem; padding:.2rem .55rem; background:rgba(250,204,21,.12); border:1px solid rgba(250,204,21,.2); border-radius:9999px; color:#facc15; font-size:.6875rem; font-weight:600; }
  .public-profile-link { display:flex; align-items:center; gap:.4rem; color:var(--vercel-text-secondary); font-size:.75rem; font-weight:550; transition:color .18s ease; }
  .public-profile-link:hover { color:var(--vercel-text); }
  .settings-message { margin-top:1rem; padding:.75rem 1rem; border:1px solid; border-radius:.65rem; font-size:.8125rem; }
  .settings-message.success { border-color:rgba(34,197,94,.22); background:rgba(34,197,94,.07); color:var(--vercel-success); }
  .settings-message.error { border-color:rgba(239,68,68,.22); background:rgba(239,68,68,.07); color:var(--vercel-danger); }
  .settings-layout { display:grid; grid-template-columns:11rem minmax(0,1fr); gap:clamp(2rem,6vw,5rem); padding-top:2.25rem; }
  .settings-index { position:sticky; top:5rem; display:flex; height:max-content; flex-direction:column; gap:.25rem; }
  .settings-index a { display:flex; align-items:center; gap:.6rem; padding:.55rem .65rem; border-radius:.5rem; color:var(--vercel-text-tertiary); font-size:.75rem; transition:background .18s ease,color .18s ease; }
  .settings-index a:hover,.settings-index a:focus-visible { background:rgba(255,255,255,.05); color:var(--vercel-text); }
  .settings-content { min-width:0; }
  .settings-section { display:grid; grid-template-columns:minmax(11rem,.8fr) minmax(0,1.4fr); gap:clamp(1.5rem,5vw,4rem); padding:0 0 3rem; scroll-margin-top:5rem; }
  .settings-section + .settings-section { padding-top:3rem; border-top:1px solid var(--settings-line); }
  .section-copy { display:grid; grid-template-columns:1.5rem 1fr; gap:.5rem; align-content:start; }
  .section-copy h2 { margin-bottom:.45rem; color:var(--vercel-text); font-size:1rem; font-weight:620; letter-spacing:-.02em; }
  .field-grid { display:grid; grid-template-columns:1fr 1fr; gap:1.25rem 1rem; }
  .field-grid label { display:flex; min-width:0; flex-direction:column; gap:.45rem; }
  .field-grid label > span { color:var(--vercel-text-secondary); font-size:.75rem; font-weight:550; }
  .field-grid em { color:var(--vercel-text-tertiary); font-style:normal; font-weight:400; }
  .field-grid small { color:var(--vercel-text-tertiary); font-size:.6875rem; line-height:1.4; }
  .field-wide { grid-column:1/-1; }
  .bio-input { min-height:7rem; resize:vertical; }
  .character-count { align-self:flex-end; font-variant-numeric:tabular-nums; }
  .session-section { align-items:start; }
  .logout-action { display:flex; width:max-content; align-items:center; gap:.5rem; padding:.55rem .75rem; border:1px solid rgba(239,68,68,.22); border-radius:.55rem; color:var(--vercel-danger); font-size:.75rem; font-weight:550; transition:background .18s ease,transform .18s ease; }
  .logout-action:hover { background:rgba(239,68,68,.08); }
  .logout-action:active { transform:translateY(1px); }
  .save-bar { position:fixed; z-index:30; right:0; bottom:0; left:0; display:flex; align-items:center; justify-content:flex-end; gap:1rem; padding:.65rem max(1rem,calc((100vw - 68rem)/2)); border-top:1px solid var(--settings-line); background:rgba(12,12,14,.88); backdrop-filter:blur(20px); }
  .save-bar p { color:var(--vercel-text-tertiary); font-size:.6875rem; }
  .settings-signed-out { margin-top:4rem; }
  @media (max-width:52rem) {
    .settings-layout { grid-template-columns:1fr; gap:1.5rem; }
    .settings-index { position:static; flex-direction:row; overflow-x:auto; padding-bottom:.35rem; }
    .settings-index a { flex:0 0 auto; }
    .settings-section { grid-template-columns:1fr; gap:1.5rem; }
  }
  @media (max-width:36rem) {
    .settings-heading { grid-template-columns:auto 1fr; align-items:start; }
    .public-profile-link { grid-column:2; }
    .field-grid { grid-template-columns:1fr; }
    .field-wide { grid-column:auto; }
    .save-bar { justify-content:space-between; padding-bottom:calc(.65rem + env(safe-area-inset-bottom)); }
    .save-bar p { display:none; }
    .save-bar .btn { width:100%; }
  }
</style>
