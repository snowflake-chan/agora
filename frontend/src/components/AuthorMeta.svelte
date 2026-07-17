<script lang="ts">
  export let username: string;
  export let createdAt: string;
  export let size: "sm" | "md" = "sm";

  function timeAgo(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "刚刚";
    if (mins < 60) return `${mins} 分钟前`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours} 小时前`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days} 天前`;
    return new Date(dateStr).toLocaleDateString("zh-CN");
  }

  const avatarSize = size === "md" ? "size-5" : "size-5";
  const fontSize = size === "md" ? "text-[9px]" : "text-[9px]";
  const textSize = size === "md" ? "text-xs" : "text-xs";
</script>

<div class="flex shrink-0 items-center gap-1.5 {textSize} text-surface-400">
  <div
    class="flex {avatarSize} items-center justify-center rounded-full bg-surface-100 {fontSize} font-semibold text-surface-500"
  >
    {(username ?? "?")[0].toUpperCase()}
  </div>
  <span class="text-surface-500">{username ?? "匿名"}</span>
  <span>·</span>
  <span>{timeAgo(createdAt)}</span>
</div>
