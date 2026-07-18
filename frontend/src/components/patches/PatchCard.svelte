<script lang="ts">
  import type { Patch } from "../../lib/patches";
  import { stripMarkdown } from "../../lib/utils";
  import AuthorMeta from "../AuthorMeta.svelte";

  let { patch }: { patch: Patch } = $props();

  const STATUS_MAP: Record<string, { label: string; type: string }> = {
    draft: { label: "草稿", type: "neutral" },
    voting: { label: "投票中", type: "warning" },
    passed: { label: "通过待合并", type: "info" },
    merged: { label: "已合并", type: "success" },
    rejected: { label: "未通过", type: "danger" },
    failed: { label: "合并失败", type: "danger" },
  };

  let statusInfo = $derived(STATUS_MAP[patch.status] ?? { label: patch.status, type: "neutral" });
  let snippet = $derived(stripMarkdown(patch.content));
</script>

<a
  href={`/patches/${patch.id}`}
  class="block px-4 py-4 border-b transition-colors"
  style="border-color: var(--vercel-border);"
  on:mouseenter={(e) => e.currentTarget.style.background = '#141417'}
  on:mouseleave={(e) => e.currentTarget.style.background = ''}
>
  <div class="flex items-start gap-3">
    <div class="min-w-0 flex-1">
      <div class="flex items-center gap-2">
        <span class="badge badge-{statusInfo.type}">
          {statusInfo.label}
        </span>
        <span class="text-xs" style="color: var(--vercel-text-tertiary);">#{patch.pr_number}</span>
      </div>
      <h2 class="mt-1 text-base font-semibold" style="color: var(--vercel-text);">
        {patch.title}
      </h2>
      <p class="mt-1 line-clamp-2 text-sm" style="color: var(--vercel-text-secondary);">{snippet}</p>
    </div>
  </div>

  <div class="mt-2 flex items-center justify-between gap-2">
    <div class="flex items-center gap-3 text-xs" style="color: var(--vercel-text-tertiary);">
      {#if patch.status !== "draft"}
        <span>赞成 {patch.for_count} · 反对 {patch.against_count}</span>
      {/if}
    </div>
    <AuthorMeta username={patch.author_username ?? "匿名"} createdAt={patch.created_at} />
  </div>
</a>