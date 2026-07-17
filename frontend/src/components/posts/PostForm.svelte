<script lang="ts">
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

<div class="flex gap-3">
  <div class="flex-1">
    <input
      bind:value={title}
      class="input mb-3 text-base font-semibold"
      placeholder="标题"
    />
    <textarea
      bind:value={content}
      class="input min-h-[120px] resize-y text-sm"
      placeholder="正文（支持 Markdown）"
    ></textarea>
    <div class="mt-3 flex justify-end gap-2">
      <a href="/" class="btn preset-tonal text-sm">取消</a>
      <button
        class="btn preset-filled-primary-500 text-sm"
        on:click={handleSubmit}
        disabled={submitting || !title.trim() || !content.trim()}
      >
        {submitting ? "发布中…" : "发布帖子"}
      </button>
    </div>
  </div>
</div>
