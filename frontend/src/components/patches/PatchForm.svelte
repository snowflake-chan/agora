<script lang="ts">
  import { marked } from "marked";
  import { createEventDispatcher } from "svelte";
  import { createPatch } from "../../lib/patches";
  import { toaster } from "../../stores/toaster";

  const dispatch = createEventDispatcher();

  let title = "";
  let prNumber: number | null = null;
  let content = "";
  let submitting = false;

  function close() {
    dispatch("close");
  }

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
      toaster.error("发起失败", e.message ?? "请稍后重试");
    } finally {
      submitting = false;
    }
  }

  function portal(node: HTMLElement) {
    document.body.appendChild(node);
    return { destroy() { node.remove(); } };
  }
</script>

<div use:portal class="fixed inset-0 z-50 flex h-dvh flex-col" style="background: var(--vercel-bg);">
  <!-- Top bar -->
  <div class="flex items-center gap-3 border-b px-6 py-3" style="border-color: var(--vercel-border);">
    <input
      bind:value={title}
      class="flex-1 bg-transparent px-0 text-xl font-bold placeholder:text-[#555] focus:outline-none"
      style="border: none; color: var(--vercel-text);"
      placeholder="标题"
    />
    <button class="btn btn-ghost btn-sm" on:click={close}>取消</button>
    <button
      class="btn btn-primary btn-sm"
      on:click={handleSubmit}
      disabled={submitting || !title.trim() || !content.trim() || !prNumber}
    >
      {submitting ? "提交中..." : "发起"}
    </button>
  </div>

  <!-- PR number input -->
  <div class="flex items-center gap-2 border-b px-6 py-2.5" style="border-color: var(--vercel-border);">
    <span class="text-sm" style="color: var(--vercel-text-tertiary);">https://github.com/</span>
    <input
      bind:value={prNumber}
      type="number"
      min="1"
      class="w-32 bg-transparent text-sm focus:outline-none"
      style="border: none; color: var(--vercel-text);"
      placeholder="PR 编号"
    />
  </div>

  <!-- Split pane -->
  <div class="flex flex-1 overflow-hidden">
    <textarea
      bind:value={content}
      class="w-1/2 resize-none border-r px-6 py-5 font-mono text-sm leading-relaxed placeholder:text-[#555] focus:outline-none"
      style="border-color: var(--vercel-border); background: transparent; color: var(--vercel-text);"
      placeholder="描述变更内容，支持 Markdown 语法"
    ></textarea>
    <div class="w-1/2 overflow-y-auto px-6 py-5">
      {#if content.trim()}
        <div class="markdown-body">{@html marked.parse(content, { breaks: true, gfm: true })}</div>
      {:else}
        <p class="text-sm" style="color: var(--vercel-text-tertiary);">预览</p>
      {/if}
    </div>
  </div>
</div>
