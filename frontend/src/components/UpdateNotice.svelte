<script lang="ts">
  import { RefreshCwIcon, SparklesIcon } from "@lucide/svelte";
  import { onMount } from "svelte";
  import { translator } from "../lib/i18n";
  import { BUILD_VERSION } from "../lib/version";
  import GlassModal from "./GlassModal.svelte";

  const STORAGE_KEY = "agora:seenBuildVersion";
  const CHECK_INTERVAL_MS = 120_000;

  let show = $state(false);
  let targetVersion = $state(BUILD_VERSION);

  onMount(() => {
    if (!hasSeen(BUILD_VERSION)) showUpdate(BUILD_VERSION);

    const check = () => void checkForUpdate();
    const handleVisibility = () => {
      if (document.visibilityState === "visible") check();
    };
    const interval = window.setInterval(check, CHECK_INTERVAL_MS);
    window.addEventListener("focus", check);
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", check);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  });

  async function checkForUpdate() {
    try {
      const response = await fetch("/version.json", { cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json() as { version?: string };
      if (data.version && data.version !== BUILD_VERSION && !hasSeen(data.version)) showUpdate(data.version);
    } catch {}
  }

  function hasSeen(version: string) {
    try { return localStorage.getItem(STORAGE_KEY) === version; } catch { return false; }
  }

  function showUpdate(version: string) {
    targetVersion = version;
    show = true;
  }

  function rememberVersion() {
    try { localStorage.setItem(STORAGE_KEY, targetVersion); } catch {}
  }

  function dismiss() {
    rememberVersion();
    show = false;
  }

  function refresh() {
    rememberVersion();
    window.location.reload();
  }
</script>

<GlassModal {show} title={$translator("update.title")} onclose={dismiss}>
  <div class="update-copy">
    <span class="update-icon" aria-hidden="true"><SparklesIcon size={20} strokeWidth={1.8} /></span>
    <div>
      <strong>{$translator("update.heading")}</strong>
      <p>{$translator("update.description")}</p>
    </div>
  </div>
  <div class="update-actions">
    <button type="button" class="btn btn-ghost" onclick={dismiss}>{$translator("update.later")}</button>
    <button type="button" class="btn btn-primary" onclick={refresh}>
      <RefreshCwIcon size={15} strokeWidth={1.9} aria-hidden="true" />
      {$translator("update.refresh")}
    </button>
  </div>
</GlassModal>

<style>
  .update-copy {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.85rem;
    align-items: start;
  }

  .update-icon {
    display: grid;
    width: 2.5rem;
    height: 2.5rem;
    place-items: center;
    border-radius: 9999px;
    color: var(--vercel-accent);
    background: color-mix(in srgb, var(--vercel-accent) 12%, transparent);
  }

  strong {
    display: block;
    margin-bottom: 0.35rem;
    color: var(--vercel-text);
    font-size: 0.95rem;
  }

  p {
    color: var(--vercel-text-secondary);
    line-height: 1.55;
  }

  .update-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.55rem;
    margin-top: 1.25rem;
  }
</style>
