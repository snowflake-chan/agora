<script lang="ts">
  import { locale } from "../lib/i18n";
  import { timeAgo } from "../lib/utils";
  import { relativeTimeClock } from "../stores/relativeTime";

  let { value, className = "" }: { value: string; className?: string } = $props();

  let parsed = $derived(new Date(value));
  let valid = $derived(!Number.isNaN(parsed.getTime()));
  let relative = $derived.by(() => {
    void $relativeTimeClock;
    return valid ? timeAgo(value, $locale) : value;
  });
  let absolute = $derived.by(() => {
    if (!valid) return value;
    return new Intl.DateTimeFormat($locale, {
      dateStyle: "full",
      timeStyle: "long",
    }).format(parsed);
  });
</script>

<time class={className} datetime={valid ? parsed.toISOString() : value} title={absolute} aria-label={absolute}>
  {relative}
</time>
