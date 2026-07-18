<script lang="ts">
  import { onMount } from "svelte";
  import { PlusIcon, GitBranchIcon } from "@lucide/svelte";
  import { initAuth, currentUser } from "../stores/auth";
  import PostForm from "./posts/PostForm.svelte";
  import PatchForm from "./patches/PatchForm.svelte";

  let showPostForm = false;
  let showPatchForm = false;

  onMount(() => initAuth());
</script>

<div class="w-px h-5 mx-1 rounded-full" style="background: rgba(255,255,255,0.1);"></div>

<button
  class="pill-item"
  on:click={() => (showPostForm = true)}
  title="发帖"
>
  <PlusIcon class="size-4.5" />
  <span class="pill-tooltip">发帖</span>
</button>

{#if $currentUser}
  <button
    class="pill-item"
    on:click={() => (showPatchForm = true)}
    title="发起变更"
  >
    <GitBranchIcon class="size-4.5" />
    <span class="pill-tooltip">发起变更</span>
  </button>
{/if}

<a
  href="/login"
  class="pill-item"
  title="登录"
>
  <svg class="size-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
  <span class="pill-tooltip">登录</span>
</a>

{#if showPostForm}
  <PostForm on:close={() => (showPostForm = false)} />
{/if}
{#if showPatchForm}
  <PatchForm on:close={() => (showPatchForm = false)} />
{/if}
