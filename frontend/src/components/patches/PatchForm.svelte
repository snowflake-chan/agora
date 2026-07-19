<script lang="ts">
  import { renderMarkdown } from "../../lib/markdown";
  import { createEventDispatcher } from "svelte";
  import { fly } from "svelte/transition";
  import { GITHUB_REPO } from "../../lib/config";
  import { createPatch } from "../../lib/patches";
  import { toaster } from "../../stores/toaster";
  import { appleEase } from "../../lib/motion";
  import { modal } from "../../lib/modal";

  const dispatch = createEventDispatcher();

  let title = "";
  let prNumber: number | null = null;
  let content = "";
  let submitting = false;
  let mobilePane: "edit" | "preview" = "edit";

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
  class="fixed inset-0 flex items-center justify-center p-4 dialog-backdrop composer-backdrop"
  onclick={handleBackdropClick}
>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    use:modal={{ onClose: close }}
    class="dialog-panel composer-dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="patch-composer-title"
    tabindex="-1"
    onclick={(e) => e.stopPropagation()}
    out:fly={{ y: 36, duration: 300, easing: appleEase }}
  >
    <!-- Header -->
    <div class="composer-header">
      <h2 id="patch-composer-title" class="sr-only">发起变更</h2>
      <div class="flex-1">
        <input
          data-autofocus
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

    <div class="composer-tabs" role="tablist" aria-label="编辑器视图">
      <button class:active={mobilePane === "edit"} onclick={() => mobilePane = "edit"} role="tab" aria-selected={mobilePane === "edit"}>编辑</button>
      <button class:active={mobilePane === "preview"} onclick={() => mobilePane = "preview"} role="tab" aria-selected={mobilePane === "preview"}>预览</button>
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
    <div class="composer-workspace">
      <!-- Left: editor -->
      <div class="composer-pane editor-pane" class:mobile-hidden={mobilePane !== "edit"}>
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
      <div class="composer-pane" class:mobile-hidden={mobilePane !== "preview"}>
        <div class="px-4 py-2 text-xs font-medium border-b" style="color: var(--vercel-text-tertiary); border-color: rgba(255,255,255,0.06);">
          预览
        </div>
        <div class="flex-1 overflow-y-auto px-6 py-4">
          {#if content.trim()}
            <div class="markdown-body">{@html renderMarkdown(content)}</div>
          {:else}
            <p class="text-sm" style="color: var(--vercel-text-tertiary);">暂无内容</p>
          {/if}
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .composer-dialog { display:flex; flex-direction:column; width:100%; height:min(54rem,calc(100dvh - 2rem)); max-width:87.5rem; overflow:hidden; border:1px solid rgba(255,255,255,.07); border-radius:.75rem; background:rgba(22,22,26,.96); box-shadow:0 8px 48px rgba(0,0,0,.5); backdrop-filter:blur(24px); }
  .composer-header { display:flex; align-items:center; gap:1rem; padding:.75rem 1.5rem; border-bottom:1px solid rgba(255,255,255,.06); }
  .composer-workspace { display:flex; flex:1; min-height:0; overflow:hidden; }
  .composer-pane { display:flex; flex:1; min-width:0; flex-direction:column; }
  .editor-pane { border-right:1px solid rgba(255,255,255,.06); }
  .composer-tabs { display:none; }
  @media (max-width: 48rem) {
    .composer-backdrop { padding:.5rem; }
    .composer-dialog { height:calc(100dvh - 1rem); border-radius:.875rem; }
    .composer-header { flex-wrap:wrap; gap:.5rem; padding:.75rem; }
    .composer-header > div { flex-basis:100%; order:-1; }
    .composer-tabs { display:grid; grid-template-columns:1fr 1fr; gap:.25rem; margin:.5rem .75rem 0; padding:.2rem; border-radius:.6rem; background:rgba(255,255,255,.05); }
    .composer-tabs button { padding:.45rem; border-radius:.45rem; color:var(--vercel-text-tertiary); font-size:.75rem; font-weight:600; }
    .composer-tabs button.active { color:var(--vercel-text); background:rgba(255,255,255,.09); }
    .editor-pane { border-right:0; }
    .composer-pane.mobile-hidden { display:none; }
  }
</style>
