<script lang="ts">
  import { SaveIcon, ShieldCheckIcon } from "@lucide/svelte";
  import { translateError, translator } from "../../lib/i18n";
  import { toaster } from "../../stores/toaster";
  import GlassModal from "../GlassModal.svelte";
  import WritingAssist from "../posts/WritingAssist.svelte";

  type EditKind = "post" | "comment" | "patch";
  type EditPayload = {
    revision_number: number;
    title?: string;
    content: string;
    tags?: string[] | null;
  };

  let {
    show,
    kind,
    title = "",
    content,
    tags = null,
    revisionNumber,
    onclose,
    onsave,
  }: {
    show: boolean;
    kind: EditKind;
    title?: string;
    content: string;
    tags?: string[] | null;
    revisionNumber: number;
    onclose: () => void;
    onsave: (payload: EditPayload) => Promise<void>;
  } = $props();

  let draftTitle = $state("");
  let draftContent = $state("");
  let draftTags = $state("");
  let saving = $state(false);
  let initializedFor = $state("");
  let hasTitle = $derived(kind !== "comment");
  let showTags = $derived(kind === "post");
  let normalizedTags = $derived(
    draftTags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean),
  );
  let unchanged = $derived(
    draftContent.trim() === content.trim()
      && (!hasTitle || draftTitle.trim() === title.trim())
      && (!showTags || JSON.stringify(normalizedTags) === JSON.stringify(tags ?? [])),
  );
  let invalid = $derived(
    !draftContent.trim() || (hasTitle && !draftTitle.trim()) || unchanged,
  );

  $effect(() => {
    const key = show ? `${kind}:${revisionNumber}` : "";
    if (!show) {
      initializedFor = "";
      return;
    }
    if (key === initializedFor) return;
    initializedFor = key;
    draftTitle = title;
    draftContent = content;
    draftTags = (tags ?? []).join(", ");
  });

  async function submit() {
    if (invalid || saving) return;
    saving = true;
    try {
      await onsave({
        revision_number: revisionNumber,
        ...(hasTitle ? { title: draftTitle.trim() } : {}),
        content: draftContent.trim(),
        ...(showTags ? { tags: normalizedTags.length ? normalizedTags : null } : {}),
      });
      onclose();
      toaster.success($translator("revision.saved"), $translator("revision.savedDescription"));
    } catch (error) {
      toaster.error(
        $translator("revision.saveFailed"),
        translateError(error, $translator, "common.tryAgain"),
      );
    } finally {
      saving = false;
    }
  }
</script>

<GlassModal {show} title={$translator(`revision.edit.${kind}`)} {onclose}>
  <div class="audit-note">
    <ShieldCheckIcon size={17} strokeWidth={1.8} aria-hidden="true" />
    <p>{$translator(kind === "patch" ? "revision.patchLockNotice" : "revision.publicNotice")}</p>
  </div>

  <form class="edit-form" onsubmit={(event) => { event.preventDefault(); void submit(); }}>
    {#if hasTitle}
      <label>
        <span>{$translator("common.title")}</span>
        <input class="input" bind:value={draftTitle} maxlength="200" required />
      </label>
    {/if}

    <label>
      <span>{$translator(kind === "comment" ? "common.comment" : "revision.body")}</span>
      <textarea class="input content-input" bind:value={draftContent} required></textarea>
    </label>

    {#if showTags}
      <label>
        <span>{$translator("revision.tags")}</span>
        <input class="input" bind:value={draftTags} placeholder={$translator("revision.tagsPlaceholder")} />
      </label>
    {/if}

    <div class="edit-assist">
      <WritingAssist
        title={hasTitle ? draftTitle : ""}
        body={draftContent}
        context={kind}
        onApply={(value) => {
          if (hasTitle) draftTitle = value.title;
          draftContent = value.body;
        }}
      />
    </div>

    <div class="form-footer">
      <span>{$translator("revision.editingVersion", { version: revisionNumber })}</span>
      <div class="form-actions">
        <button type="button" class="btn btn-ghost btn-sm" onclick={onclose}>
          {$translator("common.cancel")}
        </button>
        <button type="submit" class="btn btn-primary btn-sm" disabled={invalid || saving}>
          <SaveIcon size={15} strokeWidth={1.8} aria-hidden="true" />
          {$translator(saving ? "revision.saving" : "common.save")}
        </button>
      </div>
    </div>
  </form>
</GlassModal>

<style>
  .audit-note {
    display: flex;
    gap: 0.65rem;
    margin-bottom: 1rem;
    padding: 0.75rem;
    border: 1px solid color-mix(in srgb, var(--vercel-warning) 30%, var(--vercel-border));
    border-radius: var(--vercel-radius-sm);
    color: var(--vercel-text-secondary);
    background: color-mix(in srgb, var(--vercel-warning) 7%, var(--vercel-card));
    font-size: 0.76rem;
    line-height: 1.5;
  }

  .audit-note :global(svg) {
    flex: 0 0 auto;
    margin-top: 0.05rem;
    color: var(--vercel-warning);
  }

  .edit-form,
  label {
    display: grid;
    gap: 0.5rem;
  }

  .edit-form {
    gap: 0.9rem;
  }

  label > span {
    color: var(--vercel-text-secondary);
    font-size: 0.75rem;
    font-weight: 600;
  }

  .content-input {
    min-height: 11rem;
    resize: vertical;
    line-height: 1.55;
  }

  .form-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding-top: 0.2rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.7rem;
  }

  .form-actions {
    display: flex;
    flex: 0 0 auto;
    gap: 0.5rem;
  }

  .edit-assist {
    display: flex;
    min-height: 2.5rem;
    align-items: center;
    justify-content: flex-end;
    padding-top: 0.2rem;
    border-top: 1px solid var(--vercel-border);
  }

  @media (max-width: 30rem) {
    .form-footer {
      align-items: stretch;
      flex-direction: column;
    }

    .form-actions {
      justify-content: flex-end;
    }
  }
</style>
