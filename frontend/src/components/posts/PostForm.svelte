<script lang="ts">
  import { BarChart3Icon, PlusIcon, SparklesIcon, Trash2Icon, XIcon } from "@lucide/svelte";
  import { createEventDispatcher, onMount } from "svelte";
  import { generatePoll, getAiStatus } from "../../lib/ai";
  import { ApiError } from "../../lib/auth";
  import { translator, locale, translateError } from "../../lib/i18n";
  import { renderMarkdown } from "../../lib/markdown";
  import { modal } from "../../lib/modal";
  import { appleEase } from "../../lib/motion";
  import { createPost, type PollCreateData } from "../../lib/posts";
  import { toaster } from "../../stores/toaster";
  import WritingAssist from "./WritingAssist.svelte";

  const dispatch = createEventDispatcher();
  const POLL_DURATIONS = [
    { hours: 24, key: "poll.duration1Day" },
    { hours: 72, key: "poll.duration3Days" },
    { hours: 168, key: "poll.duration7Days" },
    { hours: 720, key: "poll.duration30Days" },
  ];

  type AiGenerationState = "idle" | "generating" | "success" | "political" | "error";

  let title = "";
  let content = "";
  let submitting = false;
  let mobilePane: "edit" | "preview" = "edit";
  let pollEnabled = false;
  let pollQuestion = "";
  let pollOptions = ["", ""];
  let pollDurationHours = 72;
  let pollTouched = false;
  let pollValidation: string | null = null;
  let aiEnabled = false;
  let aiGenerationState: AiGenerationState = "idle";
  let aiGenerationError = "";
  let generatedQuestions: string[] = [];

  $: pollValidation = validatePoll();
  $: canGeneratePoll = title.trim().length >= 8 && content.trim().length >= 40;

  onMount(async () => {
    aiEnabled = (await getAiStatus()).enabled;
  });

  function close() {
    dispatch("close");
  }

  function validatePoll(): string | null {
    if (!pollEnabled) return null;
    if (!pollQuestion.trim()) return "poll.questionRequired";
    if (pollQuestion.trim().length < 5) return "poll.questionTooShort";
    if (pollQuestion.trim().length > 160) return "poll.questionTooLong";
    if (pollOptions.length < 2) return "poll.minOptions";
    if (pollOptions.length > 6) return "poll.maxOptions";
    if (pollOptions.some((option) => !option.trim())) return "poll.optionRequired";
    if (pollOptions.some((option) => option.trim().length > 80)) return "poll.optionTooLong";
    const seen = new Set<string>();
    for (const option of pollOptions) {
      const normalized = option.trim().replace(/\s+/g, " ").toLocaleLowerCase();
      if (seen.has(normalized)) return "poll.optionDuplicate";
      seen.add(normalized);
    }
    return null;
  }

  function getPollPayload(): PollCreateData | null {
    if (!pollEnabled) return null;
    if (validatePoll()) return null;
    return {
      question: pollQuestion.trim(),
      options: pollOptions.map((option) => option.trim()),
      duration_hours: pollDurationHours,
    };
  }

  function enablePoll() {
    pollEnabled = true;
    pollTouched = false;
  }

  function removePoll() {
    pollEnabled = false;
    pollQuestion = "";
    pollOptions = ["", ""];
    pollDurationHours = 72;
    pollTouched = false;
    aiGenerationState = "idle";
  }

  function addOption() {
    if (pollOptions.length >= 6) return;
    pollOptions = [...pollOptions, ""];
  }

  function removeOption(index: number) {
    if (pollOptions.length <= 2) return;
    pollOptions = pollOptions.filter((_, optionIndex) => optionIndex !== index);
  }

  function updateOption(index: number, value: string) {
    pollOptions = pollOptions.map((option, optionIndex) =>
      optionIndex === index ? value : option,
    );
  }

  async function generatePollFromPost() {
    if (!canGeneratePoll || aiGenerationState === "generating") return;
    aiGenerationState = "generating";
    aiGenerationError = "";
    try {
      const exclude = [...generatedQuestions, pollQuestion.trim()].filter(Boolean);
      const generated = await generatePoll(
        `${title.trim()}\n\n${content.trim()}`,
        $locale,
        exclude,
      );
      pollQuestion = generated.question;
      pollOptions = generated.options;
      generatedQuestions = [...generatedQuestions, generated.question].slice(-12);
      pollTouched = true;
      aiGenerationState = "success";
    } catch (error) {
      aiGenerationState = error instanceof ApiError && error.code === "POLITICAL_CONTENT_UNAVAILABLE"
        ? "political"
        : "error";
      if (aiGenerationState === "error") {
        aiGenerationError = translateError(error, $translator, "poll.generateFailed");
      }
    }
  }

  async function handleSubmit() {
    pollTouched = true;
    if (!title.trim() || !content.trim()) return;
    const poll = getPollPayload();
    if (pollEnabled && !poll) return;

    submitting = true;
    try {
      const post = await createPost({
        title: title.trim(),
        content: content.trim(),
        ...(poll ? { poll } : {}),
      });
      window.location.href = `/posts/${post.id}`;
    } catch {
      toaster.error($translator("post.publishFailed"), $translator("common.tryAgain"));
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
    aria-labelledby="post-composer-title"
    tabindex="-1"
    onclick={(e) => e.stopPropagation()}
    out:fly={{ y: 36, duration: 300, easing: appleEase }}
  >
    <div class="composer-header">
      <h2 id="post-composer-title" class="sr-only">{$translator("post.new")}</h2>
      <div class="flex-1">
        <input
          data-autofocus
          bind:value={title}
          class="w-full px-4 py-2.5 text-lg font-semibold rounded-lg focus:outline-none"
          style="background: var(--vercel-surface-muted); border: 1px solid var(--vercel-border); color: var(--vercel-text);"
          placeholder={$translator("common.title")}
        />
      </div>
      <button type="button" class="btn btn-ghost btn-sm" onclick={close}>{$translator("common.cancel")}</button>
      <button
        type="button"
        class="btn btn-primary btn-sm"
        onclick={handleSubmit}
        disabled={submitting || !title.trim() || !content.trim()}
      >
        {submitting ? $translator("common.publishing") : $translator("common.publish")}
      </button>
    </div>

    <div class="composer-tools">
      {#if !pollEnabled}
        <button type="button" class="composer-tool" onclick={enablePoll} title={$translator("poll.add")}>
          <BarChart3Icon size={16} strokeWidth={1.8} aria-hidden="true" />
          <span>{$translator("poll.add")}</span>
        </button>
      {:else}
        <span class="composer-tool-active">
          <BarChart3Icon size={16} strokeWidth={1.8} aria-hidden="true" />
          {$translator("poll.label")}
        </span>
      {/if}
      <div class="composer-tools-spacer"></div>
      <WritingAssist
        {title}
        body={content}
        context="composer"
        onApply={(value) => {
          title = value.title;
          content = value.body;
        }}
      />
    </div>

    {#if pollEnabled}
      <section class="poll-editor" aria-labelledby="poll-editor-title">
        <div class="poll-editor-header">
          <div>
            <h3 id="poll-editor-title">{$translator("poll.label")}</h3>
            <p>{$translator("poll.editorHint")}</p>
          </div>
          <div class="poll-editor-actions">
            {#if aiEnabled}
              <button
                type="button"
                class="btn btn-ghost btn-xs ai-generate"
                disabled={!canGeneratePoll || aiGenerationState === "generating"}
                title={!canGeneratePoll ? $translator("poll.needsContext") : $translator("poll.generate")}
                onclick={() => void generatePollFromPost()}
              >
                <SparklesIcon size={14} strokeWidth={1.8} aria-hidden="true" />
                {$translator(aiGenerationState === "generating" ? "poll.generating" : "poll.generate")}
              </button>
            {/if}
            <button
              type="button"
              class="btn-icon remove-poll"
              onclick={removePoll}
              title={$translator("poll.remove")}
              aria-label={$translator("poll.remove")}
            >
              <XIcon size={16} strokeWidth={1.9} aria-hidden="true" />
            </button>
          </div>
        </div>

        {#if aiEnabled}
          <p class="poll-ai-disclosure">{$translator("ai.externalProcessing")}</p>
        {/if}

        {#if aiGenerationState === "success"}
          <p class="poll-ai-state success" role="status">{$translator("poll.generated")}</p>
        {:else if aiGenerationState === "political"}
          <p class="poll-ai-state warning" role="status">{$translator("ai.politicalUnavailable")}</p>
        {:else if aiGenerationState === "error"}
          <p class="poll-ai-state warning" role="status">{aiGenerationError || $translator("poll.generateFailed")}</p>
        {/if}

        <label class="poll-field">
          <span>{$translator("poll.question")}</span>
          <input
            class="input"
            bind:value={pollQuestion}
            maxlength="160"
            aria-invalid={pollTouched && Boolean(pollValidation) ? "true" : undefined}
            onblur={() => pollTouched = true}
            placeholder={$translator("poll.questionPlaceholder")}
          />
        </label>

        <div class="poll-option-fields">
          <span class="poll-field-label">{$translator("poll.options")}</span>
          {#each pollOptions as option, index (index)}
            <div class="poll-option-row">
              <input
                class="input"
                value={option}
                maxlength="80"
                aria-label={$translator("poll.option", { number: index + 1 })}
                aria-invalid={pollTouched && Boolean(pollValidation) ? "true" : undefined}
                oninput={(event) => updateOption(index, (event.currentTarget as HTMLInputElement).value)}
                onblur={() => pollTouched = true}
                placeholder={$translator("poll.optionPlaceholder", { number: index + 1 })}
              />
              {#if pollOptions.length > 2}
                <button
                  type="button"
                  class="btn-icon remove-option"
                  onclick={() => removeOption(index)}
                  title={$translator("poll.removeOption", { number: index + 1 })}
                  aria-label={$translator("poll.removeOption", { number: index + 1 })}
                >
                  <Trash2Icon size={15} strokeWidth={1.8} aria-hidden="true" />
                </button>
              {/if}
            </div>
          {/each}
        </div>

        <div class="poll-bottom-row">
          <button
            type="button"
            class="btn btn-ghost btn-xs add-option"
            disabled={pollOptions.length >= 6}
            onclick={addOption}
          >
            <PlusIcon size={14} strokeWidth={1.8} aria-hidden="true" />
            {$translator("poll.addOption")}
          </button>
          <label class="poll-duration">
            <span>{$translator("poll.duration")}</span>
            <select class="input" bind:value={pollDurationHours} aria-label={$translator("poll.duration")}>
              {#each POLL_DURATIONS as duration}
                <option value={duration.hours}>{$translator(duration.key)}</option>
              {/each}
            </select>
          </label>
        </div>

        {#if pollTouched && pollValidation}
          <p class="poll-validation" role="alert">{$translator(pollValidation)}</p>
        {/if}
      </section>
    {/if}

    <div class="composer-tabs" role="tablist" aria-label={$translator("editor.view")}>
      <button type="button" class:active={mobilePane === "edit"} onclick={() => mobilePane = "edit"} role="tab" aria-selected={mobilePane === "edit"}>{$translator("common.edit")}</button>
      <button type="button" class:active={mobilePane === "preview"} onclick={() => mobilePane = "preview"} role="tab" aria-selected={mobilePane === "preview"}>{$translator("common.preview")}</button>
    </div>

    <div class="composer-workspace">
      <div class="composer-pane editor-pane" class:mobile-hidden={mobilePane !== "edit"}>
        <div class="px-4 py-2 text-xs font-medium border-b" style="color: var(--vercel-text-tertiary); border-color: var(--vercel-border);">
          {$translator("common.edit")}
        </div>
        <textarea
          bind:value={content}
          class="flex-1 w-full resize-none px-6 py-4 font-mono text-sm leading-relaxed focus:outline-none"
          style="background: transparent; color: var(--vercel-text);"
          placeholder={$translator("post.contentPlaceholder")}
        ></textarea>
      </div>

      <div class="composer-pane" class:mobile-hidden={mobilePane !== "preview"}>
        <div class="px-4 py-2 text-xs font-medium border-b" style="color: var(--vercel-text-tertiary); border-color: var(--vercel-border);">
          {$translator("common.preview")}
        </div>
        <div class="flex-1 overflow-y-auto px-6 py-4">
          {#if content.trim()}
            <div class="markdown-body">{@html renderMarkdown(content)}</div>
          {:else}
            <p class="text-sm" style="color: var(--vercel-text-tertiary);">{$translator("common.noContent")}</p>
          {/if}
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .composer-dialog { display:flex; flex-direction:column; width:100%; height:min(60rem,calc(100dvh - 2rem)); max-width:87.5rem; overflow:hidden; border:1px solid var(--vercel-border); border-radius:var(--vercel-radius-lg); background:color-mix(in srgb,var(--vercel-card) 96%,transparent); box-shadow:0 8px 48px var(--vercel-shadow); backdrop-filter:blur(24px); }
  .composer-header { display:flex; align-items:center; gap:1rem; padding:.75rem 1.5rem; border-bottom:1px solid var(--vercel-border); }
  .composer-tools { display:flex; min-height:2.75rem; align-items:center; gap:.5rem; padding:.35rem 1.25rem; border-bottom:1px solid var(--vercel-border); }
  .composer-tools-spacer { flex:1; }
  .composer-tool, .composer-tool-active { display:inline-flex; min-height:2rem; align-items:center; gap:.4rem; padding:.35rem .55rem; border-radius:var(--vercel-radius-sm); color:var(--vercel-text-secondary); font:inherit; font-size:.75rem; font-weight:600; }
  .composer-tool { background:transparent; cursor:pointer; transition:color 150ms ease, background-color 150ms ease; }
  .composer-tool:hover, .composer-tool:focus-visible { color:var(--vercel-text); background:var(--vercel-hover); }
  .composer-tool:focus-visible { outline:2px solid var(--vercel-ring); outline-offset:2px; }
  .composer-tool-active { color:var(--vercel-text); background:var(--vercel-hover); }
  .poll-editor { max-height:min(20rem,34dvh); overflow-y:auto; padding:.8rem 1.25rem 1rem; border-bottom:1px solid var(--vercel-border); background:color-mix(in srgb,var(--vercel-surface-muted) 50%,transparent); }
  .poll-editor-header, .poll-editor-actions, .poll-bottom-row { display:flex; align-items:center; }
  .poll-editor-header { justify-content:space-between; gap:1rem; }
  .poll-editor-header h3 { margin:0; color:var(--vercel-text); font-size:.875rem; font-weight:650; }
  .poll-editor-header p { margin:.15rem 0 0; color:var(--vercel-text-tertiary); font-size:.6875rem; line-height:1.4; }
  .poll-editor-actions { flex:0 0 auto; gap:.3rem; }
  .remove-poll, .remove-option { color:var(--vercel-text-tertiary); }
  .remove-poll:hover, .remove-option:hover { color:var(--vercel-danger); background:color-mix(in srgb,var(--vercel-danger) 8%,transparent); }
  .poll-ai-state, .poll-validation { margin:.65rem 0 0; font-size:.75rem; line-height:1.45; }
  .poll-ai-disclosure { margin:.55rem 0 0; color:var(--vercel-text-tertiary); font-size:.6875rem; line-height:1.45; }
  .poll-ai-state.success { color:var(--vercel-success); }
  .poll-ai-state.warning, .poll-validation { color:var(--vercel-danger); }
  .poll-field, .poll-option-fields { display:block; margin-top:.7rem; }
  .poll-field > span, .poll-field-label, .poll-duration > span { display:block; margin-bottom:.3rem; color:var(--vercel-text-secondary); font-size:.6875rem; font-weight:650; }
  .poll-editor .input[aria-invalid="true"] { border-color:color-mix(in srgb,var(--vercel-danger) 65%,var(--vercel-border)); }
  .poll-option-fields { display:grid; gap:.4rem; }
  .poll-option-row { display:grid; min-width:0; grid-template-columns:minmax(0,1fr) 2.25rem; gap:.35rem; }
  .poll-option-row:has(:only-child) { grid-template-columns:minmax(0,1fr); }
  .poll-bottom-row { justify-content:space-between; gap:1rem; margin-top:.75rem; }
  .add-option { flex:0 0 auto; }
  .poll-duration { display:flex; align-items:center; gap:.45rem; }
  .poll-duration > span { margin:0; white-space:nowrap; }
  .poll-duration select { width:auto; min-height:2rem; padding:.25rem 1.7rem .25rem .5rem; font-size:.75rem; }
  .composer-workspace { display:flex; flex:1; min-height:0; overflow:hidden; }
  .composer-pane { display:flex; flex:1; min-width:0; flex-direction:column; }
  .editor-pane { border-right:1px solid var(--vercel-border); }
  .composer-tabs { display:none; }
  @media (max-width: 48rem) {
    .composer-backdrop { padding:.5rem; }
    .composer-dialog { height:calc(100dvh - 1rem); border-radius:.875rem; }
    .composer-header { flex-wrap:wrap; gap:.5rem; padding:.75rem; }
    .composer-header > div { flex-basis:100%; order:-1; }
    .composer-tools { align-items:flex-start; flex-wrap:wrap; padding-inline:.75rem; }
    .composer-tools-spacer { display:none; }
    .poll-editor { max-height:40dvh; padding-inline:.75rem; }
    .composer-tabs { display:grid; grid-template-columns:1fr 1fr; gap:.25rem; margin:.5rem .75rem 0; padding:.2rem; border-radius:.6rem; background:var(--vercel-surface-muted); }
    .composer-tabs button { padding:.45rem; border-radius:.45rem; color:var(--vercel-text-tertiary); font-size:.75rem; font-weight:600; }
    .composer-tabs button.active { color:var(--vercel-text); background:var(--vercel-hover-strong); }
    .editor-pane { border-right:0; }
    .composer-pane.mobile-hidden { display:none; }
  }
  @media (max-width: 25rem) {
    .poll-editor-header { align-items:flex-start; }
    .poll-bottom-row { align-items:flex-start; flex-direction:column; gap:.55rem; }
  }
</style>
