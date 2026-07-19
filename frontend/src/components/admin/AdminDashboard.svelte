<script lang="ts">
  import { onMount } from "svelte";
  import { checkAdmin, listReports, resolveReport, listUsers, banUser, unbanUser, getBanStatus, setUserRole, type ReportItem, type AdminUser } from "../../lib/admin";
  import { listGuilds, listMembers, type Guild, type GuildMember } from "../../lib/guilds";
  import { initAuth } from "../../stores/auth";
  import GlassModal from "../GlassModal.svelte";

  const API = "/api/v1/admin";
  async function r(path: string, o?: RequestInit): Promise<any> {
    const res = await fetch(`${API}${path}`, { credentials: "include", ...o });
    if (!res.ok) throw new Error((await res.json().catch(()=>({detail:"error"}))).detail);
    return res.json();
  }

  let tab = $state<"reports" | "posts" | "patches" | "users" | "guilds">("reports");
  let isAdmin = $state(false); let loading = $state(true);
  let reports = $state<ReportItem[]>([]); let users = $state<AdminUser[]>([]);
  let guilds = $state<Guild[]>([]); let posts = $state<any[]>([]); let patches = $state<any[]>([]);
  let actionMsg = $state("");
  let expandGuild = $state<string | null>(null);
  let guildMembers = $state<GuildMember[]>([]); let guildDiscs = $state<any[]>([]);

  // Ban modal
  let banModal = $state(false); let banUid = $state(""); let banUname = $state("");
  let banType = $state("ban_user"); let banDays = $state(0); let banHours = $state(24); let banMins = $state(0);
  let banReason = $state("");
  let banFromReportId = $state(""); // track which report opened the ban modal

  // Unban modal
  let unbanModal = $state(false); let unbanUid = $state(""); let unbanUname = $state("");
  let unbanStatuses = $state<any[]>([]);


  onMount(async () => { await initAuth(); isAdmin = await checkAdmin(); if (!isAdmin) { loading = false; return; } await refresh(); loading = false; });
  async function refresh() { [reports, users, guilds, posts, patches] = await Promise.all([listReports().catch(()=>[]), listUsers().catch(()=>[]), listGuilds().catch(()=>[]), r("/posts").catch(()=>[]), r("/patches").catch(()=>[])]); }

  async function handleResolve(reportId: string, action: string) { try { await resolveReport(reportId, action); await refresh(); actionMsg = "已处理"; } catch(e:any) { actionMsg = e.message; } }

  function openBan(uid: string, uname: string) {
    banUid = uid; banUname = uname; banFromReportId = "";
    banType = "ban_user"; banDays = 0; banHours = 24; banMins = 0; banReason = "";
    banModal = true;
  }

  function openBanFromReport(r: ReportItem) {
    banUid = r.content_author_id; banUname = r.content_author; banFromReportId = r.id;
    banType = "mute_post"; banDays = 0; banHours = 24; banMins = 0;
    banReason = r.reason || "";
    banModal = true;
  }

  function totalBanHours() { return banDays * 24 + banHours + Math.floor(banMins / 60); }

  async function submitBan() {
    const h = totalBanHours();
    if (h <= 0) return;
    try {
      await banUser(banUid, h, banType, banReason);
      // If opened from report, resolve it too
      if (banFromReportId) {
        await resolveReport(banFromReportId, "resolved");
      }
      actionMsg = `已${banType === "ban_user" ? "封禁账号" : banType === "mute_post" ? "禁止发帖" : "禁止变更"} ${h}h`;
      banModal = false; await refresh();
    } catch(e: any) { actionMsg = e.message; }
  }

  async function openUnban(uid: string, uname: string) {
    unbanUid = uid; unbanUname = uname;
    try { unbanStatuses = await getBanStatus(uid); } catch { unbanStatuses = []; }
    unbanModal = true;
  }

  const TYPE_LABELS: Record<string, string> = { ban_user: "封禁账号", mute_post: "禁止发帖", mute_patch: "禁止变更" };

  async function doUnbanType(uid: string, t?: string) {
    await unbanUser(uid, t);
    actionMsg = t ? `已解除 ${TYPE_LABELS[t] || t}` : "已全部解封";
    unbanModal = false;
    await refresh();
  }
  // Confirm delete modal
  let delModal = $state(false); let delTitle = $state(""); let delAction = $state<(()=>void)|null>(null);

  function confirmDelete(title: string, action: () => void) {
    delTitle = title; delAction = action; delModal = true;
  }

  async function doDeletePost(pid: string) {
    try { await fetch(`${API}/posts/${pid}`,{method:"DELETE",credentials:"include"}); posts = posts.filter(p=>p.id!==pid); delModal = false; }
    catch(e:any) { actionMsg = e.message; delModal = false; }
  }

  async function doDeletePatch(pid: string) {
    try { await fetch(`${API}/patches/${pid}`,{method:"DELETE",credentials:"include"}); patches = patches.filter(p=>p.id!==pid); delModal = false; }
    catch(e:any) { actionMsg = e.message; delModal = false; }
  }

  async function doDeleteGuild(gid: string) {
    try { await fetch(`${API}/guilds/${gid}`,{method:"DELETE",credentials:"include"}); guilds = guilds.filter(g=>g.id!==gid); delModal = false; }
    catch(e:any) { actionMsg = e.message; delModal = false; }
  }

  // Guild management
  async function openGuildManage(gid: string) {
    expandGuild = expandGuild === gid ? null : gid;
    if (expandGuild) {
      [guildMembers, guildDiscs] = await Promise.all([
        listMembers(gid).catch(() => []),
        r(`/guilds/${gid}/discussions`).catch(() => []),
      ]);
    }
  }

  async function guildUpdate(gid: string, field: string, value: string) {
    try {
      const body: any = {}; body[field] = value || null;
      await fetch(`/api/v1/guilds/${gid}`, { method: "PATCH", headers: {"Content-Type":"application/json"}, body: JSON.stringify(body), credentials:"include" });
      actionMsg = "已更新";
    } catch(e: any) { actionMsg = e.message; }
  }

  async function guildRemoveMember(gid: string, uid: string) {
    try { await fetch(`${API}/guilds/${gid}/members/${uid}`,{method:"DELETE",credentials:"include"}); guildMembers = guildMembers.filter(m=>m.user_id!==uid); actionMsg="已移除"; }
    catch(e:any) { actionMsg = e.message; }
  }

  async function guildDeleteDisc(gid: string, did: string) {
    try { await fetch(`${API}/guilds/${gid}/discussions/${did}`,{method:"DELETE",credentials:"include"}); guildDiscs = guildDiscs.filter((d:any)=>d.id!==did); actionMsg="已删除"; }
    catch(e:any) { actionMsg = e.message; }
  }
