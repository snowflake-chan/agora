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
  import { initAuth, currentUser } from "../../stores/auth";
  import ConfirmDialog from "../ConfirmDialog.svelte";

  let { guildId }: { guildId: string } = $props();
  let guild = $state<Guild | null>(null);
  let members = $state<GuildMember[]>([]);
  let requests = $state<any[]>([]);
  let loading = $state(true);
  let error = $state("");
  let msg = $state("");
  let myRole = $state("");
  let tab = $state<"requests" | "members" | "info">("requests");
  let name = $state("");
  let logo = $state("");
  let description = $state("");
  let saving = $state(false);
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
        requests = await api(`/${guildId}/requests`).catch(() => []);
      }
    } catch (e: any) {
      error = translateError(e, $translator, "guild.loadFailed");
    }
    loading = false;
  });

  async function approve(reqId: string) {
    try { await api(`/${guildId}/requests/${reqId}/approve`, {method:"POST"}); requests = requests.filter(r => r.id !== reqId); msg = $translator("guild.requestApproved"); }
    catch(e:any) { msg = translateError(e, $translator, "common.operationFailed"); }
  }
  async function reject(reqId: string) {
    try { await api(`/${guildId}/requests/${reqId}/reject`, {method:"POST"}); requests = requests.filter(r => r.id !== reqId); msg = $translator("guild.requestRejected"); }
    catch(e:any) { msg = translateError(e, $translator, "common.operationFailed"); }
  }
  async function removeMember(uid: string) {
    try { await api(`/${guildId}/remove-member/${uid}`, {method:"POST"}); members = members.filter(m => m.user_id !== uid); msg = $translator("guild.memberRemoved"); }
    catch(e:any) { msg = translateError(e, $translator, "common.operationFailed"); }
  }
  async function promoteMember(uid: string, role: string) {
    try {
      await api(`/${guildId}/promote/${uid}?role=${role}`, {method:"POST"});
      members = members.map((member) =>
        member.user_id === uid ? { ...member, role } : member
      );
      msg = $translator("guild.roleUpdated");
    }
    catch(e:any) { msg = translateError(e, $translator, "common.operationFailed"); }
  }
  async function updateInfo() {
    if (!name.trim()) {
      msg = $translator("guild.nameRequired");
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
    } catch(e:any) {
      msg = translateError(e, $translator, "guild.updateFailed");
    } finally {
      saving = false;
    }
  }

  function roleLabel(role: string) {
    return $translator(`guild.role.${role}`);
  }

  function confirmRemoval(member: GuildMember) {
    confirmDescription = $translator("guild.removeMemberDescription", {
      name: member.nickname ?? member.username,
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
  {#if msg}<div class="mb-3 text-xs px-3 py-1 rounded" style="background: var(--vercel-success-bg);color: var(--vercel-success);">{msg}</div>{/if}

  <div class="flex gap-1 border-b mb-4" style="border-color: var(--vercel-border);">
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
        <div class="card p-3 mb-2 flex items-center justify-between">
          <div>
            <span class="font-medium" style="color: var(--vercel-text);">{r.nickname ?? r.username}</span>
            <span class="text-xs ml-2" style="color: var(--vercel-text-tertiary);">@{r.username}</span>
          </div>
          <div class="flex gap-1">
            <button class="btn btn-primary btn-xs" onclick={()=>approve(r.id)}>{$translator("guild.approve")}</button>
            <button class="btn btn-ghost btn-xs" style="color: var(--vercel-danger);" onclick={()=>reject(r.id)}>{$translator("guild.reject")}</button>
          </div>
        </div>
      {/each}
    {/if}

  {:else if tab === "members"}
    {#each members as m (m.id)}
      <div class="card p-3 mb-2 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <div class="avatar avatar-sm" style="width: 2rem; height: 2rem; font-size: 0.7rem; flex-shrink: 0;">{(m.nickname ?? m.username)[0].toUpperCase()}</div>
          <div>
            <span style="color: var(--vercel-text);">{m.nickname ?? m.username}</span>
            <span class="text-xs ml-1 px-1 py-0.5 rounded" style="background: var(--vercel-hover);color:var(--vercel-text-tertiary);">{roleLabel(m.role)}</span>
          </div>
        </div>
        <div class="flex gap-1">
          {#if m.role !== "president" && myRole === "president"}
            <button class="btn btn-ghost btn-xs" onclick={()=>promoteMember(m.user_id, m.role === "vice_president" ? "member" : "vice_president")}>
              {$translator(m.role === "vice_president" ? "guild.demote" : "guild.promote")}
            </button>
            <button class="btn btn-ghost btn-xs" style="color: var(--vercel-danger);" onclick={()=>confirmRemoval(m)}>{$translator("guild.remove")}</button>
          {:else if m.role === "member" && myRole === "vice_president"}
            <button class="btn btn-ghost btn-xs" style="color: var(--vercel-danger);" onclick={()=>confirmRemoval(m)}>{$translator("guild.remove")}</button>
          {/if}
        </div>
      </div>
    {/each}

  {:else}
    <div class="space-y-3">
      <div>
        <label class="block text-xs mb-1" style="color:var(--vercel-text-secondary);">{$translator("guild.name")}</label>
        <input class="input" bind:value={name} maxlength="80" />
      </div>
      <div>
        <label class="block text-xs mb-1" style="color:var(--vercel-text-secondary);">Logo</label>
        <input class="input" bind:value={logo} maxlength="500" />
      </div>
      <div>
        <label class="block text-xs mb-1" style="color:var(--vercel-text-secondary);">{$translator("guild.description")}</label>
        <textarea class="input" rows="4" bind:value={description} maxlength="2000"></textarea>
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
</style>
