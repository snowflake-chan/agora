<script lang="ts">
  import { marked } from "marked";
  import { createPost } from "../../lib/posts";
  import { toaster } from "../../stores/toaster";

  let title = "";
  let content = "";
  let submitting = false;

  async function handleSubmit() {
    if (!title.trim() || !content.trim()) return;
    submitting = true;
    try {
      const post = await createPost({ title: title.trim(), content: content.trim() });
      window.location.href = `/posts/${post.id}`;
    } catch (e: any) {
      toaster.error({ title: "发布失败", description: e.message ?? "请稍后重试" });
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
    <a href="/" class="btn preset-tonal text-sm">取消</a>
    <button
      class="btn preset-filled-primary-500 text-sm"
      on:click={handleSubmit}
      disabled={submitting || !title.trim() || !content.trim()}
    >
      {submitting ? "发布中…" : "发布"}
    </button>
  </div>

  <!-- Split pane -->
  <div class="flex flex-1 overflow-hidden">
    <!-- Editor -->
    <textarea
      bind:value={content}
      class="w-1/2 resize-none border-0 border-r border-surface-200 bg-surface px-6 py-5 font-mono text-sm leading-relaxed placeholder:text-surface-300 focus:ring-0"
      placeholder="支持 Markdown 语法"
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
