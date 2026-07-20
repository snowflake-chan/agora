<script lang="ts">
  import { onMount } from "svelte";
  import {
    getGuild,
    listMembers,
    updateGuild,
    type Guild,
    type GuildMember,
  } from "../../lib/guilds";
  import { API_BASE } from "../../lib/config";
  import { translator, translateError } from "../../lib/i18n";
  import { avatarInitial, displayName } from "../../lib/utils";
  import { initAuth, currentUser } from "../../stores/auth";
  import ConfirmDialog from "../ConfirmDialog.svelte";

  let { guildId }: { guildId: string } = $props();
  let guild = $state<Guild | null>(null);
  let members = $state<GuildMember[]>([]);
  let requests = $state<any[]>([]);
  let loading = $state(true);
  let error = $state("");
  let msg = $state("");
  let msgKind = $state<"success" | "error">("success");
  let myRole = $state("");
  let tab = $state<"requests" | "members" | "info">("requests");
  let name = $state("");
  let logo = $state("");
  let description = $state("");
  let saving = $state(false);
  let busyRequestId = $state<string | null>(null);
  let busyMemberId = $state<string | null>(null);
  let confirmOpen = $state(false);
  let confirmDescription = $state("");
  let confirmAction = $state<() => void>(() => {});

  const API = `${API_BASE}/guilds`;

  async function api(path: string, options?: RequestInit) {
    const res = await fetch(`${API}${path}`, { credentials: "include", ...options });
    if (!res.ok) {
      const e = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(e.detail || res.statusText);
    }
    return res.status === 204 ? null : res.json();
  }

  onMount(async () => {
    await initAuth();
    if (!$currentUser) { error = $translator("profile.signInRequired"); loading = false; return; }
    try {
      [guild, members] = await Promise.all([getGuild(guildId), listMembers(guildId)]);
      name = guild.name;
      logo = guild.logo ?? "";
      description = guild.description ?? "";
      const me = members.find(m => m.user_id === $currentUser?.id);
      myRole = me?.role || "";
      if (myRole === "president" || myRole === "vice_president") {
        requests = await api(`/${guildId}/requests`);
      }
    } catch (e: any) {
      error = translateError(e, $translator, "guild.loadFailed");
    }
    loading = false;
  });

  async function approve(reqId: string) {
    if (busyRequestId) return;
    busyRequestId = reqId;
    try {
      await api(`/${guildId}/requests/${reqId}/approve`, {method:"POST"});
      requests = requests.filter(r => r.id !== reqId);
      try { members = await listMembers(guildId); } catch {}
      msg = $translator("guild.requestApproved");
      msgKind = "success";
    }
    catch(e:any) { msg = translateError(e, $translator, "common.operationFailed"); msgKind = "error"; }
    finally { busyRequestId = null; }
  }
  async function reject(reqId: string) {
    if (busyRequestId) return;
    busyRequestId = reqId;
    try { await api(`/${guildId}/requests/${reqId}/reject`, {method:"POST"}); requests = requests.filter(r => r.id !== reqId); msg = $translator("guild.requestRejected"); msgKind = "success"; }
    catch(e:any) { msg = translateError(e, $translator, "common.operationFailed"); msgKind = "error"; }
    finally { busyRequestId = null; }
  }
  async function removeMember(uid: string) {
    if (busyMemberId) return;
    busyMemberId = uid;
    try { await api(`/${guildId}/remove-member/${uid}`, {method:"POST"}); members = members.filter(m => m.user_id !== uid); msg = $translator("guild.memberRemoved"); msgKind = "success"; }
    catch(e:any) { msg = translateError(e, $translator, "common.operationFailed"); msgKind = "error"; }
    finally { busyMemberId = null; }
  }
  async function promoteMember(uid: string, role: string) {
    if (busyMemberId) return;
    busyMemberId = uid;
    try {
      await api(`/${guildId}/promote/${uid}?role=${role}`, {method:"POST"});
      members = members.map((member) =>
        member.user_id === uid ? { ...member, role } : member
      );
      msg = $translator("guild.roleUpdated");
      msgKind = "success";
    }
    catch(e:any) { msg = translateError(e, $translator, "common.operationFailed"); msgKind = "error"; }
    finally { busyMemberId = null; }
  }
  async function updateInfo() {
    if (!name.trim()) {
      msg = $translator("guild.nameRequired");
      msgKind = "error";
      return;
    }
    saving = true;
    try {
      guild = await updateGuild(guildId, {
        name: name.trim(),
        logo: logo.trim() || null,
        description: description.trim() || null,
      });
      msg = $translator("guild.updated");
      msgKind = "success";
    } catch(e:any) {
      msg = translateError(e, $translator, "guild.updateFailed");
      msgKind = "error";
    } finally {
      saving = false;
    }
  }

  function roleLabel(role: string) {
    return $translator(`guild.role.${role}`);
  }

  function confirmRemoval(member: GuildMember) {
    confirmDescription = $translator("guild.removeMemberDescription", {
      name: displayName(member.nickname, member.username),
    });
    confirmAction = () => removeMember(member.user_id);
    confirmOpen = true;
  }
