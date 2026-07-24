<script lang="ts">
  import { onMount } from "svelte";
  import { MessageCircleIcon, EyeOffIcon, SendIcon, CheckIcon, ReplyIcon } from "@lucide/svelte";
  import { translator } from "../../lib/i18n";
  import {
    listUserQuestions,
    askQuestion,
    answerQuestion,
    type PaidQuestionItem,
    type QACounts,
    getQACounts,
  } from "../../lib/tokens";
  import { currentUser } from "../../stores/auth";
  import { requestLogin } from "../../lib/login";
  import { toaster } from "../../stores/toaster";
  import { timeAgo } from "../../lib/utils";

  let { userId, username }: { userId: string; username: string } = $props();

  let questions = $state<PaidQuestionItem[]>([]);
  let counts = $state<QACounts | null>(null);
  let loading = $state(true);
  let error = $state(false);
  let showAsk = $state(false);
  let askText = $state("");
  let askAmount = $state(10);
  let askAnonymous = $state(false);
  let asking = $state(false);

  // Reply state per question
  let replyTexts = $state<Record<string, string>>({});
  let replying = $state<Record<string, boolean>>({});

  let isOwner = $derived($currentUser?.id === userId);

  async function loadData() {
    try {
      const [qData, cData] = await Promise.all([
        listUserQuestions(userId, 1, 20),
        getQACounts(userId),
      ]);
      questions = qData.items;
      counts = cData;
    } catch {
      error = true;
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    void loadData();
  });

  async function handleAsk() {
    if (!$currentUser) {
      requestLogin(window.location.pathname);
      return;
    }
    if (!askText.trim() || askAmount < 1) return;
    asking = true;
    try {
      await askQuestion(userId, askText.trim(), askAmount, askAnonymous);
      toaster.success($translator("tokens.qa.askSuccess"));
      showAsk = false;
      askText = "";
      askAmount = 10;
      askAnonymous = false;
      await loadData();
    } catch (e: any) {
      toaster.error(e.message || $translator("tokens.qa.askFailed"));
    } finally {
      asking = false;
    }
  }

  async function handleReply(q: PaidQuestionItem) {
    const text = replyTexts[q.id]?.trim();
    if (!text) return;
    replying = { ...replying, [q.id]: true };
    try {
      await answerQuestion(q.id, text);
      toaster.success($translator("tokens.qa.replySuccess"));
      replyTexts = { ...replyTexts, [q.id]: "" };
      await loadData();
    } catch (e: any) {
      toaster.error(e.message || $translator("tokens.qa.replyFailed"));
    } finally {
      replying = { ...replying, [q.id]: false };
    }
  }

  // Whether the current viewer is authorized to see the raw anonymous text.
  // The backend already masks it, but we also use this for the blur overlay.
  function canSeeContent(q: PaidQuestionItem): boolean {
    if (!q.is_anonymous) return true;
    if (!$currentUser) return false;
    return $currentUser.id === q.to_user.id || (q.from_user?.id === $currentUser.id);
  }

  // Check if the masked placeholder is being returned by the backend
  function isMasked(q: PaidQuestionItem): boolean {
    return q.is_anonymous && !canSeeContent(q);
  }
</script>

