<script lang="ts">
  import { marked } from "marked";
  import { createPatch } from "../../lib/patches";
  import { toaster } from "../../stores/toaster";

  let title = "";
  let prNumber: number | null = null;
  let content = "";
  let submitting = false;

  async function handleSubmit() {
    if (!title.trim() || !content.trim() || !prNumber) return;
    submitting = true;
    try {
      const patch = await createPatch({
        title: title.trim(),
        content: content.trim(),
        pr_number: prNumber,
      });
      window.location.href = `/patches/${patch.id}`;
    } catch (e: any) {
      toaster.error({ title: "发起失败", description: e.message ?? "请稍后重试" });
    } finally {
      submitting = false;
    }
  }
</script>

<div class="flex h-dvh flex-col bg-surface">
  <!-- Top bar -->
  <div class="flex items-center gap-3 border-b border-surface-200 px-6 py-3">
    <input
      bind:value={title}
      class="input flex-1 border-0 bg-transparent px-0 text-xl font-bold placeholder:text-surface-300 focus:ring-0"
      placeholder="标题"
    />
    <a href="/patches" class="btn preset-tonal text-sm">取消</a>
    <button
      class="btn preset-filled-primary-500 text-sm"
      on:click={handleSubmit}
      disabled={submitting || !title.trim() || !content.trim() || !prNumber}
    >
      {submitting ? "提交中…" : "发起"}
    </button>
  </div>

  <!-- PR number input -->
  <div class="flex items-center gap-2 border-b border-surface-200 px-6 py-3">
    <span class="text-sm text-surface-500">https://github.com/</span>
    <input
      bind:value={prNumber}
      type="number"
      min="1"
      class="input w-32 border-0 bg-transparent px-0 text-sm focus:ring-0"
      placeholder="PR 编号"
    />
  </div>

  <!-- Split pane -->
  <div class="flex flex-1 overflow-hidden">
    <!-- Editor -->
    <textarea
      bind:value={content}
      class="w-1/2 resize-none border-0 border-r border-surface-200 bg-surface px-6 py-5 font-mono text-sm leading-relaxed placeholder:text-surface-300 focus:ring-0"
      placeholder="描述变更内容，支持 Markdown 语法"
    ></textarea>

    <!-- Preview -->
    <div class="w-1/2 overflow-y-auto px-6 py-5">
      {#if content.trim()}
        {#await marked.parse(content, { breaks: true, gfm: true }) then html}
          <div class="markdown-body">{@html html}</div>
        {/await}
      {:else}
        <p class="text-sm text-surface-300">预览</p>
      {/if}
    </div>
  </div>
</div>
