<script lang="ts">
  import { onMount } from "svelte";
  import { getPost, listComments, createComment, type Post, type Comment } from "../../lib/posts";
  import { toaster } from "../../stores/toaster";
  import { currentUser } from "../../stores/auth";
  import TimelineItem from "./TimelineItem.svelte";

  export let postId: string;

  let post: Post | null = null;
  let comments: Comment[] = [];
  let loading = true;
  let replyText = "";
  let replyingTo: Comment | null = null;
  let submitting = false;

  onMount(async () => {
    try {
      const [p, c] = await Promise.all([getPost(postId), listComments(postId)]);
      post = p;
      comments = c;
    } catch {
      toaster.error({ title: "错误", description: "无法加载帖子" });
    } finally {
      loading = false;
    }
  });

  function cancelReply() {
    replyingTo = null;
    replyText = "";
  }

  function handleReplyClick(c: Comment) {
    replyingTo = c;
    replyText = "";
    setTimeout(() => {
      const ta = document.querySelector<HTMLTextAreaElement>("#reply-textarea");
      ta?.focus();
    }, 0);
  }

  async function handleSubmitReply() {
    if (!replyText.trim()) return;
    submitting = true;
    try {
      const newComment = await createComment(postId, {
        content: replyText.trim(),
        ...(replyingTo ? { replying_id: replyingTo.id } : {}),
      });
      comments = [...comments, newComment];
      replyText = "";
      replyingTo = null;
      if (post) post.reply_count++;
    } catch (e: any) {
      toaster.error({ title: "错误", description: e.message ?? "回复失败" });
    } finally {
      submitting = false;
    }
  }

  // Flatten post + comments into a single timeline
  let postTitle = "";
  let postTags: string[] | null = null;
  let items: Array<{
    key: string;
    username: string;
    createdAt: string;
    content: string;
    replyingToUsername: string | null;
  }> = [];

  $: if (post) {
    postTitle = post.title;
    postTags = post.tags;
    items = [
      {
        key: post.id,
        username: post.author_username ?? "匿名",
        createdAt: post.created_at,
        content: post.content,
        replyingToUsername: null,
      },
      ...comments.map((c) => ({
        key: c.id,
        username: c.author_username ?? "匿名",
        createdAt: c.created_at,
        content: c.content,
        replyingToUsername: c.replying_to_username,
      })),
    ];
  }
</script>

{#if loading}
  <div class="flex justify-center py-12 text-sm text-surface-400">加载中…</div>
{:else if !post}
  <div class="flex justify-center py-12 text-sm text-surface-500">帖子不存在</div>
{:else}
  <!-- Title outside timeline, aligned with cards -->
  <div class="mb-6 ml-7">
    <h1 class="text-xl font-bold text-surface-900">{postTitle}</h1>
    {#if postTags && postTags.length > 0}
      <div class="mt-2 flex flex-wrap gap-2">
        {#each postTags as tag}
          <span class="rounded-full bg-surface-100 px-2.5 py-0.5 text-xs text-surface-600">{tag}</span>
        {/each}
      </div>
    {/if}
  </div>

  <div class="relative">
    <!-- Continuous timeline line behind all cards -->
    <div class="absolute left-[36px] inset-y-0 w-0.5 bg-surface-100"></div>

    <div>
      {#each items as item, i (item.key)}
        <TimelineItem
          username={item.username}
          createdAt={item.createdAt}
          content={item.content}
          replyingToUsername={item.replyingToUsername}
          onReply={$currentUser && i > 0 ? () => handleReplyClick(comments[i - 1]) : null}
        />
      {/each}
    </div>
  </div>

  <!-- Reply form -->
  {#if $currentUser}
    <div class="mt-4 border-t border-surface-200/50 pt-4">
      {#if replyingTo}
        <div class="mb-2 flex items-center gap-2 text-xs text-surface-500">
          <span>回复 <span class="font-medium text-primary-600">@{replyingTo.author_username}</span></span>
          <button class="text-surface-400 hover:text-surface-600" on:click={cancelReply}>取消</button>
        </div>
      {/if}
      <div class="flex gap-3">
        <div
          class="mt-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-surface-200 text-[10px] font-bold text-surface-600"
        >
          {($currentUser.username ?? "?")[0].toUpperCase()}
        </div>
        <div class="flex-1">
          <textarea
            id="reply-textarea"
            bind:value={replyText}
            class="input min-h-[80px] resize-y text-sm"
            placeholder="写下你的回复…"
          ></textarea>
          <div class="mt-2 flex justify-end">
            <button
              class="btn preset-filled-primary-500 text-sm"
              on:click={handleSubmitReply}
              disabled={submitting || !replyText.trim()}
            >
              {submitting ? "发送中…" : "回复"}
            </button>
          </div>
        </div>
      </div>
    </div>
  {:else}
    <div class="mt-4 border-t border-surface-200/50 pt-4 text-center">
      <a href="/login" class="text-sm text-primary-600 hover:text-primary-700">登录后参与回复</a>
    </div>
  {/if}
{/if}
