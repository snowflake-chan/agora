<script lang="ts">
  import { timeAgo } from "../lib/utils";

  let { username, userId, createdAt }: { username: string; userId?: string; createdAt: string } = $props();

  let profileHref = $derived(userId ? `/users/${userId}` : "#");
</script>

<div class="relative z-10 flex shrink-0 items-center gap-1.5 text-xs" style="color: var(--vercel-text-tertiary);">
  <a href={profileHref} class="avatar avatar-sm no-underline hover:opacity-80 transition-opacity" style="cursor: {userId ? 'pointer' : 'default'};">
    {(username ?? "?")[0].toUpperCase()}
  </a>
  <a href={profileHref} class="no-underline hover:underline" style="color: var(--vercel-text-secondary); cursor: {userId ? 'pointer' : 'default'};">
    {username ?? "匿名"}
  </a>
  <span>·</span>
  <span>{timeAgo(createdAt)}</span>
</div>
