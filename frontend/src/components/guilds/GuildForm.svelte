<script lang="ts">
  import { createGuild } from "../../lib/guilds";
  import { translator, translateError } from "../../lib/i18n";

  let name = $state("");
  let logo = $state("");
  let description = $state("");
  let saving = $state(false);
  let error = $state("");

  async function handleSubmit() {
    if (!name.trim()) { error = $translator("guild.nameRequired"); return; }
    saving = true; error = "";
    try {
      const g = await createGuild({ name: name.trim(), logo: logo.trim() || null, description: description.trim() || null });
      window.location.href = `/guilds/${g.id}`;
    } catch (e: any) {
      error = translateError(e, $translator, "guild.createFailed");
    } finally {
      saving = false;
    }
  }
</script>

<div class="card p-6">
  <h1 class="text-xl font-bold mb-6" style="color: var(--vercel-text);">{$translator("guild.create")}</h1>

  {#if error}
    <div class="mb-4 p-3 rounded text-sm" style="background: var(--vercel-danger-bg); color: var(--vercel-danger);">{error}</div>
  {/if}

  <div class="space-y-4">
    <div>
      <label for="guild-name" class="block text-xs mb-1" style="color: var(--vercel-text-secondary);">{$translator("guild.name")} *</label>
      <input id="guild-name" class="input" type="text" bind:value={name} placeholder={$translator("guild.namePlaceholder")} maxlength="80" />
    </div>
    <div>
      <label for="guild-logo" class="block text-xs mb-1" style="color: var(--vercel-text-secondary);">{$translator("guild.logo")}</label>
      <input id="guild-logo" class="input" type="text" bind:value={logo} placeholder={$translator("guild.logoPlaceholder")} maxlength="500" />
    </div>
    <div>
      <label for="guild-description" class="block text-xs mb-1" style="color: var(--vercel-text-secondary);">{$translator("guild.description")}</label>
      <textarea id="guild-description" class="input" rows="3" bind:value={description} placeholder={$translator("guild.descriptionPlaceholder")} maxlength="2000"></textarea>
    </div>
  </div>

  <div class="flex justify-end gap-3 mt-6">
    <a href="/guilds" class="btn btn-ghost btn-sm">{$translator("common.cancel")}</a>
    <button class="btn btn-primary" onclick={handleSubmit} disabled={saving}>
      {$translator(saving ? "common.creating" : "guild.create")}
    </button>
  </div>
</div>
