<script lang="ts">
  import { onMount } from "svelte";
  import {
    listNotifications,
    markAllRead,
    markRead,
    type Notification,
  } from "../lib/notifications";
  import { timeAgo } from "../lib/utils";
  import { toaster } from "../stores/toaster";

  let items = $state<Notification[]>([]);
  let loading = $state(true);
  let unread = $state(0);

  let direct = $derived(items.filter((item) => !item.type.startsWith("following_")));
  let following = $derived(items.filter((item) => item.type.startsWith("following_")));

  onMount(async () => {
    try {
      const result = await listNotifications(1);
      items = result.items;
      unread = result.unread_count;
    } catch {
      toaster.error("无法加载通知");
    } finally {
      loading = false;
    }
  });

  async function openItem(item: Notification) {
    if (!item.is_read) await markRead(item.id);
    window.location.href = item.link;
  }

  async function readAll() {
    await markAllRead();
    items = items.map((item) => ({ ...item, is_read: true }));
    unread = 0;
  }
</script>

<header class="notification-header">
  <div>
    <p>Inbox</p>
    <h1>通知</h1>
    <span>{unread > 0 ? `${unread} 条未读` : "已全部读完"}</span>
  </div>
  {#if unread > 0}<button onclick={readAll}>全部标为已读</button>{/if}
</header>

{#if loading}
  <div class="empty-state"><div class="spinner"></div></div>
{:else}
  <div class="notification-grid">
    <section aria-labelledby="direct-title">
      <div class="section-heading">
        <div>
          <span>Primary</span>
          <h2 id="direct-title">与你相关</h2>
        </div>
        <strong>{direct.length}</strong>
      </div>
      <div class="notification-list">
        {#if direct.length === 0}
          <div class="notification-empty">暂时没有新的回复或治理结果。</div>
        {:else}
          {#each direct as item (item.id)}
            <button class:unread={!item.is_read} onclick={() => openItem(item)}>
              <span class="notification-dot"></span>
              <span class="notification-copy">
                <strong>{item.title}</strong>
                <span>{item.message}</span>
              </span>
              <time>{timeAgo(item.created_at)}</time>
            </button>
          {/each}
        {/if}
      </div>
    </section>

    <section class="following-section" aria-labelledby="following-title">
      <div class="section-heading">
        <div>
          <span>Secondary</span>
          <h2 id="following-title">关注动态</h2>
        </div>
        <strong>{following.length}</strong>
      </div>
      <p class="section-note">你关注的创作者发布新帖子或新变更时，会出现在这里。</p>
      <div class="notification-list secondary">
        {#if following.length === 0}
          <div class="notification-empty">关注一些创作者后，这里会出现他们的新内容。</div>
        {:else}
          {#each following as item (item.id)}
            <button class:unread={!item.is_read} onclick={() => openItem(item)}>
              <span class="notification-dot"></span>
              <span class="notification-copy">
                <strong>{item.title}</strong>
                <span>{item.message}</span>
              </span>
              <time>{timeAgo(item.created_at)}</time>
            </button>
          {/each}
        {/if}
      </div>
    </section>
  </div>
{/if}

<style>
  .notification-header {
    display: flex; align-items: end; justify-content: space-between; gap: 2rem;
    padding-bottom: 1.5rem; border-bottom: 1px solid var(--vercel-border);
  }
  .notification-header p, .section-heading span {
    color: var(--vercel-text-tertiary); font-size: .625rem; font-weight: 650;
    letter-spacing: .14em; text-transform: uppercase;
  }
  .notification-header h1 { font-size: 1.8rem; font-weight: 650; letter-spacing: -.04em; }
  .notification-header > div > span { color: var(--vercel-text-tertiary); font-size: .75rem; }
  .notification-header button {
    color: var(--vercel-text-secondary); font-size: .75rem;
  }
  .notification-grid {
    display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(18rem, .65fr);
    gap: 2rem; padding-top: 1.5rem;
  }
  .section-heading {
    display: flex; align-items: end; justify-content: space-between;
    margin-bottom: .75rem;
  }
  .section-heading h2 { margin-top: .15rem; font-size: 1rem; font-weight: 630; }
  .section-heading > strong {
    color: var(--vercel-text-tertiary); font-size: .75rem; font-variant-numeric: tabular-nums;
  }
  .section-note {
    margin: -.35rem 0 .85rem; color: var(--vercel-text-tertiary);
    font-size: .72rem; line-height: 1.5;
  }
  .notification-list { border-top: 1px solid var(--vercel-border); }
  .notification-list button {
    display: grid; width: 100%; grid-template-columns: .4rem minmax(0,1fr) auto;
    gap: .75rem; align-items: start; padding: 1rem .25rem;
    border-bottom: 1px solid var(--vercel-border); text-align: left;
    transition: background 150ms ease;
  }
  .notification-list button:hover { background: rgba(255,255,255,.025); }
  .notification-dot {
    width: .35rem; height: .35rem; margin-top: .35rem; border-radius: 999px;
    background: transparent;
  }
  .notification-list button.unread .notification-dot { background: var(--vercel-text); }
  .notification-copy { display: grid; gap: .2rem; min-width: 0; }
  .notification-copy strong { color: var(--vercel-text); font-size: .8rem; font-weight: 600; }
  .notification-copy > span { color: var(--vercel-text-secondary); font-size: .74rem; line-height: 1.45; }
  .notification-list time { color: var(--vercel-text-tertiary); font-size: .65rem; white-space: nowrap; }
  .notification-list.secondary { opacity: .78; }
  .notification-empty {
    padding: 2rem .25rem; border-bottom: 1px solid var(--vercel-border);
    color: var(--vercel-text-tertiary); font-size: .75rem; line-height: 1.55;
  }
  @media (max-width: 48rem) {
    .notification-grid { grid-template-columns: 1fr; }
    .notification-header { align-items: start; flex-direction: column; gap: .75rem; }
  }
</style>
