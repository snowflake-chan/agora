<script lang="ts">
  import { onMount } from "svelte";
  import { translateError, translator } from "../../lib/i18n";
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

    if (editForm.username && editForm.username !== $currentUser?.username) {
      data.username = editForm.username;
    }
    if ((editForm.nickname ?? "") !== ($currentUser?.nickname ?? "")) {
      data.nickname = editForm.nickname || null;
    }
    if ((editForm.bio ?? "") !== ($currentUser?.bio ?? "")) {
      data.bio = editForm.bio || null;
    }
    if (editForm.email && editForm.email !== $currentUser?.email) {
      data.email = editForm.email;
    }

    // Password change
    if (newPassword) {
      if (newPassword.length < 8) {
        message = { type: "error", text: $translator("profile.passwordTooShort") };
        saving = false;
        return;
      }
      if (newPassword !== confirmPassword) {
        message = { type: "error", text: $translator("profile.passwordMismatch") };
        saving = false;
        return;
      }
      data.password = newPassword;
    }

    if (Object.keys(data).length === 0) {
      message = { type: "error", text: $translator("profile.noChanges") };
      saving = false;
      return;
    }

    try {
      await updateProfile(data);
      message = { type: "success", text: $translator("profile.updated") };
      newPassword = "";
      confirmPassword = "";
    } catch (e: any) {
      message = {
        type: "error",
        text: translateError(e, $translator, "profile.updateFailed"),
      };
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
  <div class="empty-state">
    <p>{$translator("profile.signInRequired")}</p>
    <a href="/login" class="btn btn-primary btn-sm mt-3">{$translator("profile.goSignIn")}</a>
  </div>
{:else}
  <div class="card p-6 mb-6">
    <div class="flex items-center gap-4 mb-6">
      <div class="avatar" style="width: 3.5rem; height: 3.5rem; font-size: 1.5rem;">
        {($currentUser.nickname ?? $currentUser.username)[0].toUpperCase()}
      </div>
      <div>
        <h1 class="text-xl font-bold" style="color: var(--vercel-text);">{$translator("profile.myProfile")}</h1>
        <p class="text-sm" style="color: var(--vercel-text-tertiary);">{$translator("profile.editDescription")}</p>
      </div>
    </div>

    {#if message}
      <div
        class="mb-4 p-3 rounded-md text-sm"
        style="background: {message.type === 'success' ? 'var(--vercel-success-bg)' : 'rgba(239,68,68,0.1)'}; color: {message.type === 'success' ? 'var(--vercel-success)' : 'var(--vercel-danger)'};"
      >
        {message.text}
      </div>
    {/if}

    <div class="space-y-4">
      <!-- Username -->
      <div>
        <label class="block text-xs mb-1" style="color: var(--vercel-text-secondary);">{$translator("auth.username")}</label>
        <input
          class="input"
          type="text"
          bind:value={editForm.username}
          placeholder={$translator("auth.username")}
        />
      </div>

      <!-- Nickname -->
      <div>
        <label class="block text-xs mb-1" style="color: var(--vercel-text-secondary);">{$translator("profile.displayName")}</label>
        <input
          class="input"
          type="text"
          bind:value={editForm.nickname}
          placeholder={$translator("profile.displayNamePlaceholder")}
        />
      </div>

      <!-- Bio -->
      <div>
        <label class="block text-xs mb-1" style="color: var(--vercel-text-secondary);">{$translator("profile.bio")}</label>
        <textarea
          class="input"
          rows="3"
          bind:value={editForm.bio}
          placeholder={$translator("profile.bioPlaceholder")}
          maxlength="500"
        ></textarea>
        <p class="text-xs mt-1" style="color: var(--vercel-text-tertiary);">{(editForm.bio ?? "").length}/500</p>
      </div>

      <!-- Email -->
      <div>
        <label class="block text-xs mb-1" style="color: var(--vercel-text-secondary);">{$translator("auth.email")}</label>
        <input
          class="input"
          type="email"
          bind:value={editForm.email}
          placeholder="your@email.com"
        />
      </div>

      <div class="divider"></div>

      <!-- Password -->
      <div>
        <label class="block text-xs mb-1" style="color: var(--vercel-text-secondary);">{$translator("profile.newPassword")}</label>
        <input
          class="input"
          type="password"
          bind:value={newPassword}
          placeholder={$translator("profile.newPasswordPlaceholder")}
        />
      </div>

      <div>
        <label class="block text-xs mb-1" style="color: var(--vercel-text-secondary);">{$translator("profile.confirmPassword")}</label>
        <input
          class="input"
          type="password"
          bind:value={confirmPassword}
          placeholder={$translator("profile.confirmPasswordPlaceholder")}
        />
      </div>
    </div>

    <div class="flex items-center justify-between mt-6 pt-4 border-t" style="border-color: var(--vercel-border);">
      <button class="btn btn-ghost btn-sm" style="color: var(--vercel-danger);" onclick={handleLogout}>
        {$translator("common.logout")}
      </button>
      <button class="btn btn-primary" onclick={handleSave} disabled={saving}>
        {saving ? $translator("profile.saving") : $translator("profile.save")}
      </button>
    </div>
  </div>

  <div class="flex justify-center gap-4 text-sm">
    <a href="/users/{$currentUser.id}" style="color: var(--vercel-text-secondary);">{$translator("profile.viewPublic")}</a>
  </div>
{/if}