{#if loading}
  <div class="qa-loading"><div class="spinner"></div></div>
{:else if error}
  <p class="qa-error">{$translator("tokens.qa.loadFailed")}</p>
{:else}
  <div class="qa-section">
    <div class="qa-header">
      <div class="qa-stats">
        <span><MessageCircleIcon size={13} /> {counts?.questions_received ?? 0} {$translator("tokens.qa.received")}</span>
        <span><CheckIcon size={13} /> {counts?.questions_answered ?? 0} {$translator("tokens.qa.answered")}</span>
      </div>
      {#if !isOwner}
        <button class="btn btn-primary btn-xs" onclick={() => (showAsk = !showAsk)}>
          {$translator("tokens.qa.askButton")}
        </button>
      {/if}
    </div>

    {#if showAsk}
      <div class="qa-ask-form">
        <textarea
          bind:value={askText}
          rows={3}
          placeholder={$translator("tokens.qa.askPlaceholder", { username })}
          maxlength={500}
        ></textarea>
        <div class="qa-ask-controls">
          <div class="qa-ask-amount">
            <label>{$translator("tokens.qa.amount")}</label>
            <input type="number" bind:value={askAmount} min={1} max={10000} />
            <span>AGC</span>
          </div>
          <label class="qa-anon-toggle">
            <input type="checkbox" bind:checked={askAnonymous} />
            <EyeOffIcon size={13} />
            {$translator("tokens.qa.anonymous")}
          </label>
          <button class="btn btn-primary btn-xs" onclick={handleAsk} disabled={asking || !askText.trim()}>
            <SendIcon size={12} />
            {asking ? $translator("common.processing") : $translator("tokens.qa.send")}
          </button>
        </div>
      </div>
    {/if}

    {#if questions.length > 0}
      <div class="qa-list">
        {#each questions as q (q.id)}
          <div class="qa-card" class:unanswered={!q.is_answered}>
            <!-- Question header: asker info + status -->
            <div class="qa-card-header">
              <span class="qa-asker">
                {#if q.from_user}
                  <a href="/users/{q.from_user.id}">@{q.from_user.username}</a>
                {:else}
                  <span class="qa-anon-label">
                    <EyeOffIcon size={12} />
                    {$translator("tokens.qa.anonymousUser")}
                  </span>
                {/if}
              </span>
              <span class="qa-amount">{q.amount} AGC</span>
              {#if !q.is_answered}
                <span class="qa-badge qa-badge-pending">{$translator("tokens.qa.pendingReply")}</span>
              {:else}
                <span class="qa-badge qa-badge-done"><CheckIcon size={11} /> {$translator("tokens.qa.answered")}</span>
              {/if}
            </div>

            <!-- Question text (with frosted-glass blur for masked anonymous) -->
            <div class="qa-question-text" class:blurred={isMasked(q)}>
              {#if isMasked(q)}
                <div class="qa-blur-overlay">
                  <EyeOffIcon size={16} />
                  <span>{$translator("tokens.qa.anonymousQuestion")}</span>
                </div>
              {:else}
                <p>{q.question_text}</p>
              {/if}
            </div>

            <div class="qa-card-meta">
              <span>{timeAgo(q.created_at)}</span>
            </div>

            <!-- Reply section: show answer if answered, or reply box if owner -->
            {#if q.is_answered}
              <div class="qa-answer-box" class:blurred={isMasked(q)}>
                <div class="qa-answer-label">
                  <ReplyIcon size={12} />
                  <span>@{q.to_user.username}</span>
                </div>
                {#if isMasked(q)}
                  <div class="qa-blur-overlay">
                    <EyeOffIcon size={16} />
                    <span>{$translator("tokens.qa.anonymousQuestion")}</span>
                  </div>
                {:else}
                  <p class="qa-answer-text">{q.answer_text}</p>
                {/if}
                {#if !isMasked(q) && q.answered_at}
                  <span class="qa-answer-meta">{timeAgo(q.answered_at)}</span>
                {/if}
              </div>
            {:else if isOwner}
              <!-- Reply input for the profile owner -->
              <div class="qa-reply-form">
                <textarea
                  rows={2}
                  placeholder={$translator("tokens.qa.replyPlaceholder")}
                  value={replyTexts[q.id] ?? ""}
                  oninput={(e) => (replyTexts = { ...replyTexts, [q.id]: e.currentTarget.value })}
                  maxlength={1000}
                ></textarea>
                <button
                  class="btn btn-primary btn-xs"
                  onclick={() => handleReply(q)}
                  disabled={replying[q.id] || !(replyTexts[q.id]?.trim())}
                >
                  <SendIcon size={12} />
                  {replying[q.id] ? $translator("tokens.qa.replying") : $translator("tokens.qa.reply")}
                </button>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {:else}
      <p class="qa-empty">{$translator("tokens.qa.empty")}</p>
    {/if}
  </div>
{/if}

<style>
  .qa-loading { display: flex; justify-content: center; padding: 1.5rem 0; }
  .spinner {
    width: 20px; height: 20px; border: 2px solid var(--vercel-border);
    border-top-color: var(--vercel-accent); border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .qa-section { border: 1px solid var(--vercel-border); border-radius: var(--vercel-radius); padding: 1rem; background: var(--vercel-card); }
  .qa-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; }
  .qa-stats { display: flex; gap: 1rem; color: var(--vercel-text-tertiary); font-size: 0.72rem; }
  .qa-stats span { display: flex; align-items: center; gap: 0.25rem; }

  .qa-ask-form { margin-bottom: 0.75rem; }
  .qa-ask-form textarea {
    width: 100%; padding: 0.5rem; border: 1px solid var(--vercel-border); border-radius: 6px;
    background: var(--vercel-surface); color: var(--vercel-text); font-size: 0.8rem; resize: vertical;
  }
  .qa-ask-controls { display: flex; align-items: center; gap: 0.75rem; margin-top: 0.5rem; flex-wrap: wrap; }
  .qa-ask-amount { display: flex; align-items: center; gap: 0.3rem; }
  .qa-ask-amount label { font-size: 0.7rem; color: var(--vercel-text-tertiary); }
  .qa-ask-amount input { width: 5rem; padding: 0.2rem 0.4rem; border: 1px solid var(--vercel-border); border-radius: 4px; background: var(--vercel-surface); color: var(--vercel-text); font-size: 0.78rem; }
  .qa-ask-amount span { font-size: 0.7rem; color: var(--vercel-text-tertiary); }
  .qa-anon-toggle { display: flex; align-items: center; gap: 0.25rem; font-size: 0.7rem; color: var(--vercel-text-tertiary); cursor: pointer; }

  .qa-list { display: grid; gap: 0.75rem; }

  .qa-card {
    border: 1px solid var(--vercel-border); border-radius: 8px;
    padding: 0.75rem; background: var(--vercel-surface-muted);
    transition: border-color 0.15s;
  }
  .qa-card.unanswered { border-color: color-mix(in srgb, var(--vercel-accent) 30%, var(--vercel-border)); }

  .qa-card-header {
    display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.4rem;
    font-size: 0.72rem;
  }
  .qa-asker { flex: 1; color: var(--vercel-text-tertiary); }
  .qa-asker a { color: var(--vercel-accent); font-weight: 500; }
  .qa-anon-label { display: flex; align-items: center; gap: 0.25rem; color: var(--vercel-text-tertiary); }
  .qa-amount { color: var(--vercel-text-secondary); font-weight: 600; font-variant-numeric: tabular-nums; }
  .qa-badge {
    display: flex; align-items: center; gap: 0.2rem;
    padding: 0.1rem 0.4rem; border-radius: 999px; font-size: 0.62rem; font-weight: 600;
  }
  .qa-badge-pending { background: color-mix(in srgb, var(--vercel-accent) 12%, transparent); color: var(--vercel-accent); }
  .qa-badge-done { background: color-mix(in srgb, #22c55e 12%, transparent); color: #16a34a; }

  .qa-question-text {
    position: relative; min-height: 1.5rem;
  }
  .qa-question-text p {
    font-size: 0.83rem; color: var(--vercel-text); margin: 0; line-height: 1.5;
  }
  /* Frosted-glass blur overlay for anonymous questions visible to unauthorized viewers */
  .qa-question-text.blurred,
  .qa-answer-box.blurred {
    filter: blur(5px); user-select: none; pointer-events: none;
  }
  .qa-blur-overlay {
    display: flex; align-items: center; gap: 0.4rem;
    color: var(--vercel-text-tertiary); font-size: 0.78rem;
    padding: 0.3rem 0;
  }

  .qa-card-meta {
    margin-top: 0.3rem; font-size: 0.65rem; color: var(--vercel-text-tertiary);
  }

  /* Answer display */
  .qa-answer-box {
    margin-top: 0.5rem; padding: 0.6rem 0.75rem;
    border-left: 3px solid var(--vercel-accent);
    background: var(--vercel-surface); border-radius: 0 6px 6px 0;
  }
  .qa-answer-label {
    display: flex; align-items: center; gap: 0.3rem;
    font-size: 0.68rem; color: var(--vercel-accent); font-weight: 600; margin-bottom: 0.25rem;
  }
  .qa-answer-text { font-size: 0.8rem; color: var(--vercel-text-secondary); margin: 0; line-height: 1.5; }
  .qa-answer-meta { font-size: 0.62rem; color: var(--vercel-text-tertiary); }

  /* Reply form for the profile owner */
  .qa-reply-form {
    margin-top: 0.5rem; display: flex; flex-direction: column; gap: 0.4rem;
  }
  .qa-reply-form textarea {
    width: 100%; padding: 0.45rem; border: 1px solid var(--vercel-border); border-radius: 6px;
    background: var(--vercel-surface); color: var(--vercel-text); font-size: 0.78rem; resize: vertical;
  }
  .qa-reply-form textarea:focus { border-color: var(--vercel-accent); outline: none; }
  .qa-reply-form button { align-self: flex-end; }

  .qa-empty { text-align: center; color: var(--vercel-text-tertiary); font-size: 0.75rem; padding: 1rem 0; }
  .qa-error { text-align: center; color: var(--vercel-danger, #ef4444); font-size: 0.75rem; padding: 1rem 0; }
</style>
