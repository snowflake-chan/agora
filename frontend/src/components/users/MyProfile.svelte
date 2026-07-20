<script lang="ts">
  import { onMount } from "svelte";
  import {
    ExternalLink,
    LockKeyhole,
    LogOut,
    UserRound,
  } from "@lucide/svelte";
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
      if (data.password) {
        message = {
          type: "success",
          text: $translator("profile.passwordUpdatedSignIn"),
        };
        window.setTimeout(() => {
          void logout().finally(() => {
            window.location.assign("/login?returnTo=%2Fmy");
          });
        }, 1200);
        return;
      }
      message = { type: "success", text: $translator("profile.updated") };
      newPassword = "";
      confirmPassword = "";
    } catch (error) {
      message = {
        type: "error",
        text: translateError(error, $translator, "profile.updateFailed"),
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
  <div class="empty-state signed-out">
    <p>{$translator("profile.signInRequired")}</p>
    <a href="/login?returnTo=%2Fmy" class="btn btn-primary btn-sm mt-3">
      {$translator("profile.goSignIn")}
    </a>
  </div>
{:else}
  <form
    class="profile-settings"
    onsubmit={(event) => {
      event.preventDefault();
      void handleSave();
    }}
  >
    <header class="profile-heading">
      <a
        class="identity-link"
        href="/users/{$currentUser.id}"
        aria-label={$translator("profile.viewPublic")}
      >
        <span class="identity-avatar" aria-hidden="true">
          {($currentUser.nickname ?? $currentUser.username)[0].toUpperCase()}
        </span>
        <span class="identity-copy">
          <strong>{$currentUser.nickname ?? $currentUser.username}</strong>
          <small>@{$currentUser.username}</small>
        </span>
      </a>

      <div class="heading-copy">
        <p class="settings-kicker">{$translator("profile.accountEyebrow")}</p>
        <h1>{$translator("profile.settingsTitle")}</h1>
        <p>{$translator("profile.settingsDescription")}</p>
      </div>

      <a class="public-profile-link" href="/users/{$currentUser.id}">
        {$translator("profile.viewPublic")}
        <ExternalLink size={14} strokeWidth={1.8} />
      </a>
    </header>

    {#if message}
      <div
        class:success={message.type === "success"}
        class:error={message.type === "error"}
        class="settings-message"
        role="status"
      >
        {message.text}
      </div>
    {/if}

    <div class="settings-layout">
      <nav class="settings-index" aria-label={$translator("profile.sectionNav")}>
        <a href="#identity"><UserRound size={16} />{$translator("profile.publicIdentity")}</a>
        <a href="#security"><LockKeyhole size={16} />{$translator("profile.security")}</a>
        <a href="#session"><LogOut size={16} />{$translator("profile.session")}</a>
      </nav>

      <div class="settings-content">
        <section id="identity" class="settings-section">
          <div class="section-copy">
            <span class="section-number">01</span>
            <div>
              <h2>{$translator("profile.publicIdentity")}</h2>
              <p>{$translator("profile.publicIdentityDescription")}</p>
            </div>
          </div>

          <div class="field-grid">
            <label>
              <span>{$translator("auth.username")}</span>
              <input
                class="input"
                type="text"
                bind:value={editForm.username}
                autocomplete="username"
                maxlength="50"
                required
              />
              <small>{$translator("profile.usernameHelp")}</small>
            </label>

            <label>
              <span>{$translator("profile.displayName")}</span>
              <input
                class="input"
                type="text"
                bind:value={editForm.nickname}
                placeholder={$translator("profile.displayNamePlaceholder")}
                maxlength="100"
              />
              <small>{$translator("profile.displayNameHelp")}</small>
            </label>

            <label class="field-wide">
              <span>{$translator("profile.bio")}</span>
              <textarea
                class="input bio-input"
                rows="4"
                bind:value={editForm.bio}
                placeholder={$translator("profile.bioPlaceholder")}
                maxlength="500"
              ></textarea>
              <small class="character-count">{(editForm.bio ?? "").length} / 500</small>
            </label>
          </div>
        </section>

        <section id="security" class="settings-section">
          <div class="section-copy">
            <span class="section-number">02</span>
            <div>
              <h2>{$translator("profile.security")}</h2>
              <p>{$translator("profile.securityDescription")}</p>
            </div>
          </div>

          <div class="field-grid">
            <label class="field-wide">
              <span>{$translator("auth.email")}</span>
              <input
                class="input"
                type="email"
                bind:value={editForm.email}
                autocomplete="email"
                required
              />
            </label>

            <label>
              <span>
                {$translator("profile.newPassword")}
                <em>{$translator("profile.optional")}</em>
              </span>
              <input
                class="input"
                type="password"
                bind:value={newPassword}
                placeholder={$translator("profile.newPasswordPlaceholder")}
                autocomplete="new-password"
                minlength="8"
              />
            </label>

            <label>
              <span>{$translator("profile.confirmPassword")}</span>
              <input
                class="input"
                type="password"
                bind:value={confirmPassword}
                placeholder={$translator("profile.confirmPasswordPlaceholder")}
                autocomplete="new-password"
              />
            </label>
          </div>
        </section>

        <section id="session" class="settings-section session-section">
          <div class="section-copy">
            <span class="section-number">03</span>
            <div>
              <h2>{$translator("profile.session")}</h2>
              <p>{$translator("profile.sessionDescription")}</p>
            </div>
          </div>

          <button type="button" class="logout-action" onclick={handleLogout}>
            <LogOut size={16} strokeWidth={1.8} />
            {$translator("common.logout")}
          </button>
        </section>
      </div>
    </div>

    <footer class="save-bar">
      <p>{$translator("profile.saveHint")}</p>
      <button class="btn btn-primary" type="submit" disabled={saving}>
        {$translator(saving ? "profile.saving" : "profile.save")}
      </button>
    </footer>
  </form>
{/if}

<style>
  .profile-settings {
    --settings-line: var(--vercel-border);
    padding-bottom: 2rem;
  }

  .profile-heading {
    display: grid;
    grid-template-columns: minmax(10rem, auto) minmax(0, 1fr) auto;
    align-items: center;
    gap: 1.5rem;
    padding: 1.5rem 0 2rem;
    border-bottom: 1px solid var(--settings-line);
  }

  .identity-link {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    min-width: 0;
    padding: 0.35rem;
    border-radius: var(--vercel-radius);
  }

  .identity-link:hover {
    background: var(--vercel-hover);
  }

  .identity-avatar {
    display: grid;
    width: 3.5rem;
    height: 3.5rem;
    place-items: center;
    flex: 0 0 auto;
    border-radius: var(--vercel-radius-lg);
    color: var(--vercel-bg);
    background: var(--vercel-text);
    font-size: 1.25rem;
    font-weight: 700;
  }

  .identity-copy {
    display: grid;
    min-width: 0;
  }

  .identity-copy strong,
  .identity-copy small {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .identity-copy strong {
    color: var(--vercel-text);
    font-size: 0.875rem;
  }

  .identity-copy small,
  .settings-kicker,
  .section-number {
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
  }

  .heading-copy {
    min-width: 0;
  }

  .heading-copy h1 {
    margin: 0.2rem 0 0.35rem;
    font-size: 1.75rem;
    line-height: 1.15;
    letter-spacing: 0;
  }

  .heading-copy > p:last-child,
  .section-copy p {
    max-width: 58ch;
    margin: 0;
    color: var(--vercel-text-tertiary);
    font-size: 0.8125rem;
    line-height: 1.55;
  }

  .public-profile-link {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--vercel-text-secondary);
    font-size: 0.75rem;
    font-weight: 550;
  }

  .public-profile-link:hover {
    color: var(--vercel-text);
  }

  .settings-message {
    margin-top: 1rem;
    padding: 0.75rem 1rem;
    border-left: 3px solid;
    font-size: 0.8125rem;
  }

  .settings-message.success {
    color: var(--vercel-success);
    background: var(--vercel-success-bg);
    border-color: var(--vercel-success);
  }

  .settings-message.error {
    color: var(--vercel-danger);
    background: color-mix(in srgb, var(--vercel-danger) 9%, transparent);
    border-color: var(--vercel-danger);
  }

  .settings-layout {
    display: grid;
    grid-template-columns: 11rem minmax(0, 1fr);
    gap: 3rem;
    padding-top: 2rem;
  }

  .settings-index {
    position: sticky;
    top: 5rem;
    display: flex;
    height: max-content;
    flex-direction: column;
    gap: 0.25rem;
  }

  .settings-index a {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.55rem 0.65rem;
    border-radius: var(--vercel-radius-sm);
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
    transition: background 180ms ease, color 180ms ease;
  }

  .settings-index a:hover,
  .settings-index a:focus-visible {
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .settings-content {
    min-width: 0;
  }

  .settings-section {
    display: grid;
    grid-template-columns: minmax(11rem, 0.8fr) minmax(0, 1.4fr);
    gap: 2.5rem;
    padding: 0 0 3rem;
    scroll-margin-top: 5rem;
  }

  .settings-section + .settings-section {
    padding-top: 3rem;
    border-top: 1px solid var(--settings-line);
  }

  .section-copy {
    display: grid;
    grid-template-columns: 1.5rem 1fr;
    gap: 0.5rem;
    align-content: start;
  }

  .section-copy h2 {
    margin: 0 0 0.45rem;
    font-size: 1rem;
    line-height: 1.3;
    letter-spacing: 0;
  }

  .field-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.25rem 1rem;
  }

  .field-grid label {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: 0.45rem;
  }

  .field-grid label > span {
    color: var(--vercel-text-secondary);
    font-size: 0.75rem;
    font-weight: 550;
  }

  .field-grid em {
    margin-left: 0.35rem;
    color: var(--vercel-text-tertiary);
    font-style: normal;
    font-weight: 400;
  }

  .field-grid small {
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
    line-height: 1.4;
  }

  .field-wide {
    grid-column: 1 / -1;
  }

  .bio-input {
    min-height: 7rem;
    resize: vertical;
  }

  .character-count {
    align-self: flex-end;
    font-variant-numeric: tabular-nums;
  }

  .session-section {
    align-items: start;
  }

  .logout-action {
    display: flex;
    width: max-content;
    align-items: center;
    gap: 0.5rem;
    padding: 0.55rem 0.75rem;
    color: var(--vercel-danger);
    background: transparent;
    border: 1px solid color-mix(in srgb, var(--vercel-danger) 24%, transparent);
    border-radius: var(--vercel-radius-sm);
    cursor: pointer;
    font: inherit;
    font-size: 0.75rem;
    font-weight: 550;
    transition: background 180ms ease, transform 180ms ease;
  }

  .logout-action:hover {
    background: color-mix(in srgb, var(--vercel-danger) 8%, transparent);
  }

  .logout-action:active {
    transform: translateY(1px);
  }

  .save-bar {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--settings-line);
  }

  .save-bar p {
    margin: 0;
    color: var(--vercel-text-tertiary);
    font-size: 0.6875rem;
  }

  .signed-out {
    margin-top: 4rem;
  }

  @media (max-width: 52rem) {
    .profile-heading {
      grid-template-columns: minmax(0, 1fr) auto;
    }

    .identity-link {
      grid-column: 1 / -1;
    }

    .settings-layout {
      grid-template-columns: 1fr;
      gap: 1.5rem;
    }

    .settings-index {
      position: static;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      overflow: visible;
      padding-bottom: 0.35rem;
    }

    .settings-index a {
      min-width: 0;
      min-height: 3.75rem;
      justify-content: center;
      flex-direction: column;
      gap: 0.35rem;
      padding-inline: 0.35rem;
      text-align: center;
      line-height: 1.25;
    }

    .settings-section {
      grid-template-columns: 1fr;
      gap: 1.5rem;
    }
  }

  @media (max-width: 36rem) {
    .profile-heading {
      grid-template-columns: 1fr;
      align-items: start;
      gap: 1rem;
    }

    .identity-link,
    .public-profile-link {
      grid-column: auto;
    }

    .field-grid {
      grid-template-columns: 1fr;
    }

    .field-wide {
      grid-column: auto;
    }

    .save-bar {
      align-items: stretch;
      flex-direction: column;
    }

    .save-bar .btn {
      width: 100%;
    }
  }
</style>
