<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { Bell, Check, GitMerge, MessageSquare, ThumbsUp, X } from "@lucide/svelte";
  import { unreadCount, notifications, initNotificationStore, cleanupNotificationStore, openNotifications } from "../stores/notifications";
  import { currentUser, initAuth } from "../stores/auth";

  let open = false;
  let initialized = false;

  onMount(async () => {
    await initAuth();
    if ($currentUser) {
      initNotificationStore();
      initialized = true;
    }
  });
  onDestroy(() => {
    if (initialized) cleanupNotificationStore();
  });

  function toggle() {
    if (!open) {
      openNotifications();
    }
    open = !open;
  }

  function handleClickOutside(e: MouseEvent) {
    if (!(e.target as HTMLElement).closest(".notif-bell")) {
      open = false;
    }
  }

  function handleNotifClick(link: string) {
    open = false;
    window.location.href = link;
  }

  function timeAgo(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "刚刚";
    if (mins < 60) return `${mins}分钟前`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}小时前`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}天前`;
    return `${Math.floor(days / 30)}月前`;
  }

  function typeIcon(type: string) {
    if (type === "reply") return MessageSquare;
    if (type === "vote") return ThumbsUp;
    if (type === "vote_passed" || type === "patch_merged") return Check;
    if (type === "vote_rejected" || type === "patch_failed") return X;
    return Bell;
  }

  function isFollowing(type: string) {
    return type.startsWith("following_");
  }
</script>

<svelte:window on:click={handleClickOutside} />

{#if $currentUser}
  <div class="notif-bell relative">
    <button class="bell-btn" on:click={toggle} title="通知">
      <Bell class="size-4.5" />
      {#if $unreadCount > 0}
        <span class="bell-badge">
          {$unreadCount > 99 ? "99+" : $unreadCount}
        </span>
      {/if}
    </button>

    {#if open}
      <div class="notif-dropdown">
        {#if $notifications.length === 0}
          <div class="notif-empty">暂无通知</div>
        {:else}
          <div class="notif-section-label">与你相关</div>
          {#each $notifications.filter((item) => !isFollowing(item.type)).slice(0, 6) as notif (notif.id)}
            <button class="notif-item" on:click={() => handleNotifClick(notif.link)}>
              <div class="notif-icon">
                <svelte:component this={typeIcon(notif.type)} class="size-3.5" />
              </div>
              <div class="notif-body">
                <div class="notif-title">{notif.title}</div>
                <div class="notif-msg">{notif.message}</div>
                <div class="notif-time">{timeAgo(notif.created_at)}</div>
              </div>
            </button>
          {/each}
          {#if $notifications.some((item) => isFollowing(item.type))}
            <div class="notif-section-label secondary">关注动态</div>
            {#each $notifications.filter((item) => isFollowing(item.type)).slice(0, 4) as notif (notif.id)}
              <button class="notif-item secondary-item" on:click={() => handleNotifClick(notif.link)}>
                <div class="notif-icon">
                  <svelte:component this={typeIcon(notif.type)} class="size-3.5" />
                </div>
                <div class="notif-body">
                  <div class="notif-title">{notif.title}</div>
                  <div class="notif-msg">{notif.message}</div>
                  <div class="notif-time">{timeAgo(notif.created_at)}</div>
                </div>
              </button>
            {/each}
          {/if}
          <a class="notif-all" href="/notifications">查看全部通知</a>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .bell-btn {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.25rem;
    height: 2.25rem;
    border-radius: 6px;
    color: var(--vercel-text-secondary);
    background: transparent;
    border: none;
    cursor: pointer;
    transition: all 0.15s ease;
    font-family: inherit;
  }

  .bell-btn:hover {
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .bell-badge {
    position: absolute;
    top: 2px;
    right: 2px;
    min-width: 1rem;
    height: 1rem;
    padding: 0 3px;
    font-size: 0.625rem;
    font-weight: 700;
    line-height: 1rem;
    text-align: center;
    border-radius: 9999px;
    background: #ef4444;
    color: #fff;
    pointer-events: none;
  }

  .notif-dropdown {
    position: absolute;
    right: 0;
    top: calc(100% + 4px);
    width: 22rem;
    max-height: 24rem;
    overflow-y: auto;
    background: #1a1a1a;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius-lg);
    box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
    z-index: 60;
    animation: menuIn 0.15s ease;
  }

  @keyframes menuIn {
    from { opacity: 0; transform: translateY(-4px) scale(0.97); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }

  .notif-empty {
    padding: 2rem 1rem;
    text-align: center;
    font-size: 0.8125rem;
    color: var(--vercel-text-tertiary);
  }

  .notif-section-label {
    padding: .65rem .75rem .45rem;
    border-bottom: 1px solid var(--vercel-border);
    color: var(--vercel-text-secondary);
    font-size: .65rem;
    font-weight: 650;
    letter-spacing: .1em;
  }

  .notif-section-label.secondary {
    margin-top: .25rem;
    color: var(--vercel-text-tertiary);
  }

  .secondary-item {
    opacity: .78;
  }

  .notif-all {
    display: block;
    padding: .75rem;
    color: var(--vercel-text-secondary);
    font-size: .75rem;
    text-align: center;
  }

  .notif-item {
    display: flex;
    gap: 0.75rem;
    padding: 0.75rem;
    border: none;
    background: none;
    width: 100%;
    text-align: left;
    cursor: pointer;
    transition: background 0.1s ease;
    border-bottom: 1px solid var(--vercel-border);
    font-family: inherit;
  }

  .notif-item:last-child {
    border-bottom: none;
  }

  .notif-item:hover {
    background: var(--vercel-hover);
  }

  .notif-icon {
    flex-shrink: 0;
    width: 2rem;
    height: 2rem;
    border-radius: 9999px;
    background: rgba(255, 255, 255, 0.06);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--vercel-text-secondary);
  }

  .notif-body {
    flex: 1;
    min-width: 0;
  }

  .notif-title {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--vercel-text);
    margin-bottom: 0.125rem;
  }

  .notif-msg {
    font-size: 0.75rem;
    color: var(--vercel-text-secondary);
    line-height: 1.4;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .notif-time {
    font-size: 0.6875rem;
    color: var(--vercel-text-tertiary);
    margin-top: 0.25rem;
  }
</style>
