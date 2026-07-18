<script lang="ts">
  import { marked } from "marked";
  import { createEventDispatcher } from "svelte";
  import { createPost } from "../../lib/posts";
  import { toaster } from "../../stores/toaster";

  const dispatch = createEventDispatcher();

  let title = "";
  let content = "";
  let submitting = false;

  function close() {
    dispatch("close");
  }

  async function handleSubmit() {
    if (!title.trim() || !content.trim()) return;
    submitting = true;
    try {
      const post = await createPost({ title: title.trim(), content: content.trim() });
      window.location.href = `/posts/${post.id}`;
    } catch (e: any) {
      toaster.error("发布失败", e.message ?? "请稍后重试");
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
      disabled={submitting || !title.trim() || !content.trim()}
    >
      {submitting ? "发布中..." : "发布"}
    </button>
  </div>

  <!-- Split pane -->
  <div class="flex flex-1 overflow-hidden">
    <textarea
      bind:value={content}
      class="w-1/2 resize-none border-r px-6 py-5 font-mono text-sm leading-relaxed placeholder:text-[#555] focus:outline-none"
      style="border-color: var(--vercel-border); background: transparent; color: var(--vercel-text);"
      placeholder="支持 Markdown 语法"
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
