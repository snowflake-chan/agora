<script lang="ts">
  import { marked } from "marked";
  import { createEventDispatcher } from "svelte";
  import { fly } from "svelte/transition";
  import { GITHUB_REPO } from "../../lib/config";
  import { createPatch } from "../../lib/patches";
  import { toaster } from "../../stores/toaster";
  import { appleEase } from "../../lib/motion";

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

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) close();
  }

  function portal(node: HTMLElement) {
    document.body.appendChild(node);
    return { destroy() { node.remove(); } };
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div use:portal
  class="fixed inset-0 z-50 flex items-center justify-center p-4 dialog-backdrop"
  onclick={handleBackdropClick}
>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="dialog-panel flex flex-col w-full h-[calc(100vh-1rem)] max-w-[1400px] rounded-xl overflow-hidden"
    style="
      background: rgba(22, 22, 26, 0.94);
      border: 1px solid rgba(255,255,255,0.07);
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
      box-shadow: 0 8px 48px rgba(0,0,0,0.5);
    "
    onclick={(e) => e.stopPropagation()}
    out:fly={{ y: 36, duration: 300, easing: appleEase }}
  >
    <!-- Header -->
    <div class="flex items-center gap-4 border-b px-6 py-3" style="border-color: rgba(255,255,255,0.06);">
      <div class="flex-1">
        <input
          bind:value={title}
          class="w-full px-4 py-2.5 text-lg font-semibold rounded-lg placeholder:text-[#555] focus:outline-none"
          style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); color: var(--vercel-text);"
          placeholder="标题"
        />
      </div>
      <button class="btn btn-ghost btn-sm" onclick={close}>取消</button>
      <button
        class="btn btn-primary btn-sm"
        onclick={handleSubmit}
        disabled={submitting || !title.trim() || !content.trim() || !prNumber}
      >
        {submitting ? "提交中..." : "发起"}
      </button>
    </div>

    <!-- PR number -->
    <div class="flex items-center gap-2 border-b px-6 py-2.5" style="border-color: rgba(255,255,255,0.06);">
      <span class="text-sm" style="color: var(--vercel-text-tertiary);">{GITHUB_REPO}#</span>
      <input
        bind:value={prNumber}
        type="number"
        min="1"
        class="w-32 text-sm placeholder:text-[#555] focus:outline-none"
        style="background: transparent; border: none; color: var(--vercel-text);"
        placeholder="PR 编号"
      />
    </div>

    <!-- Split pane: edit | preview -->
    <div class="flex flex-1 overflow-hidden">
      <!-- Left: editor -->
      <div class="flex-1 flex flex-col border-r" style="border-color: rgba(255,255,255,0.06);">
        <div class="px-4 py-2 text-xs font-medium border-b" style="color: var(--vercel-text-tertiary); border-color: rgba(255,255,255,0.06);">
          编辑
        </div>
        <textarea
          bind:value={content}
          class="flex-1 w-full resize-none px-6 py-4 font-mono text-sm leading-relaxed placeholder:text-[#555] focus:outline-none"
          style="background: transparent; color: var(--vercel-text);"
          placeholder="描述变更内容，支持 Markdown 语法"
        ></textarea>
      </div>

      <!-- Right: preview -->
      <div class="flex-1 flex flex-col">
        <div class="px-4 py-2 text-xs font-medium border-b" style="color: var(--vercel-text-tertiary); border-color: rgba(255,255,255,0.06);">
          预览
        </div>
        <div class="flex-1 overflow-y-auto px-6 py-4">
          {#if content.trim()}
            {#await marked.parse(content, { breaks: true, gfm: true }) then html}
              <div class="markdown-body">{@html html}</div>
            {/await}
          {:else}
            <p class="text-sm" style="color: var(--vercel-text-tertiary);">暂无内容</p>
          {/if}
        </div>
      </div>
    </div>
  </div>
</div>