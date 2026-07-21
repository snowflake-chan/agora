<script module lang="ts">
  export type RevisionSnapshot = {
    version: number;
    title: string | null;
    content: string;
    tags?: string[] | null;
    edited_at: string;
  };
</script>

<script lang="ts">
  import { HistoryIcon } from "@lucide/svelte";
  import { translator } from "../../lib/i18n";
  import { renderMarkdown } from "../../lib/markdown";
  import GlassModal from "../GlassModal.svelte";
  import RelativeTime from "../RelativeTime.svelte";

  let {
    show,
    current,
    load,
    onclose,
  }: {
    show: boolean;
    current: RevisionSnapshot | null;
    load: () => Promise<RevisionSnapshot[]>;
    onclose: () => void;
  } = $props();

  let history = $state<RevisionSnapshot[]>([]);
  let loading = $state(false);
  let failed = $state(false);
  let requestId = 0;
  let openedFor = $state("");

  $effect(() => {
    const key = show && current ? `${current.version}:${current.edited_at}` : "";
    if (!key) {
      openedFor = "";
      return;
    }
    if (key === openedFor) return;
    openedFor = key;
    void loadHistory();
  });

  async function loadHistory() {
    const activeRequest = ++requestId;
    loading = true;
    failed = false;
    history = [];
    try {
      const result = await load();
      if (activeRequest === requestId) history = result;
    } catch {
      if (activeRequest === requestId) failed = true;
    } finally {
      if (activeRequest === requestId) loading = false;
    }
  }
</script>

<GlassModal {show} title={$translator("revision.historyTitle")} {onclose}>
  <p class="history-intro">{$translator("revision.historyDescription")}</p>

  {#if current}
    <div class="history-list">
      <article class="revision-card current-version">
        <header>
          <div class="version-label">
            <HistoryIcon size={15} strokeWidth={1.8} aria-hidden="true" />
            <strong>{$translator("revision.version", { version: current.version })}</strong>
            <span>{$translator("revision.current")}</span>
          </div>
          <RelativeTime value={current.edited_at} />
        </header>
        {#if current.title}<h3>{current.title}</h3>{/if}
        <div class="markdown-body revision-copy">{@html renderMarkdown(current.content)}</div>
        {#if current.tags?.length}
          <div class="revision-tags">
            {#each current.tags as tag}<span class="badge badge-neutral">{tag}</span>{/each}
          </div>
        {/if}
      </article>

      {#if loading}
        <div class="history-state"><span class="spinner"></span>{$translator("revision.loading")}</div>
      {:else if failed}
        <div class="history-state error-state">
          <span>{$translator("revision.loadFailed")}</span>
          <button type="button" class="btn btn-ghost btn-sm" onclick={() => void loadHistory()}>
            {$translator("common.retry")}
          </button>
        </div>
      {:else}
        {#each history as item (item.version)}
          <article class="revision-card">
            <header>
              <strong>{$translator("revision.version", { version: item.version })}</strong>
              <span class="revision-time">
                {$translator("revision.replacedAt")}
                <RelativeTime value={item.edited_at} />
              </span>
            </header>
            {#if item.title}<h3>{item.title}</h3>{/if}
            <div class="markdown-body revision-copy">{@html renderMarkdown(item.content)}</div>
            {#if item.tags?.length}
              <div class="revision-tags">
                {#each item.tags as tag}<span class="badge badge-neutral">{tag}</span>{/each}
              </div>
            {/if}
          </article>
        {/each}
      {/if}
    </div>
  {/if}
</GlassModal>

<style>
  .history-intro {
    margin: -0.2rem 0 1rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
    line-height: 1.5;
  }

  .history-list {
    display: grid;
    gap: 0.75rem;
  }

  .revision-card {
    overflow: hidden;
    padding: 0.85rem;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius-sm);
    background: var(--vercel-surface-muted);
  }

  .revision-card.current-version {
    border-color: color-mix(in srgb, var(--vercel-accent) 35%, var(--vercel-border));
    background: color-mix(in srgb, var(--vercel-accent) 5%, var(--vercel-card));
  }

  .revision-card header,
  .version-label,
  .revision-tags {
    display: flex;
    align-items: center;
  }

  .revision-card header {
    justify-content: space-between;
    gap: 0.75rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.68rem;
  }

  .version-label,
  .revision-tags {
    gap: 0.4rem;
  }

  .version-label strong,
  .revision-card header > strong {
    color: var(--vercel-text);
    font-size: 0.75rem;
  }

  .version-label > span {
    padding: 0.08rem 0.35rem;
    border-radius: 999px;
    color: var(--vercel-accent);
    background: color-mix(in srgb, var(--vercel-accent) 10%, transparent);
    font-size: 0.62rem;
    font-weight: 650;
  }

  .revision-card h3 {
    margin: 0.65rem 0 0;
    color: var(--vercel-text);
    font-size: 0.9rem;
    font-weight: 650;
    line-height: 1.4;
  }

  .revision-copy {
    max-height: 12rem;
    overflow: auto;
    margin-top: 0.6rem;
    color: var(--vercel-text-secondary);
    font-size: 0.78rem;
  }

  .revision-tags {
    flex-wrap: wrap;
    margin-top: 0.7rem;
  }

  .revision-time {
    text-align: right;
  }

  .history-state {
    display: flex;
    min-height: 4rem;
    align-items: center;
    justify-content: center;
    gap: 0.55rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
  }

  .error-state {
    flex-direction: column;
  }
</style>
