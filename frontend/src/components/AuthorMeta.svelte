<script lang="ts">
  import { timeAgo } from "../lib/utils";

  export let username: string;
  export let createdAt: string;
</script>

<div class="flex shrink-0 items-center gap-1.5 text-xs text-surface-400-600">
  <div
    class="flex size-5 items-center justify-center rounded-full bg-surface-100-900 text-[9px] font-semibold text-surface-500"
  >
    {(username ?? "?")[0].toUpperCase()}
  </div>
  <span class="text-surface-500">{username ?? "匿名"}</span>
  <span>·</span>
  <span>{timeAgo(createdAt)}</span>
</div>
