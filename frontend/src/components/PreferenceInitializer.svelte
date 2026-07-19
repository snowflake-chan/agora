<script lang="ts">
  import { onMount } from "svelte";
  import { initI18n } from "../lib/i18n";
  import { initPreferences } from "../lib/preferences";

  onMount(() => {
    initI18n();
    initPreferences();
    document.documentElement.dataset.uiReady = "true";
  });
</script>
