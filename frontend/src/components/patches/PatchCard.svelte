<script lang="ts">
  import type { Patch } from "../../lib/patches";
  import { stripMarkdown } from "../../lib/utils";
  import AuthorMeta from "../AuthorMeta.svelte";

  export let patch: Patch;

  const STATUS_MAP: Record<string, { label: string; cls: string }> = {
    draft: { label: "草稿", cls: "bg-surface-300 text-surface-700" },
    voting: { label: "投票中", cls: "bg-warning-500 text-white" },
    passed: { label: "通过待合并", cls: "bg-info-500 text-white" },
    merged: { label: "已合并", cls: "bg-success-500 text-white" },
    rejected: { label: "未通过", cls: "bg-error-500 text-white" },
    failed: { label: "合并失败", cls: "bg-error-500 text-white" },
  };

  $: statusInfo = STATUS_MAP[patch.status] ?? { label: patch.status, cls: "bg-surface-300 text-surface-700" };
  $: snippet = stripMarkdown(patch.content);
</script>

<a
  href={`/patches/${patch.id}`}
  class="group block border-b border-surface-200-800/50 px-4 py-4 transition-colors hover:bg-surface"
>
  <div class="flex items-start gap-3">
    <div class="min-w-0 flex-1">
      <div class="flex items-center gap-2">
        <span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium {statusInfo.cls}">
          {statusInfo.label}
        </span>
        <span class="text-xs text-surface-400">#{patch.pr_number}</span>
      </div>
      <h2 class="mt-1 text-base font-semibold text-surface-900-100 group-hover:text-primary-700">
        {patch.title}
      </h2>
      <p class="mt-1 line-clamp-2 text-sm text-surface-500">{snippet}</p>
    </div>
  </div>

  <div class="mt-2 flex items-center justify-between gap-2">
    <div class="flex items-center gap-3 text-xs text-surface-400-600">
      {#if patch.status !== "draft"}
        <span>赞成 {patch.for_count} · 反对 {patch.against_count}</span>
      {/if}
    </div>
    <AuthorMeta username={patch.author_username ?? "匿名"} createdAt={patch.created_at} />
  </div>
</a>
