<script lang="ts">
  import { translator } from "../lib/i18n";

  let { messageKey }: { messageKey: string } = $props();
</script>

{$translator(messageKey)}
