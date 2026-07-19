<script lang="ts">
  import { onMount } from "svelte";
  import {
    getGuild, joinGuild, leaveGuild,
    listMembers, listGuildPatches, listDiscussions, createDiscussion, deleteDiscussion,
    type Guild, type GuildMember, type GuildDiscussion,
  } from "../../lib/guilds";
  import type { Patch } from "../../lib/patches";
  import { currentUser, initAuth } from "../../stores/auth";
  import { timeAgo } from "../../lib/utils";
  import GuildMemberCard from "./GuildMemberCard.svelte";

  let { guildId }: { guildId: string } = $props();

  let guild = $state<Guild | null>(null);
  let members = $state<GuildMember[]>([]);
  let patches = $state<Patch[]>([]);
  let discussions = $state<GuildDiscussion[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let joining = $state(false);
  let leaving = $state(false);
  let tab = $state<"patches" | "members" | "discussions">("patches");

  let discussionTitle = $state("");
  let discussionContent = $state("");
  let discussionSending = $state(false);
  let myMembership = $state<GuildMember | null>(null);

  const LEVEL_LABELS = ["", "heiker", "black客", "黑色的客人", "黑客", "Natriumchlorid"];
  const LEVEL_COLORS = ["", "#cd7f32", "#c0c0c0", "#ffd700", "#b9f2ff", "#ff4500"];

  onMount(async () => {
    await initAuth();
    await loadAll();
  });

  async function loadAll() {
    loading = true;
    try {
      const [g, m] = await Promise.all([getGuild(guildId), listMembers(guildId)]);
      guild = g;
      members = m;
      if ($currentUser) {
        myMembership = m.find((x) => x.user_id === $currentUser!.id) || null;
      }
      const p = await listGuildPatches(guildId).catch(() => []);
      patches = p;
      if (myMembership) {
        const d = await listDiscussions(guildId).catch(() => []);
        discussions = d;
      }
    } catch (e: any) {
      error = e.message || "加载失败";
    } finally {
      loading = false;
    }
  }

  async function handleJoin() {
    joining = true;
    try { await joinGuild(guildId); await loadAll(); } catch (e: any) { error = e.message; }
    finally { joining = false; }
  }

  async function handleLeave() {
    leaving = true;
    try { await leaveGuild(guildId); await loadAll(); } catch (e: any) { error = e.message; }
    finally { leaving = false; }
  }

  async function handlePostDiscussion() {
    if (!discussionContent.trim()) return;
    discussionSending = true;
    try {
      await createDiscussion(guildId, { title: discussionTitle.trim() || null, content: discussionContent.trim() });
      discussionTitle = "";
      discussionContent = "";
      discussions = await listDiscussions(guildId);
    } catch (e: any) { error = e.message; }
    finally { discussionSending = false; }
  }

  async function handleDeletePost(postId: string) {
    try {
      await deleteDiscussion(guildId, postId);
      discussions = discussions.filter((d) => d.id !== postId);
    } catch (e: any) { error = e.message; }
  }
</script>

{#if loading}
  <div class="empty-state"><div class="spinner mb-3"></div>加载中...</div>
{:else if error}
  <div class="empty-state"><p style="color: var(--vercel-danger);">{error}</p></div>
{:else if guild}
  <!-- Header -->
  <div class="card p-6 mb-6 text-center">
    <div class="w-20 h-20 mx-auto rounded-2xl flex items-center justify-center text-3xl mb-4" style="background: linear-gradient(135deg, var(--vercel-surface-highlight), var(--vercel-surface)); border: 2px solid {LEVEL_COLORS[guild.level] || 'var(--vercel-border)'};">
      {guild.logo || guild.name[0].toUpperCase()}
    </div>
    <div class="inline-flex items-center gap-2 mb-1">
      <h1 class="text-2xl font-bold" style="color: var(--vercel-text);">{guild.name}</h1>
      <span class="text-xs font-bold px-2 py-0.5 rounded-full" style="background: {(LEVEL_COLORS[guild.level] || '#888')}22; color: {LEVEL_COLORS[guild.level] || '#888'}; border: 1px solid {(LEVEL_COLORS[guild.level] || '#888')}44;">
        Lv.{guild.level} {LEVEL_LABELS[guild.level] || ''}
      </span>
    </div>
    {#if guild.description}
      <p class="text-sm mt-2 max-w-md mx-auto" style="color: var(--vercel-text-secondary);">{guild.description}</p>
    {/if}
    <div class="flex items-center justify-center gap-3 mt-3 text-xs" style="color: var(--vercel-text-tertiary);">
      <span>{guild.member_count} 成员</span>
      <span>·</span>
      <span>社长 {guild.president_username}</span>
    </div>

    {#if $currentUser}
      <div class="mt-4">
        {#if myMembership}
          <div class="flex items-center justify-center gap-2">
            <span class="text-xs px-2 py-0.5 rounded-full" style="background: var(--vercel-success-bg); color: var(--vercel-success);">
              已加入 · {myMembership.role === "president" ? "社长" : myMembership.role === "vice_president" ? "副社长" : "成员"}
            </span>
            {#if myMembership.role !== "president"}
              <button class="btn btn-ghost btn-xs" onclick={handleLeave} disabled={leaving}>退出社团</button>
            {/if}
            {#if myMembership.role === "president" || myMembership.role === "vice_president"}
              <a href="/guilds/{guildId}/manage" class="btn btn-ghost btn-xs no-underline">管理中心</a>
            {/if}
          </div>
        {:else}
          <button class="btn btn-primary btn-sm" onclick={handleJoin} disabled={joining}>加入社团</button>
        {/if}
      </div>
    {/if}
  </div>

  <!-- Tabs -->
  <div class="flex gap-1 border-b mb-4" style="border-color: var(--vercel-border);">
    <button class="filter-tab" class:active={tab === "patches"} onclick={() => tab = "patches"}>社团变更</button>
    <button class="filter-tab" class:active={tab === "members"} onclick={() => tab = "members"}>成员</button>
    <button class="filter-tab" class:active={tab === "discussions"} onclick={() => tab = "discussions"}>讨论组</button>
  </div>

  {#if tab === "patches"}
    {#if patches.length === 0}
      <div class="empty-state"><p>暂无社团变更</p></div>
    {:else}
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {#each patches as p (p.id)}
          <a href="/patches/{p.id}" class="card p-4 block no-underline transition-colors" style="border: 1px solid var(--vercel-border);" onmouseenter={(e) => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)'} onmouseleave={(e) => e.currentTarget.style.borderColor = ''}>
            <h3 class="font-semibold text-sm" style="color: var(--vercel-text);">{p.title}</h3>
            <div class="flex items-center gap-2 mt-2 text-xs" style="color: var(--vercel-text-tertiary);">
              <span>赞成 {p.for_count} · 反对 {p.against_count}</span>
              <span>·</span>
              <span>{timeAgo(p.created_at)}</span>
            </div>
          </a>
        {/each}
      </div>
    {/if}

  {:else if tab === "members"}
    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
      {#each members as m (m.id)}
        <GuildMemberCard member={m} />
      {/each}
    </div>

  {:else}
    <!-- Discussions -->
    {#if !myMembership}
      <div class="card p-8 text-center">
        <p style="color: var(--vercel-text-tertiary);">🔒 非本社团成员无法查看讨论组</p>
        {#if $currentUser}
          <button class="btn btn-primary btn-sm mt-3" onclick={handleJoin} disabled={joining}>加入社团</button>
        {/if}
      </div>
    {:else}
      <!-- Post form -->
      <div class="card p-4 mb-4">
        <input class="input mb-2" type="text" bind:value={discussionTitle} placeholder="标题（选填）" />
        <textarea class="input mb-2" rows="2" bind:value={discussionContent} placeholder="说点什么..."></textarea>
        <div class="flex justify-end">
          <button class="btn btn-primary btn-sm" onclick={handlePostDiscussion} disabled={discussionSending || !discussionContent.trim()}>{discussionSending ? "发送中..." : "发布"}</button>
        </div>
      </div>

      {#if discussions.length === 0}
        <div class="empty-state"><p>还没有讨论，来发起第一个吧</p></div>
      {:else}
        {#each discussions as d (d.id)}
          <div class="card p-4 mb-2">
            <div class="flex items-center justify-between mb-1">
              <div class="flex items-center gap-2 text-xs" style="color: var(--vercel-text-tertiary);">
                <a href="/users/{d.author_id}" class="font-medium no-underline" style="color: var(--vercel-text-secondary);">{d.author_username}</a>
                <span>·</span>
                <span>{timeAgo(d.created_at)}</span>
              </div>
              {#if $currentUser?.id === d.author_id}
                <button class="text-xs" style="color: var(--vercel-text-tertiary); background: none; border: none; cursor: pointer;" onclick={() => handleDeletePost(d.id)}>删除</button>
              {/if}
            </div>
            {#if d.title}
              <h4 class="font-semibold text-sm mb-1" style="color: var(--vercel-text);">{d.title}</h4>
            {/if}
            <p class="text-sm" style="color: var(--vercel-text-secondary);">{d.content}</p>
          </div>
        {/each}
      {/if}
    {/if}
  {/if}
{/if}
