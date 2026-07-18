<script lang="ts">
  import { onMount } from "svelte";

  interface ToastItem {
    id: number;
    type: "success" | "error" | "info";
    title: string;
    description?: string;
  }

  let toasts: ToastItem[] = [];
  let nextId = 0;

  function show(type: ToastItem["type"], title: string, description?: string) {
    const id = nextId++;
    toasts = [...toasts, { id, type, title, description }];
    setTimeout(() => {
      toasts = toasts.filter((t) => t.id !== id);
    }, 4000);
  }

  function dismiss(id: number) {
    toasts = toasts.filter((t) => t.id !== id);
  }

  // Expose globally for other components
  onMount(() => {
    (window as any).__toaster = { show, dismiss };
  });
</script>

{#if toasts.length > 0}
  <div class="toast-container">
    {#each toasts as toast (toast.id)}
      <div class="toast toast-{toast.type}">
        <div class="toast-body">
          <div class="toast-title">{toast.title}</div>
          {#if toast.description}
            <div class="toast-desc">{toast.description}</div>
          {/if}
        </div>
        <button class="toast-close" on:click={() => dismiss(toast.id)}>&times;</button>
      </div>
    {/each}
  </div>
{/if}