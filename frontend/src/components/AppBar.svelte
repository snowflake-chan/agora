<script lang="ts">
  import { MenuIcon, SearchIcon, LogOutIcon } from "@lucide/svelte";
  import { AppBar, Avatar, Menu } from "@skeletonlabs/skeleton-svelte";
  import { onMount } from "svelte";
  import { initAuth, currentUser, logout } from "../stores/auth";

  onMount(() => {
    initAuth();
  });

  async function handleLogout() {
    await logout();
    window.location.href = "/";
  }
</script>

<AppBar>
  <AppBar.Toolbar class="grid-cols-[auto_1fr_auto]">
    <AppBar.Lead>
      <button type="button" class="btn-icon btn-icon-lg hover:preset-tonal">
        <MenuIcon />
      </button>
    </AppBar.Lead>

    <AppBar.Headline>
      <a href="/" class="text-2xl font-bold no-underline text-surface-900">
        Agora
      </a>
    </AppBar.Headline>

    <AppBar.Trail>
      <button type="button" class="btn-icon hover:preset-tonal">
        <SearchIcon class="size-6" />
      </button>

      {#if $currentUser}
        <Menu>
          <Menu.Trigger class="flex-none rounded-full">
            <Avatar class="size-8">
              <Avatar.Fallback>{($currentUser.nickname ?? $currentUser.username)[0].toUpperCase()}</Avatar.Fallback>
            </Avatar>
          </Menu.Trigger>
          <Menu.Positioner>
            <Menu.Content class="min-w-40">
              <div class="px-3 py-2 text-sm text-surface-500">
                {$currentUser.nickname ?? $currentUser.username}
              </div>
              <Menu.Separator />
              <Menu.Item value="logout" onclick={handleLogout}>
                <LogOutIcon class="size-4" />
                <Menu.ItemText>退出登录</Menu.ItemText>
              </Menu.Item>
            </Menu.Content>
          </Menu.Positioner>
        </Menu>
      {:else}
        <a href="/login" class="btn preset-filled-primary-500 text-sm">登录</a>
        <a href="/register" class="btn preset-tonal text-sm">注册</a>
      {/if}
    </AppBar.Trail>
  </AppBar.Toolbar>
</AppBar>