</script>

{#if loading}<div class="empty-state"><div class="spinner mb-3"></div></div>
{:else if !isAdmin}<div class="card p-8 text-center"><h2 class="text-xl font-bold mb-2" style="color:var(--vercel-danger);">403 无权访问</h2></div>
{:else}
  <h1 class="text-xl font-bold mb-4" style="color:var(--vercel-text);">管理后台</h1>
  {#if actionMsg}<div class="mb-3 text-xs px-3 py-2 rounded" style="background:var(--vercel-success-bg);color:var(--vercel-success);">{actionMsg}</div>{/if}
  <div class="flex gap-1 border-b mb-4 flex-wrap" style="border-color:var(--vercel-border);">
    {#each [["reports","举报管理"],["posts","帖子管理"],["patches","变更管理"],["users","用户管理"],["guilds","社团管理"]] as [k,l]}<button class="filter-tab" class:active={tab===k} onclick={()=>tab=k as any}>{l}</button>{/each}
  </div>

  {#if tab === "reports"}
    {#if reports.length===0}<div class="empty-state"><p>暂无举报</p></div>
    {:else}
      {#each reports as r (r.id)}
        <div class="card p-4 mb-2" style="opacity:{r.status!=='pending'?'0.5':'1'};">
          <div class="text-xs" style="color:var(--vercel-text-tertiary);">举报人: {r.reporter_username} | 被举报: {r.content_author} | {r.created_at?.slice(0,10)||''} {#if r.status!=="pending"}<span class="ml-1 text-[10px] px-1 py-0.5 rounded" style="background:var(--vercel-success-bg);color:var(--vercel-success);">已处理</span>{/if}</div>
          <p class="mt-1 text-sm" style="color:var(--vercel-text-secondary);">{r.reason}</p>
          <div class="mt-1 text-xs mb-2" style="color:var(--vercel-text-tertiary);">{r.content_body?.slice(0,150)||''}</div>
          {#if r.status==="pending"}
            <div class="flex flex-wrap gap-1">
              <button class="btn btn-ghost btn-xs" style="color:var(--vercel-danger);" onclick={() => handleResolve(r.id, "delete_post")}>删除帖子</button>
              <button class="btn btn-ghost btn-xs" onclick={() => openBanFromReport(r)}>封禁</button>
            </div>
          {/if}
        </div>
      {/each}
    {/if}

  {:else if tab === "posts"}
    {#if posts.length===0}<div class="empty-state"><p>暂无帖子</p></div>{:else}{#each posts as p (p.id)}<div class="card p-3 mb-2 flex items-start justify-between gap-2"><div class="min-w-0"><div class="text-sm font-medium truncate" style="color:var(--vercel-text);">{p.title||"无标题"}</div><div class="text-xs" style="color:var(--vercel-text-tertiary);">{p.author_username} · {p.created_at?.slice(0,16)||''}</div></div><div class="flex-shrink-0 flex gap-1"><a href="/posts/{p.id}" target="_blank" class="btn btn-ghost btn-xs">查看</a><button class="btn btn-ghost btn-xs" style="color:var(--vercel-danger);" onclick={()=>confirmDelete("删除帖子「"+p.title+"」",()=>doDeletePost(p.id))}>删除</button></div></div>{/each}{/if}

  {:else if tab === "patches"}
    {#if patches.length===0}<div class="empty-state"><p>暂无变更</p></div>{:else}{#each patches as p (p.id)}<div class="card p-3 mb-2 flex items-start justify-between gap-2"><div class="min-w-0"><div class="text-sm font-medium truncate" style="color:var(--vercel-text);">{p.title||"无标题"}</div><div class="text-xs" style="color:var(--vercel-text-tertiary);">{p.author_username} · #{p.pr_number} · {p.status} · {p.created_at?.slice(0,16)||''}</div></div><div class="flex-shrink-0 flex gap-1"><a href="/patches/{p.id}" target="_blank" class="btn btn-ghost btn-xs">查看</a><button class="btn btn-ghost btn-xs" style="color:var(--vercel-danger);" onclick={()=>confirmDelete("删除变更「"+p.title+"」",()=>doDeletePatch(p.id))}>删除</button></div></div>{/each}{/if}

  {:else if tab === "users"}
    <div class="card overflow-hidden">
      {#each users as u (u.id)}
        <div class="flex items-center justify-between px-4 py-2 border-b" style="border-color:var(--vercel-border);">
          <div><span style="color:var(--vercel-text);">{u.username}</span><span class="text-xs ml-2" style="color:var(--vercel-text-tertiary);">{u.email}</span>{#if u.role!=="user"}<span class="text-[10px] ml-1 px-1.5 py-0.5 rounded-full" style="background:{u.role==='super_admin'?'rgba(239,68,68,0.15)':'rgba(59,130,246,0.15)'};color:{u.role==='super_admin'?'#f87171':'#60a5fa'};">{u.role==="super_admin"?"超管":"风纪委员"}</span>{/if}</div>
          <div class="flex gap-1 items-center">
            <select class="text-xs px-1 py-0.5 rounded" style="background:var(--vercel-surface);color:var(--vercel-text);border:1px solid var(--vercel-border);" onchange={async(e)=>{const v=(e.target as HTMLSelectElement).value;if(!v)return;try{await setUserRole(u.id,v);actionMsg="已设置";users=users.map(x=>x.id===u.id?{...x,role:v}:x)}catch(ex:any){actionMsg=ex.message}}}>
              <option value="">权限</option><option value="super_admin">超管</option><option value="moderator">风纪委员</option><option value="user">普通用户</option></select>
            <button class="btn btn-ghost btn-xs" onclick={()=>openBan(u.id,u.username)}>封禁</button>
            <button class="btn btn-ghost btn-xs" onclick={()=>openUnban(u.id, u.username)}>解封</button>
          </div>
        </div>
      {/each}
    </div>

  {:else if tab === "guilds"}
    {#each guilds as g (g.id)}
      <div class="card mb-2">
        <div class="p-4 flex items-center justify-between">
          <div><span class="font-semibold" style="color:var(--vercel-text);">{g.name}</span><span class="text-xs ml-2" style="color:var(--vercel-text-tertiary);">Lv.{g.level} | {g.member_count}人 | {g.president_username}</span></div>
          <div class="flex gap-1">
            <button class="btn btn-ghost btn-xs" onclick={() => openGuildManage(g.id)}>管理</button>
            <button class="btn btn-ghost btn-xs" style="color:var(--vercel-danger);" onclick={() => confirmDelete("删除社团「"+g.name+"」", ()=>doDeleteGuild(g.id))}>删除</button>
          </div>
        </div>
        {#if expandGuild === g.id}
          <div class="px-4 pb-4 space-y-3 border-t pt-3" style="border-color:var(--vercel-border);">
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <div><label class="text-[10px]" style="color:var(--vercel-text-tertiary);">名称</label><input class="input" style="font-size:0.8rem;padding:4px 8px;" value={g.name} onchange={(e) => guildUpdate(g.id,"name",(e.target as HTMLInputElement).value)} /></div>
              <div><label class="text-[10px]" style="color:var(--vercel-text-tertiary);">Logo</label><input class="input" style="font-size:0.8rem;padding:4px 8px;" value={g.logo||""} onchange={(e) => guildUpdate(g.id,"logo",(e.target as HTMLInputElement).value)} /></div>
              <div><label class="text-[10px]" style="color:var(--vercel-text-tertiary);">等级(1-5)</label><input class="input" type="number" min="1" max="5" style="font-size:0.8rem;padding:4px 8px;width:60px;" value={g.level} onchange={(e) => guildUpdate(g.id,"level",(e.target as HTMLInputElement).value)} /></div>
              <div><label class="text-[10px]" style="color:var(--vercel-text-tertiary);">简介</label><input class="input" style="font-size:0.8rem;padding:4px 8px;" value={g.description||""} onchange={(e) => guildUpdate(g.id,"description",(e.target as HTMLInputElement).value)} /></div>
            </div>
            <div><h4 class="text-xs font-bold mb-2" style="color:var(--vercel-text-secondary);">成员 ({guildMembers.length})</h4>
              {#each guildMembers as m (m.id)}
                <div class="flex items-center justify-between px-3 py-1.5 rounded mb-1" style="background:rgba(255,255,255,0.02);">
                  <span class="text-xs" style="color:var(--vercel-text);">{m.nickname ?? m.username} {m.role!=="member"?`(${m.role==="president"?"社长":"副社长"})`:""}</span>
                  {#if m.role !== "president"}<button class="btn btn-ghost btn-xs" style="color:var(--vercel-danger);" onclick={()=>guildRemoveMember(g.id,m.user_id)}>移除</button>{/if}
                </div>
              {/each}
            </div>
            <div><h4 class="text-xs font-bold mb-2" style="color:var(--vercel-text-secondary);">讨论组 ({guildDiscs.length})</h4>
              {#if guildDiscs.length===0}<p class="text-xs" style="color:var(--vercel-text-tertiary);">暂无</p>
              {:else}{#each guildDiscs as d (d.id)}
                <div class="flex items-center justify-between px-3 py-1.5 rounded mb-1" style="background:rgba(255,255,255,0.02);"><span class="text-xs" style="color:var(--vercel-text);">{d.title||"无标题"}</span><button class="btn btn-ghost btn-xs" style="color:var(--vercel-danger);" onclick={()=>guildDeleteDisc(g.id,d.id)}>删除</button></div>
              {/each}{/if}
            </div>
          </div>
        {/if}
      </div>
    {/each}
  {/if}

  <!-- Ban/mute Modal -->
  <GlassModal show={banModal} title="封禁/禁言 - {banUname}" onclose={()=>banModal=false}>
    <div class="space-y-3">
      <div>
        <label class="text-xs" style="color:var(--vercel-text-tertiary);">类型</label>
        <div class="flex flex-wrap gap-1 mt-1">
          {#each [{v:"ban_user",l:"封禁账号"},{v:"mute_post",l:"禁止发帖"},{v:"mute_patch",l:"禁止变更"}] as o}
            <button class="btn btn-xs" class:btn-primary={banType===o.v} onclick={()=>banType=o.v}>{o.l}</button>
          {/each}
        </div>
      </div>
      <div>
        <label class="text-xs" style="color:var(--vercel-text-tertiary);">时长</label>
        <div class="grid grid-cols-3 gap-2 mt-1">
          <div><label class="text-[10px]" style="color:var(--vercel-text-tertiary);">天</label><input type="number" class="input" min="0" style="padding:4px 6px;font-size:.8rem;width:100%;" bind:value={banDays} /></div>
          <div><label class="text-[10px]" style="color:var(--vercel-text-tertiary);">时</label><input type="number" class="input" min="0" max="23" style="padding:4px 6px;font-size:.8rem;width:100%;" bind:value={banHours} /></div>
          <div><label class="text-[10px]" style="color:var(--vercel-text-tertiary);">分</label><input type="number" class="input" min="0" max="59" style="padding:4px 6px;font-size:.8rem;width:100%;" bind:value={banMins} /></div>
        </div>
        <p class="text-[10px] mt-1" style="color:var(--vercel-text-tertiary);">总计 {totalBanHours()} 小时{banDays === 0 && banHours === 0 && banMins === 0 ? "（永久）" : ""}</p>
      </div>
      <textarea class="input" rows="2" style="width:100%;" bind:value={banReason} placeholder="封禁理由（选填）"></textarea>
      <div style="display:flex;justify-content:flex-end;gap:.5rem;">
        <button class="btn btn-ghost btn-sm" onclick={()=>banModal=false}>取消</button>
        <button class="btn btn-sm" style="background:var(--vercel-danger);border-color:var(--vercel-danger);color:#fff;" onclick={submitBan}>确认</button>
      </div>
    </div>
  </GlassModal>

  <!-- Unban Modal -->
  <GlassModal show={unbanModal} title="解封 - {unbanUname}" onclose={() => unbanModal = false}>
    {#if unbanStatuses.length === 0}
      <p class="text-sm" style="color: var(--vercel-success);">该用户当前没有被封禁或禁言</p>
    {:else}
      <div class="space-y-2 mb-4">
        {#each unbanStatuses as s (s.id)}
          <div class="flex items-center justify-between p-2 rounded" style="background: rgba(255,255,255,0.03); border: 1px solid var(--vercel-border);">
            <div>
              <span class="text-sm font-medium" style="color: var(--vercel-text);">{TYPE_LABELS[s.type] || s.type}</span>
              <span class="text-xs ml-2" style="color: var(--vercel-text-tertiary);">
                {#if s.expires_at}
                  至 {new Date(s.expires_at).toLocaleString('zh-CN')}
                {:else}
                  永久
                {/if}
              </span>
              {#if s.reason}
                <p class="text-xs mt-0.5" style="color: var(--vercel-text-tertiary);">理由: {s.reason}</p>
              {/if}
            </div>
            <button class="btn btn-ghost btn-xs" style="color: var(--vercel-success);" onclick={() => doUnbanType(unbanUid, s.type)}>解除</button>
          </div>
        {/each}
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span class="text-xs" style="color: var(--vercel-text-tertiary);">或</span>
        <button class="btn btn-sm" style="background: var(--vercel-success); border-color: var(--vercel-success); color: #fff;" onclick={() => doUnbanType(unbanUid)}>完全解封</button>
      </div>
    {/if}
    <div style="display:flex;justify-content:flex-end;margin-top:1rem;">
      <button class="btn btn-ghost btn-sm" onclick={() => unbanModal = false}>关闭</button>
    </div>
  </GlassModal>

  <!-- Confirm Delete Modal -->
  <GlassModal show={delModal} title="确认删除" onclose={() => delModal = false}>
    <p style="color: var(--vercel-text-secondary);">{delTitle}</p>
    <p class="mt-2 text-xs" style="color: var(--vercel-text-tertiary);">此操作不可撤销</p>
    <div style="display:flex;justify-content:flex-end;gap:.5rem;margin-top:1rem;">
      <button class="btn btn-ghost btn-sm" onclick={() => delModal = false}>取消</button>
      <button class="btn btn-sm" style="background:var(--vercel-danger);border-color:var(--vercel-danger);color:#fff;" onclick={() => delAction?.()}>确认删除</button>
    </div>
  </GlassModal>
{/if}
