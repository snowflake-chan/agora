<script lang="ts">
  import { timeAgo } from "../lib/utils";

  let { username, createdAt }: { username: string; createdAt: string } = $props();
</script>

<div class="flex shrink-0 items-center gap-1.5 text-xs" style="color: var(--vercel-text-tertiary);">
  <div class="avatar avatar-sm">
    {(username ?? "?")[0].toUpperCase()}
  </div>
  <span style="color: var(--vercel-text-secondary);">{username ?? "匿名"}</span>
  <span>·</span>
  <span>{timeAgo(createdAt)}</span>
</div>