</script>

{#if loading}
  <div class="empty-state"><div class="spinner mb-3"></div></div>
{:else if error}
  <div class="empty-state"><p style="color: var(--vercel-danger);">{error}</p></div>
{:else if myRole !== "president" && myRole !== "vice_president"}
  <div class="empty-state"><p style="color: var(--vercel-danger);">{$translator("guild.manageForbidden")}</p></div>
{:else}
  <header class="manage-header mb-5">
    <p class="text-xs" style="color: var(--vercel-text-tertiary);">{$translator("guild.manageEyebrow")}</p>
    <h1 class="text-xl font-bold" style="color: var(--vercel-text);">{guild?.name}</h1>
  </header>
  {#if msg}
    <div class="manage-message" class:is-error={msgKind === "error"} role={msgKind === "error" ? "alert" : "status"}>{msg}</div>
  {/if}

  <div class="manage-tabs flex gap-1 border-b mb-4" style="border-color: var(--vercel-border);">
    <button class="filter-tab" class:active={tab === "requests"} onclick={()=>tab="requests"}>{$translator("guild.requests")} ({requests.length})</button>
    <button class="filter-tab" class:active={tab === "members"} onclick={()=>tab="members"}>{$translator("guild.memberManagement")} ({members.length})</button>
    {#if myRole === "president"}
      <button class="filter-tab" class:active={tab === "info"} onclick={()=>tab="info"}>{$translator("guild.editInfo")}</button>
    {/if}
  </div>

  {#if tab === "requests"}
    {#if requests.length === 0}
      <div class="empty-state"><p>{$translator("guild.noRequests")}</p></div>
    {:else}
      {#each requests as r (r.id)}
        <div class="request-card card p-3 mb-2 flex items-center justify-between">
          <div class="request-identity">
            <span class="font-medium" style="color: var(--vercel-text);">{displayName(r.nickname, r.username)}</span>
            <span class="text-xs ml-2" style="color: var(--vercel-text-tertiary);">@{r.username}</span>
          </div>
          <div class="request-actions flex gap-1">
            <button class="btn btn-primary btn-xs" onclick={()=>approve(r.id)} disabled={busyRequestId !== null}>{$translator("guild.approve")}</button>
            <button class="btn btn-ghost btn-xs" style="color: var(--vercel-danger);" onclick={()=>reject(r.id)} disabled={busyRequestId !== null}>{$translator("guild.reject")}</button>
          </div>
        </div>
      {/each}
    {/if}

  {:else if tab === "members"}
    {#each members as m (m.id)}
      <div class="member-row card p-3 mb-2 flex items-center justify-between">
        <div class="member-identity flex items-center gap-2">
          <div class="avatar avatar-sm" style="width: 2rem; height: 2rem; font-size: 0.7rem; flex-shrink: 0;">{avatarInitial(m.nickname, m.username)}</div>
          <div>
            <span style="color: var(--vercel-text);">{displayName(m.nickname, m.username)}</span>
            <span class="text-xs ml-1 px-1 py-0.5 rounded" style="background: var(--vercel-hover);color:var(--vercel-text-tertiary);">{roleLabel(m.role)}</span>
          </div>
        </div>
        <div class="member-actions flex gap-1">
          {#if m.role !== "president" && myRole === "president"}
            <button class="btn btn-ghost btn-xs" onclick={()=>promoteMember(m.user_id, m.role === "vice_president" ? "member" : "vice_president")} disabled={busyMemberId !== null}>
              {$translator(m.role === "vice_president" ? "guild.demote" : "guild.promote")}
            </button>
            <button class="btn btn-ghost btn-xs" style="color: var(--vercel-danger);" onclick={()=>confirmRemoval(m)} disabled={busyMemberId !== null}>{$translator("guild.remove")}</button>
          {:else if m.role === "member" && myRole === "vice_president"}
            <button class="btn btn-ghost btn-xs" style="color: var(--vercel-danger);" onclick={()=>confirmRemoval(m)} disabled={busyMemberId !== null}>{$translator("guild.remove")}</button>
          {/if}
        </div>
      </div>
    {/each}

  {:else}
    <div class="space-y-3">
      <div>
        <label for="manage-guild-name" class="block text-xs mb-1" style="color:var(--vercel-text-secondary);">{$translator("guild.name")}</label>
        <input id="manage-guild-name" class="input" bind:value={name} maxlength="80" />
      </div>
      <div>
        <label for="manage-guild-logo" class="block text-xs mb-1" style="color:var(--vercel-text-secondary);">{$translator("guild.logo")}</label>
        <input id="manage-guild-logo" class="input" bind:value={logo} maxlength="500" />
      </div>
      <div>
        <label for="manage-guild-description" class="block text-xs mb-1" style="color:var(--vercel-text-secondary);">{$translator("guild.description")}</label>
        <textarea id="manage-guild-description" class="input" rows="4" bind:value={description} maxlength="2000"></textarea>
      </div>
      <button class="btn btn-primary btn-sm" onclick={updateInfo} disabled={saving}>
        {$translator(saving ? "common.saving" : "common.save")}
      </button>
    </div>
  {/if}
{/if}

<ConfirmDialog
  bind:open={confirmOpen}
  title={$translator("guild.removeMemberTitle")}
  description={confirmDescription}
  confirmText={$translator("guild.remove")}
  onConfirm={confirmAction}
/>

<style>
  .manage-header {
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--vercel-border);
  }

  .manage-message {
    margin-bottom: 0.75rem;
    padding: 0.625rem 0.75rem;
    color: var(--vercel-success);
    background: var(--vercel-success-bg);
    border-left: 3px solid var(--vercel-success);
    font-size: 0.75rem;
  }

  .manage-message.is-error {
    color: var(--vercel-danger);
    background: var(--vercel-danger-bg);
    border-left-color: var(--vercel-danger);
  }

  @media (max-width: 40rem) {
    .request-card,
    .member-row {
      align-items: stretch;
      flex-direction: column;
      gap: 0.75rem;
    }

    .request-identity,
    .member-identity {
      min-width: 0;
      overflow-wrap: anywhere;
    }

    .request-actions,
    .member-actions {
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .manage-tabs {
      overflow-x: auto;
      scrollbar-width: none;
    }

    .manage-tabs::-webkit-scrollbar {
      display: none;
    }

    .manage-tabs :global(.filter-tab) {
      flex: 0 0 auto;
      white-space: nowrap;
    }
  }
</style>
