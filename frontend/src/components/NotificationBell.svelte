<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { Bell, Check, MessageSquare, ThumbsUp, X } from "@lucide/svelte";
  import { locale, localizeNotification, translator } from "../lib/i18n";
  import {
    cleanupNotificationStore,
    initNotificationStore,
    notifications,
    openNotifications,
    unreadCount,
  } from "../stores/notifications";
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
    if (!open) openNotifications();
    open = !open;
  }

  function handleClickOutside(event: MouseEvent) {
    if (!(event.target as HTMLElement).closest(".notif-bell")) open = false;
  }

  function handleNotifClick(link: string) {
    open = false;
    window.location.href = link;
  }

  function timeAgo(value: string): string {
    const elapsedSeconds = Math.round((new Date(value).getTime() - Date.now()) / 1000);
    const format = new Intl.RelativeTimeFormat($locale, { numeric: "auto" });
    if (Math.abs(elapsedSeconds) < 60) return format.format(elapsedSeconds, "second");
    const minutes = Math.round(elapsedSeconds / 60);
    if (Math.abs(minutes) < 60) return format.format(minutes, "minute");
    const hours = Math.round(minutes / 60);
    if (Math.abs(hours) < 24) return format.format(hours, "hour");
    const days = Math.round(hours / 24);
    if (Math.abs(days) < 30) return format.format(days, "day");
    return format.format(Math.round(days / 30), "month");
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

<svelte:window onclick={handleClickOutside} />

{#if $currentUser}
  <div class="notif-bell relative">
    <button class="bell-btn" onclick={toggle} title={$translator("notifications.title")} aria-label={$translator("notifications.title")} aria-expanded={open}>
      <Bell class="size-4.5" />
      {#if $unreadCount > 0}
        <span class="bell-badge">{$unreadCount > 99 ? "99+" : $unreadCount}</span>
      {/if}
    </button>

    {#if open}
      <div class="notif-dropdown">
        {#if $notifications.length === 0}
          <div class="notif-empty">{$translator("notifications.empty")}</div>
        {:else}
          <div class="notif-section-label">{$translator("notifications.related")}</div>
          {#each $notifications.filter((item) => !isFollowing(item.type)).slice(0, 6) as notif (notif.id)}
            {@const copy = localizeNotification(notif, $translator)}
            <button class="notif-item" onclick={() => handleNotifClick(notif.link)}>
              <div class="notif-icon">
                <svelte:component this={typeIcon(notif.type)} class="size-3.5" />
              </div>
              <div class="notif-body">
                <div class="notif-title">{copy.title}</div>
                <div class="notif-msg">{copy.message}</div>
                <div class="notif-time">{timeAgo(notif.created_at)}</div>
              </div>
            </button>
          {/each}
          {#if $notifications.some((item) => isFollowing(item.type))}
            <div class="notif-section-label secondary">{$translator("notifications.following")}</div>
            {#each $notifications.filter((item) => isFollowing(item.type)).slice(0, 4) as notif (notif.id)}
              {@const copy = localizeNotification(notif, $translator)}
              <button class="notif-item secondary-item" onclick={() => handleNotifClick(notif.link)}>
                <div class="notif-icon">
                  <svelte:component this={typeIcon(notif.type)} class="size-3.5" />
                </div>
                <div class="notif-body">
                  <div class="notif-title">{copy.title}</div>
                  <div class="notif-msg">{copy.message}</div>
                  <div class="notif-time">{timeAgo(notif.created_at)}</div>
                </div>
              </button>
            {/each}
          {/if}
          <a class="notif-all" href="/notifications">{$translator("notifications.all")}</a>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .bell-btn { position:relative; display:flex; width:2.25rem; height:2.25rem; align-items:center; justify-content:center; border:0; border-radius:var(--vercel-radius-sm); color:var(--vercel-text-secondary); background:transparent; cursor:pointer; transition:color .15s ease,background .15s ease; }
  .bell-btn:hover { color:var(--vercel-text); background:var(--vercel-hover); }
  .bell-badge { position:absolute; top:2px; right:2px; min-width:1rem; height:1rem; padding:0 3px; border-radius:9999px; color:#fff; background:var(--vercel-danger); font-size:.625rem; font-weight:700; line-height:1rem; text-align:center; pointer-events:none; }
  .notif-dropdown { position:absolute; z-index:60; top:calc(100% + 4px); right:0; width:min(22rem,calc(100vw - 1rem)); max-height:24rem; overflow-y:auto; border:1px solid var(--vercel-border); border-radius:var(--vercel-radius-lg); background:var(--vercel-card); box-shadow:0 8px 40px rgba(0,0,0,.32); animation:menuIn .15s ease; }
  @keyframes menuIn { from { opacity:0; transform:translateY(-4px) scale(.97); } to { opacity:1; transform:translateY(0) scale(1); } }
  .notif-empty { padding:2rem 1rem; color:var(--vercel-text-tertiary); font-size:.8125rem; text-align:center; }
  .notif-section-label { padding:.65rem .75rem .45rem; border-bottom:1px solid var(--vercel-border); color:var(--vercel-text-secondary); font-size:.65rem; font-weight:650; }
  .notif-section-label.secondary { margin-top:.25rem; color:var(--vercel-text-tertiary); }
  .secondary-item { opacity:.78; }
  .notif-all { display:block; padding:.75rem; color:var(--vercel-text-secondary); font-size:.75rem; text-align:center; }
  .notif-item { display:flex; width:100%; gap:.75rem; padding:.75rem; border:0; border-bottom:1px solid var(--vercel-border); color:inherit; background:none; text-align:left; cursor:pointer; transition:background .1s ease; }
  .notif-item:hover { background:var(--vercel-hover); }
  .notif-icon { display:flex; width:2rem; height:2rem; flex-shrink:0; align-items:center; justify-content:center; border-radius:var(--vercel-radius-sm); color:var(--vercel-text-secondary); background:var(--vercel-hover-strong); }
  .notif-body { min-width:0; flex:1; }
  .notif-title { margin-bottom:.125rem; color:var(--vercel-text); font-size:.8125rem; font-weight:600; }
  .notif-msg { overflow:hidden; color:var(--vercel-text-secondary); font-size:.75rem; line-height:1.4; text-overflow:ellipsis; white-space:nowrap; }
  .notif-time { margin-top:.25rem; color:var(--vercel-text-tertiary); font-size:.6875rem; }
</style>
