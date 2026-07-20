<script lang="ts">
  import { createGuild } from "../../lib/guilds";

  let name = $state("");
  let logo = $state("");
  let description = $state("");
  let saving = $state(false);
  let error = $state("");

  async function handleSubmit() {
    if (!name.trim()) { error = "请输入社团名称"; return; }
    saving = true; error = "";
    try {
      const g = await createGuild({ name: name.trim(), logo: logo.trim() || null, description: description.trim() || null });
      window.location.href = `/guilds/${g.id}`;
    } catch (e: any) {
      error = e.message || "创建失败";
    } finally {
      saving = false;
    }
  }
</script>

<div class="card p-6">
  <h1 class="text-xl font-bold mb-6" style="color: var(--vercel-text);">创建社团</h1>

  {#if error}
    <div class="mb-4 p-3 rounded text-sm" style="background: rgba(239,68,68,0.1); color: var(--vercel-danger);">{error}</div>
  {/if}

  <div class="space-y-4">
    <div>
      <label class="block text-xs mb-1" style="color: var(--vercel-text-secondary);">社团名称 *</label>
      <input class="input" type="text" bind:value={name} placeholder="给你的社团起个名字" maxlength="80" />
    </div>
    <div>
      <label class="block text-xs mb-1" style="color: var(--vercel-text-secondary);">Logo (emoji)</label>
      <input class="input" type="text" bind:value={logo} placeholder="一个 emoji 作为 logo，如 🚀" maxlength="10" />
    </div>
    <div>
      <label class="block text-xs mb-1" style="color: var(--vercel-text-secondary);">简介</label>
      <textarea class="input" rows="3" bind:value={description} placeholder="介绍一下社团" maxlength="300"></textarea>
    </div>
  </div>

  <div class="flex justify-end gap-3 mt-6">
    <a href="/guilds" class="btn btn-ghost btn-sm">取消</a>
    <button class="btn btn-primary" onclick={handleSubmit} disabled={saving}>
      {saving ? "创建中..." : "创建社团"}
    </button>
  </div>
</div>
