<script lang="ts">
  import { onMount } from "svelte";
  import { getGuild, listMembers, type Guild, type GuildMember } from "../../lib/guilds";
  import { initAuth, currentUser } from "../../stores/auth";

  let { guildId }: { guildId: string } = $props();
  let guild = $state<Guild | null>(null);
  let members = $state<GuildMember[]>([]);
  let requests = $state<any[]>([]);
  let loading = $state(true);
  let error = $state("");
  let msg = $state("");
  let myRole = $state("");
  let tab = $state<"requests" | "members" | "info">("requests");

  const API = "/api/v1/guilds";

  async function api(path: string, options?: RequestInit) {
    const res = await fetch(`${API}${path}`, { credentials: "include", ...options });
    if (!res.ok) { const e = await res.json().catch(()=>({detail:"error"})); throw new Error(e.detail); }
    return res.json();
  }

  onMount(async () => {
    await initAuth();
    if (!$currentUser) { error = "请先登录"; loading = false; return; }
    try {
      [guild, members] = await Promise.all([getGuild(guildId), listMembers(guildId)]);
      const me = members.find(m => m.user_id === $currentUser?.id);
      myRole = me?.role || "";
      if (myRole === "president" || myRole === "vice_president") {
        requests = await api(`/${guildId}/requests`).catch(() => []);
      }
    } catch (e: any) { error = e.message; }
    loading = false;
  });

  async function approve(reqId: string) {
    try { await api(`/${guildId}/requests/${reqId}/approve`, {method:"POST"}); requests = requests.filter(r => r.id !== reqId); msg = "已通过"; }
    catch(e:any) { msg = e.message; }
  }
  async function reject(reqId: string) {
    try { await api(`/${guildId}/requests/${reqId}/reject`, {method:"POST"}); requests = requests.filter(r => r.id !== reqId); msg = "已拒绝"; }
    catch(e:any) { msg = e.message; }
  }
  async function removeMember(uid: string) {
    try { await api(`/${guildId}/remove-member/${uid}`, {method:"POST"}); members = members.filter(m => m.user_id !== uid); msg = "已移除"; }
    catch(e:any) { msg = e.message; }
  }
  async function promoteMember(uid: string, role: string) {
    try { await api(`/${guildId}/promote/${uid}?role=${role}`, {method:"POST"}); msg = "已操作"; }
    catch(e:any) { msg = e.message; }
  }
  async function updateInfo() {
    const name = (document.getElementById("gname") as HTMLInputElement)?.value;
    const logo = (document.getElementById("glogo") as HTMLInputElement)?.value;
    const desc = (document.getElementById("gdesc") as HTMLTextAreaElement)?.value;
    try {
      await fetch(`${API}/${guildId}`, {method:"PATCH", headers:{"Content-Type":"application/json"}, body: JSON.stringify({
        name: name || undefined, logo: logo || null, description: desc || null,
      }), credentials: "include"});
      msg = "已更新";
    } catch(e:any) { msg = e.message; }
  }
</script>

{#if loading}
  <div class="empty-state"><div class="spinner mb-3"></div></div>
{:else if error}
  <div class="empty-state"><p style="color: var(--vercel-danger);">{error}</p></div>
{:else if myRole !== "president" && myRole !== "vice_president"}
  <div class="card p-8 text-center"><p style="color: var(--vercel-danger);">无权访问</p></div>
{:else}
  <h1 class="text-xl font-bold mb-4" style="color: var(--vercel-text);">{guild?.name} · 管理中心</h1>
  {#if msg}<div class="mb-3 text-xs px-3 py-1 rounded" style="background: var(--vercel-success-bg);color: var(--vercel-success);">{msg}</div>{/if}

  <div class="flex gap-1 border-b mb-4" style="border-color: var(--vercel-border);">
    <button class="filter-tab" class:active={tab === "requests"} onclick={()=>tab="requests"}>入社申请 ({requests.length})</button>
    <button class="filter-tab" class:active={tab === "members"} onclick={()=>tab="members"}>成员管理 ({members.length})</button>
    {#if myRole === "president"}
      <button class="filter-tab" class:active={tab === "info"} onclick={()=>tab="info"}>修改信息</button>
    {/if}
  </div>

  {#if tab === "requests"}
    {#if requests.length === 0}
      <div class="empty-state"><p>暂无申请</p></div>
    {:else}
      {#each requests as r (r.id)}
        <div class="card p-3 mb-2 flex items-center justify-between">
          <div>
            <span class="font-medium" style="color: var(--vercel-text);">{r.nickname ?? r.username}</span>
            <span class="text-xs ml-2" style="color: var(--vercel-text-tertiary);">@{r.username}</span>
          </div>
          <div class="flex gap-1">
            <button class="btn btn-primary btn-xs" onclick={()=>approve(r.id)}>通过</button>
            <button class="btn btn-ghost btn-xs" style="color: var(--vercel-danger);" onclick={()=>reject(r.id)}>拒绝</button>
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
            <span class="text-xs ml-1 px-1 py-0.5 rounded" style="background: var(--vercel-surface-highlight);color:var(--vercel-text-tertiary);">{m.role === "president" ? "社长" : m.role === "vice_president" ? "副社长" : "成员"}</span>
          </div>
        </div>
        <div class="flex gap-1">
          {#if m.role !== "president" && myRole === "president"}
            <button class="btn btn-ghost btn-xs" onclick={()=>promoteMember(m.user_id, m.role === "vice_president" ? "member" : "vice_president")}>{m.role === "vice_president" ? "降级" : "升副社"}</button>
            <button class="btn btn-ghost btn-xs" style="color: var(--vercel-danger);" onclick={()=>removeMember(m.user_id)}>移除</button>
          {:else if m.role !== "president" && myRole === "vice_president"}
            <button class="btn btn-ghost btn-xs" style="color: var(--vercel-danger);" onclick={()=>removeMember(m.user_id)}>移除</button>
          {/if}
        </div>
      </div>
    {/each}

  {:else}
    <div class="space-y-3">
      <div>
        <label class="block text-xs mb-1" style="color:var(--vercel-text-secondary);">名称</label>
        <input id="gname" class="input" value={guild?.name || ""} />
      </div>
      <div>
        <label class="block text-xs mb-1" style="color:var(--vercel-text-secondary);">Logo</label>
        <input id="glogo" class="input" value={guild?.logo || ""} />
      </div>
      <div>
        <label class="block text-xs mb-1" style="color:var(--vercel-text-secondary);">简介</label>
        <textarea id="gdesc" class="input" rows="3">{guild?.description || ""}</textarea>
      </div>
      <button class="btn btn-primary btn-sm" onclick={updateInfo}>保存</button>
    </div>
  {/if}
{/if}
