<script lang="ts">
  import { onMount } from "svelte";
  import {
    Ban,
    Bot,
    Check,
    ChevronDown,
    ChevronUp,
    Coins,
    Eye,
    ShieldAlert,
    Trash2,
    RotateCcw,
    UnlockKeyhole,
    X,
  } from "@lucide/svelte";
  import {
    adminDeleteGuild,
    adminDeleteGuildDiscussion,
    adminRemoveMember,
    adminUpdateGuild,
    banUser,
    checkAdmin,
    deletePatchAdmin,
    deletePostAdmin,
    getAISettings,
    getBanStatus,
    listAdminGuildDiscussions,
    listAdminPatches,
    listAdminPosts,
    listModerationReviews,
    listReports,
    listUsers,
    resetAISettings,
    testAISettings,
    resolveReport,
    reviewModerationItem,
    setUserRole,
    unbanUser,
    updateAISettings,
    type AdminAISettings,
    type AdminGuildDiscussion,
    type AdminPatch,
    type AdminPost,
    type AdminUser,
    type AdminModerationItem,
    type ReportItem,
  } from "../../lib/admin";
  import {
    listGuilds,
    listMembers,
    type Guild,
    type GuildMember,
  } from "../../lib/guilds";
  import {
    getTokenParamHistory,
    getTokenParams,
    getTokenSupply,
    getMonetaryMetrics,
    getSupplyHistory,
    mintTokens,
    updateTokenParams,
    shortenPatchVote,
    type TokenParamHistoryItem,
    type TokenParams,
    type TokenSupply,
    type MonetaryMetrics,
    type SupplySnapshot,
  } from "../../lib/tokens";
  import { locale, translator, translateError } from "../../lib/i18n";
  import { currentUser, initAuth } from "../../stores/auth";
  import ConfirmDialog from "../ConfirmDialog.svelte";
  import GlassModal from "../GlassModal.svelte";
  import TokenSupplyChart from "./TokenSupplyChart.svelte";
  import TokenMonetaryPanel from "./TokenMonetaryPanel.svelte";

  type Tab = "reports" | "moderation" | "posts" | "patches" | "ai" | "users" | "guilds" | "tokens";
  type BanStatus = {
    id: string;
    type: string;
    reason: string | null;
    expires_at: string | null;
  };

  let tab = $state<Tab>("reports");
  let loading = $state(true);
  let isAdmin = $state(false);
  let isSuperAdmin = $state(false);
  let reports = $state<ReportItem[]>([]);
  let handlingReportId = $state<string | null>(null);
  let moderationReviews = $state<AdminModerationItem[]>([]);
  let moderationLoading = $state(false);
  let moderationError = $state(false);
  let posts = $state<AdminPost[]>([]);
  let patches = $state<AdminPatch[]>([]);
  let users = $state<AdminUser[]>([]);
  let guilds = $state<Guild[]>([]);
  let notice = $state("");
  let noticeKind = $state<"success" | "error">("success");
  let aiSettings = $state<AdminAISettings | null>(null);
  let aiApiKey = $state("");
  let aiSaving = $state(false);
  let aiTesting = $state(false);

  let expandedGuild = $state<string | null>(null);
  let guildMembers = $state<GuildMember[]>([]);
  let guildDiscussions = $state<AdminGuildDiscussion[]>([]);
  let guildLoading = $state(false);
  let guildSaving = $state(false);
  let guildLoadToken = 0;
  let guildDraft = $state({ name: "", logo: "", description: "", level: 1 });

  let banModal = $state(false);
  let banUserId = $state("");
  let banUsername = $state("");
  let banType = $state("ban_user");
  let banDays = $state(0);
  let banHours = $state(24);
  let banReason = $state("");
  let banReportId = $state("");
  let banSaving = $state(false);

  let unbanModal = $state(false);
  let unbanUserId = $state("");
  let unbanUsername = $state("");
  let unbanStatuses = $state<BanStatus[]>([]);

  let tokenSupply = $state<TokenSupply | null>(null);
  let tokenParams = $state<TokenParams | null>(null);
  let tokenParamDraft = $state<Partial<TokenParams>>({});
  let tokenParamHistory = $state<TokenParamHistoryItem[]>([]);
  let tokenLoading = $state(false);
  let tokenSaving = $state(false);
  let mintAmount = $state(0);
  let mintRecipient = $state("");
  let minting = $state(false);

  let monetaryMetrics = $state<MonetaryMetrics | null>(null);
  let supplyHistory = $state<SupplySnapshot[]>([]);

  // shorten-vote modal
  let shortenModal = $state(false);
  let shortenPatchId = $state("");
  let shortenPatchTitle = $state("");
  let shortenHours = $state<number | null>(null);
  let shortenSubmitting = $state(false);
  let shortenResult = $state<{ action: string; new_voting_ends_at?: string; outcome?: string } | null>(null);

  let confirmOpen = $state(false);
  let confirmTitle = $state("");
  let confirmDescription = $state("");
  let confirmText = $state("");
  let confirmAction = $state<() => void>(() => {});

  let moderationModal = $state(false);
  let moderationTarget = $state<AdminModerationItem | null>(null);
  let moderationDecision = $state<"approve" | "reject">("approve");
  let moderationNote = $state("");
  let moderationSaving = $state(false);

  const banOptions = [
    { value: "ban_user", key: "admin.ban.account" },
    { value: "mute_post", key: "admin.ban.posts" },
    { value: "mute_patch", key: "admin.ban.patches" },
  ];

  const tokenParamOrder: Array<keyof TokenParams> = [
    "like_reward",
    "vote_reward",
    "proposal_pass_reward",
    "daily_login_base",
    "proposal_deposit",
    "boost_price_low",
    "boost_price_mid",
    "boost_price_high",
    "guild_create_fee",
    "daily_user_cap",
  ];

  onMount(async () => {
    const user = await initAuth();
    isSuperAdmin = user?.role === "super_admin";
    isAdmin = await checkAdmin();
    if (isAdmin) await refresh();
    loading = false;
  });

  function showNotice(text: string, kind: "success" | "error" = "success") {
    notice = text;
    noticeKind = kind;
  }

  async function refresh() {
    try {
      [reports, posts, patches] = await Promise.all([
        listReports(),
        listAdminPosts(),
        listAdminPatches(),
      ]);
      await loadModerationReviews();
      if (isSuperAdmin) {
        [users, guilds, aiSettings] = await Promise.all([
          listUsers(),
          listGuilds(),
          getAISettings(),
        ]);
        await loadTokenEconomy();
      }
    } catch (error) {
      showNotice(
        translateError(error, $translator, "admin.loadFailed"),
        "error",
      );
    }
  }

  async function loadTokenEconomy() {
    tokenLoading = true;
    try {
      const [supply, params, history] = await Promise.all([
        getTokenSupply(),
        getTokenParams(),
        getTokenParamHistory(),
      ]);
      tokenSupply = supply;
      tokenParams = params;
      tokenParamDraft = { ...params };
      tokenParamHistory = history.items ?? [];
    } catch (error) {
      showNotice(
        translateError(error, $translator, "tokens.loadFailed"),
        "error",
      );
    } finally {
      tokenLoading = false;
    }
  }

  async function loadMonetaryMetrics() {
    try {
      monetaryMetrics = await getMonetaryMetrics();
    } catch (error) {
      showNotice(
        translateError(error, $translator, "common.operationFailed"),
        "error",
      );
    }
  }

  async function saveTokenParams() {
    if (!tokenParams || tokenSaving) return;
    const updates: Partial<TokenParams> = {};
    for (const key of Object.keys(tokenParams) as Array<keyof TokenParams>) {
      const next = Number(tokenParamDraft[key]);
      if (!Number.isNaN(next) && next !== tokenParams[key]) {
        updates[key] = next;
      }
    }
    if (Object.keys(updates).length === 0) return;
    tokenSaving = true;
    try {
      const result = await updateTokenParams(updates);
      tokenParams = result.params;
      tokenParamDraft = { ...result.params };
      await loadTokenEconomy();
      showNotice($translator("tokens.admin.saveParams"));
    } catch (error) {
      showNotice(translateError(error, $translator, "common.operationFailed"), "error");
    } finally {
      tokenSaving = false;
    }
  }

  async function submitMint() {
    if (!mintRecipient.trim() || mintAmount <= 0 || minting) return;
    minting = true;
    try {
      await mintTokens(mintRecipient.trim(), mintAmount);
      mintAmount = 0;
      mintRecipient = "";
      await loadTokenEconomy();
      showNotice($translator("tokens.admin.mintSuccess"));
    } catch (error) {
      showNotice(translateError(error, $translator, "common.operationFailed"), "error");
    } finally {
      minting = false;
    }
  }

  function tabs(): Array<{ value: Tab; key: string }> {
    const shared: Array<{ value: Tab; key: string }> = [
      { value: "reports", key: "admin.tabs.reports" },
      { value: "moderation", key: "admin.tabs.moderation" },
      { value: "posts", key: "admin.tabs.posts" },
      { value: "patches", key: "admin.tabs.patches" },
    ];
    if (isSuperAdmin) {
      shared.push(
        { value: "ai", key: "admin.tabs.ai" },
        { value: "users", key: "admin.tabs.users" },
        { value: "guilds", key: "admin.tabs.guilds" },
        { value: "tokens", key: "tokens.admin.title" },
      );
    }
    return shared;
  }

  function aiSettingsPayload() {
    if (!aiSettings) return null;
    return {
      enabled: aiSettings.enabled,
      base_url: aiSettings.base_url,
      model: aiSettings.model,
      ...(aiApiKey.trim() ? { api_key: aiApiKey.trim() } : {}),
      moderation_provider_fallback_enabled:
        aiSettings.moderation_provider_fallback_enabled,
    };
  }

  async function testAIProviderSettings() {
    const payload = aiSettingsPayload();
    if (!payload || aiTesting || aiSaving) return;
    aiTesting = true;
    try {
      await testAISettings(payload);
      showNotice($translator("admin.ai.testPassed"));
    } catch (error) {
      showNotice(translateError(error, $translator, "admin.ai.testFailed"), "error");
    } finally {
      aiTesting = false;
    }
  }

  async function saveAISettings() {
    const payload = aiSettingsPayload();
    if (!payload || aiSaving || aiTesting) return;
    aiSaving = true;
    try {
      aiSettings = await updateAISettings(payload);
      aiApiKey = "";
      showNotice($translator("admin.ai.saved"));
    } catch (error) {
      showNotice(translateError(error, $translator, "admin.ai.saveFailed"), "error");
    } finally {
      aiSaving = false;
    }
  }

  async function resetAIProviderSettings() {
    if (aiSaving) return;
    aiSaving = true;
    try {
      await resetAISettings();
      aiSettings = await getAISettings();
      aiApiKey = "";
      showNotice($translator("admin.ai.resetDone"));
    } catch (error) {
      showNotice(translateError(error, $translator, "admin.ai.resetFailed"), "error");
    } finally {
      aiSaving = false;
    }
  }

  function formatDate(value: string | null | undefined) {
    if (!value) return "";
    return new Intl.DateTimeFormat($locale, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  }

  function roleLabel(role: string) {
    return $translator(`admin.role.${role}`);
  }

  function guildRoleLabel(role: string) {
    return $translator(`guild.role.${role}`);
  }

  function banLabel(type: string) {
    const option = banOptions.find((item) => item.value === type);
    return option ? $translator(option.key) : type;
  }

  function moderationTypeLabel(type: AdminModerationItem["content_type"]) {
    return $translator(`admin.moderationType.${type}`);
  }

  function moderationReasonLabel(reason: string | null) {
    if (reason === "political_or_uncertain") {
      return $translator("admin.moderationReason.politicalOrUncertain");
    }
    if (reason === "classifier_unavailable") {
      return $translator("admin.moderationReason.classifierUnavailable");
    }
    return $translator("admin.moderationReason.fallback");
  }

  async function loadModerationReviews() {
    moderationLoading = true;
    moderationError = false;
    try {
      moderationReviews = await listModerationReviews("pending_review");
    } catch {
      moderationReviews = [];
      moderationError = true;
    } finally {
      moderationLoading = false;
    }
  }

  function openModerationReview(
    item: AdminModerationItem,
    decision: "approve" | "reject",
  ) {
    moderationTarget = item;
    moderationDecision = decision;
    moderationNote = "";
    moderationModal = true;
  }

  async function submitModerationReview() {
    if (!moderationTarget || moderationSaving) return;
    if (moderationDecision === "reject" && !moderationNote.trim()) {
      showNotice($translator("admin.moderationRejectNoteRequired"), "error");
      return;
    }

    moderationSaving = true;
    try {
      await reviewModerationItem(
        moderationTarget.id,
        moderationDecision,
        moderationNote,
        moderationTarget.revision_number,
      );
      moderationReviews = moderationReviews.filter(
        (item) => item.id !== moderationTarget?.id,
      );
      showNotice(
        $translator(
          moderationDecision === "approve"
            ? "admin.moderationApproved"
            : "admin.moderationRejected",
        ),
      );
      moderationModal = false;
      moderationTarget = null;
    } catch (error) {
      if (
        (error as Error)?.message === "CONTENT_REVIEW_ALREADY_DECIDED"
        || (error as Error)?.message === "CONTENT_REVIEW_CONFLICT"
      ) {
        await loadModerationReviews();
      }
      showNotice(
        translateError(error, $translator, "admin.moderationReviewFailed"),
        "error",
      );
    } finally {
      moderationSaving = false;
    }
  }

  async function handleReport(reportId: string, action: string) {
    if (handlingReportId) return;
    const target = reports.find((report) => report.id === reportId);
    handlingReportId = reportId;
    try {
      await resolveReport(reportId, action);
      reports = reports.map((report) =>
        report.id === reportId || (
          target?.target_id != null
          && report.target_type === target.target_type
          && report.target_id === target.target_id
          && report.status === "pending"
        )
          ? { ...report, status: action === "dismissed" ? "dismissed" : "resolved" }
          : report
      );
      showNotice($translator("admin.reportHandled"));
    } catch (error) {
      showNotice(translateError(error, $translator, "common.operationFailed"), "error");
    } finally {
      handlingReportId = null;
    }
  }

  function openBan(userId: string, username: string, report?: ReportItem) {
    banUserId = userId;
    banUsername = username;
    banReportId = report?.id ?? "";
    banType = report
      ? report.target_type === "patch" ? "mute_patch" : "mute_post"
      : "ban_user";
    banDays = 0;
    banHours = 24;
    banReason = report?.reason ?? "";
    banModal = true;
  }

  async function submitBan() {
    banSaving = true;
    const duration = Math.max(0, banDays * 24 + banHours);
    try {
      await banUser(banUserId, duration, banType, banReason.trim());
      if (banReportId) await resolveReport(banReportId, "resolved");
      showNotice(
        duration === 0
          ? $translator("admin.banAppliedPermanent", { type: banLabel(banType) })
          : $translator("admin.banApplied", {
              type: banLabel(banType),
              hours: duration,
            }),
      );
      banModal = false;
      await refresh();
    } catch (error) {
      showNotice(translateError(error, $translator, "common.operationFailed"), "error");
    } finally {
      banSaving = false;
    }
  }

  async function openUnban(userId: string, username: string) {
    unbanUserId = userId;
    unbanUsername = username;
    try {
      unbanStatuses = await getBanStatus(userId);
      unbanModal = true;
    } catch (error) {
      showNotice(translateError(error, $translator, "common.operationFailed"), "error");
    }
  }

  async function removeBan(type?: string) {
    try {
      await unbanUser(unbanUserId, type);
      showNotice(
        type
          ? $translator("admin.unbanApplied", { type: banLabel(type) })
          : $translator("admin.unbanAllApplied"),
      );
      unbanModal = false;
    } catch (error) {
      showNotice(translateError(error, $translator, "common.operationFailed"), "error");
    }
  }

  function requestConfirmation(
    title: string,
    description: string,
    action: () => void,
    text = $translator("common.delete"),
  ) {
    confirmTitle = title;
    confirmDescription = description;
    confirmText = text;
    confirmAction = action;
    confirmOpen = true;
  }

  function openShortenModal(patch: AdminPatch) {
    shortenPatchId = patch.id;
    shortenPatchTitle = patch.title;
    shortenHours = null;
    shortenResult = null;
    shortenModal = true;
  }

  async function handleShortenVote() {
    shortenSubmitting = true;
    shortenResult = null;
    try {
      const result = await shortenPatchVote(shortenPatchId, shortenHours ?? undefined);
      shortenResult = result;
      // Refresh the patches list so the status updates
      patches = await listAdminPatches();
    } catch (error) {
      showNotice(translateError(error, $translator, "common.operationFailed"), "error");
    } finally {
      shortenSubmitting = false;
    }
  }

  async function deletePost(post: AdminPost) {
    try {
      await deletePostAdmin(post.id);
      posts = posts.filter((item) => item.id !== post.id);
      showNotice($translator("admin.deleted"));
    } catch (error) {
      showNotice(translateError(error, $translator, "common.operationFailed"), "error");
    }
  }

  async function deletePatch(patch: AdminPatch) {
    try {
      await deletePatchAdmin(patch.id);
      patches = patches.filter((item) => item.id !== patch.id);
      showNotice($translator("admin.deleted"));
    } catch (error) {
      showNotice(translateError(error, $translator, "common.operationFailed"), "error");
    }
  }

  async function updateRole(user: AdminUser, role: string) {
    if (!role || role === user.role) return;
    try {
      await setUserRole(user.id, role);
      users = users.map((item) => item.id === user.id ? { ...item, role } : item);
      showNotice($translator("admin.roleUpdated"));
    } catch (error) {
      showNotice(translateError(error, $translator, "common.operationFailed"), "error");
    }
  }

  async function toggleGuild(guild: Guild) {
    if (expandedGuild === guild.id) {
      expandedGuild = null;
      return;
    }
    expandedGuild = guild.id;
    guildMembers = [];
    guildDiscussions = [];
    const loadToken = ++guildLoadToken;
    guildDraft = {
      name: guild.name,
      logo: guild.logo ?? "",
      description: guild.description ?? "",
      level: guild.level,
    };
    guildLoading = true;
    try {
      const [nextMembers, nextDiscussions] = await Promise.all([
        listMembers(guild.id),
        listAdminGuildDiscussions(guild.id),
      ]);
      if (loadToken === guildLoadToken && expandedGuild === guild.id) {
        guildMembers = nextMembers;
        guildDiscussions = nextDiscussions;
      }
    } catch (error) {
      if (loadToken === guildLoadToken) {
        showNotice(translateError(error, $translator, "common.operationFailed"), "error");
      }
    } finally {
      if (loadToken === guildLoadToken) guildLoading = false;
    }
  }

  async function saveGuild(guild: Guild) {
    if (guildSaving) return;
    if (!guildDraft.name.trim()) {
      showNotice($translator("guild.nameRequired"), "error");
      return;
    }
    const guildId = guild.id;
    const draft = {
      name: guildDraft.name.trim(),
      logo: guildDraft.logo.trim(),
      description: guildDraft.description.trim(),
      level: guildDraft.level,
    };
    guildSaving = true;
    try {
      await adminUpdateGuild(guildId, draft);
      guilds = guilds.map((item) =>
        item.id === guildId
          ? {
              ...item,
              name: draft.name,
              logo: draft.logo || null,
              description: draft.description || null,
              level: draft.level,
            }
          : item
      );
      showNotice($translator("admin.guildUpdated"));
    } catch (error) {
      showNotice(translateError(error, $translator, "common.operationFailed"), "error");
    } finally {
      guildSaving = false;
    }
  }

  async function removeGuildMember(guildId: string, member: GuildMember) {
    try {
      await adminRemoveMember(guildId, member.user_id);
      guildMembers = guildMembers.filter((item) => item.user_id !== member.user_id);
      showNotice($translator("guild.memberRemoved"));
    } catch (error) {
      showNotice(translateError(error, $translator, "common.operationFailed"), "error");
    }
  }

  async function deleteGuildDiscussion(guildId: string, discussion: AdminGuildDiscussion) {
    try {
      await adminDeleteGuildDiscussion(guildId, discussion.id);
      guildDiscussions = guildDiscussions.filter((item) => item.id !== discussion.id);
      showNotice($translator("admin.deleted"));
    } catch (error) {
      showNotice(translateError(error, $translator, "common.operationFailed"), "error");
    }
  }

  async function deleteGuild(guild: Guild) {
    try {
      await adminDeleteGuild(guild.id);
      guilds = guilds.filter((item) => item.id !== guild.id);
      showNotice($translator("admin.deleted"));
    } catch (error) {
      showNotice(translateError(error, $translator, "common.operationFailed"), "error");
    }
  }
</script>

{#if loading}
  <div class="empty-state"><div class="spinner"></div></div>
{:else if !isAdmin}
  <div class="empty-state">
    <h1 class="text-lg font-semibold" style="color: var(--vercel-danger);">
      {$translator("admin.accessDenied")}
    </h1>
  </div>
{:else}
  <header class="admin-header">
    <div>
      <p class="admin-eyebrow">{$translator("admin.eyebrow")}</p>
      <h1>{$translator("admin.title")}</h1>
    </div>
    <span class="role-indicator">{roleLabel($currentUser?.role ?? "moderator")}</span>
  </header>

  {#if notice}
    <div class:notice-error={noticeKind === "error"} class="notice" role="status">
      {notice}
    </div>
  {/if}

  <nav class="admin-tabs" aria-label={$translator("admin.title")}>
    {#each tabs() as item (item.value)}
      <button
        class="filter-tab"
        class:active={tab === item.value}
        onclick={() => (tab = item.value)}
      >
        {$translator(item.key)}
        {#if item.value === "moderation" && moderationReviews.length > 0}
          <span class="tab-count">{moderationReviews.length}</span>
        {/if}
      </button>
    {/each}
  </nav>

  {#if tab === "reports"}
    <section aria-label={$translator("admin.tabs.reports")}>
      {#if reports.length === 0}
        <div class="empty-state">{$translator("admin.emptyReports")}</div>
      {:else}
        <div class="admin-list">
          {#each reports as report (report.id)}
            <article class:resolved={report.status !== "pending"} class="admin-row report-row">
              <div class="row-main">
                <div class="row-meta">
                  {$translator("admin.reportMeta", {
                    reporter: report.reporter_username || $translator("common.anonymous"),
                    author: report.content_author || $translator("admin.authorDeleted"),
                  })}
                  · {formatDate(report.created_at)}
                </div>
                <h2>
                  {#if report.target_id && report.target_type !== "deleted"}
                    <a
                      class="report-target-link"
                      href={report.target_href || (report.target_type === "patch"
                        ? `/patches/${report.target_id}`
                        : `/posts/${report.target_id}`)}
                    >
                      {report.content_title || $translator("admin.untitled")}
                      <Eye size={14} aria-hidden="true" />
                    </a>
                  {:else}
                    {report.target_deleted
                      ? $translator("admin.deleted")
                      : report.content_title || $translator("admin.untitled")}
                  {/if}
                </h2>
                <p class="report-reason">{report.reason}</p>
                {#if report.content_body}
                  <p class="content-excerpt">{report.content_body}</p>
                {/if}
              </div>
              <div class="row-actions">
                {#if report.status === "pending"}
                  <button class="btn btn-secondary btn-sm" onclick={() => handleReport(report.id, "dismissed")} disabled={handlingReportId !== null}>
                    {$translator("admin.dismiss")}
                  </button>
                  <button class="btn btn-secondary btn-sm" onclick={() => handleReport(report.id, "resolved")} disabled={handlingReportId !== null}>
                    <Check size={15} aria-hidden="true" />
                    {$translator("admin.resolved")}
                  </button>
                  {#if isSuperAdmin && report.target_type !== "deleted"}
                    <button
                      class="btn btn-danger btn-sm"
                      disabled={handlingReportId !== null}
                      onclick={() => requestConfirmation(
                        $translator("admin.deleteReportedTitle"),
                        $translator("admin.deleteReportedDescription"),
                        () => handleReport(report.id, report.target_type === "patch" ? "delete_patch" : "delete_post"),
                      )}
                    >
                      <Trash2 size={15} aria-hidden="true" />
                      {$translator("admin.deleteContent")}
                    </button>
                  {/if}
                  {#if isSuperAdmin && report.content_author_id}
                    <button class="btn btn-secondary btn-sm" onclick={() => openBan(report.content_author_id, report.content_author, report)} disabled={handlingReportId !== null}>
                      <Ban size={15} />
                      {$translator("admin.restrict")}
                    </button>
                  {/if}
                {:else}
                  <span class="status-text">{$translator("admin.resolved")}</span>
                {/if}
              </div>
            </article>
          {/each}
        </div>
      {/if}
    </section>

  {:else if tab === "moderation"}
    <section aria-label={$translator("admin.tabs.moderation")}>
      {#if moderationLoading}
        <div class="empty-state"><div class="spinner"></div></div>
      {:else if moderationError}
        <div class="inline-error" role="alert">
          <span>{$translator("admin.moderationLoadFailed")}</span>
          <button class="btn btn-ghost btn-xs" type="button" onclick={loadModerationReviews}>
            {$translator("common.retry")}
          </button>
        </div>
      {:else if moderationReviews.length === 0}
        <div class="empty-state">{$translator("admin.emptyModeration")}</div>
      {:else}
        <div class="admin-list">
          {#each moderationReviews as review (review.id)}
            <article class="admin-row moderation-row">
              <div class="row-main">
                <div class="row-meta">
                  {$translator("admin.moderationMeta", {
                    type: moderationTypeLabel(review.content_type),
                    author: review.author_username || $translator("common.anonymous"),
                  })}
                  · {formatDate(review.created_at)}
                </div>
                <h2>
                  <a class="report-target-link" href={review.target_href} target="_blank" rel="noreferrer">
                    {review.title || $translator("admin.untitled")}
                    <Eye size={14} aria-hidden="true" />
                  </a>
                </h2>
                <p class="content-excerpt">{review.content}</p>
                {#if review.poll_question}
                  <div class="moderation-poll">
                    <strong>{$translator("poll.label")}: {review.poll_question}</strong>
                    <ul>
                      {#each review.poll_options as option}
                        <li>{option}</li>
                      {/each}
                    </ul>
                  </div>
                {/if}
                <p class="moderation-reason">
                  <ShieldAlert size={14} strokeWidth={1.8} aria-hidden="true" />
                  {moderationReasonLabel(review.moderation_reason)}
                </p>
              </div>
              <div class="row-actions">
                <button
                  class="btn btn-secondary btn-sm"
                  disabled={moderationSaving}
                  onclick={() => openModerationReview(review, "approve")}
                >
                  <Check size={15} aria-hidden="true" />
                  {$translator("admin.moderationApprove")}
                </button>
                <button
                  class="btn btn-danger-ghost btn-sm"
                  disabled={moderationSaving}
                  onclick={() => openModerationReview(review, "reject")}
                >
                  <X size={15} aria-hidden="true" />
                  {$translator("admin.moderationReject")}
                </button>
              </div>
            </article>
          {/each}
        </div>
      {/if}
    </section>

  {:else if tab === "posts" || tab === "patches"}
    {@const items = tab === "posts" ? posts : patches}
    <section aria-label={$translator(tab === "posts" ? "admin.tabs.posts" : "admin.tabs.patches")}>
      {#if items.length === 0}
        <div class="empty-state">
          {$translator(tab === "posts" ? "admin.emptyPosts" : "admin.emptyPatches")}
        </div>
      {:else}
        <div class="admin-list">
          {#each items as item (item.id)}
            <article class="admin-row">
              <div class="row-main">
                <h2>{item.title || $translator("admin.untitled")}</h2>
                <div class="row-meta">
                  {item.author_username} · {formatDate(item.created_at)}
                  {#if "pr_number" in item} · #{item.pr_number} · {item.status}{/if}
                </div>
              </div>
              <div class="row-actions">
                {#if tab === "patches" && (item as AdminPatch).status === "voting"}
                  {#if isSuperAdmin}
                    <button
                      class="btn btn-warning btn-sm"
                      onclick={() => openShortenModal(item as AdminPatch)}
                    >
                      {$translator("admin.shortenVote")}
                    </button>
                  {/if}
                {/if}
                <a
                  href={tab === "posts" ? `/posts/${item.id}` : `/patches/${item.id}`}
                  target="_blank"
                  rel="noreferrer"
                  class="btn btn-secondary btn-sm"
                >
                  <Eye size={15} />
                  {$translator("admin.view")}
                </a>
                {#if isSuperAdmin}
                  <button
                    class="btn btn-danger btn-sm"
                    onclick={() => requestConfirmation(
                      $translator("admin.deleteTitle"),
                      $translator("admin.deleteDescription", {
                        title: item.title || $translator("admin.untitled"),
                      }),
                      () => tab === "posts"
                        ? deletePost(item as AdminPost)
                        : deletePatch(item as AdminPatch),
                    )}
                  >
                    <Trash2 size={15} />
                    {$translator("common.delete")}
                  </button>
                {/if}
              </div>
            </article>
          {/each}
        </div>
      {/if}
    </section>

  {:else if tab === "ai"}
    <section class="settings-panel" aria-label={$translator("admin.tabs.ai")}>
      {#if aiSettings}
        <div class="settings-heading">
          <div>
            <p class="admin-eyebrow">{$translator("admin.ai.eyebrow")}</p>
            <h2><Bot size={19} /> {$translator("admin.ai.title")}</h2>
          </div>
          <span class="source-badge">
            {$translator(aiSettings.source === "database" ? "admin.ai.sourceDatabase" : "admin.ai.sourceEnvironment")}
          </span>
        </div>

        <p class="settings-description">{$translator("admin.ai.description")}</p>

        <label class="toggle-row">
          <span>
            <strong>{$translator("admin.ai.enabled")}</strong>
            <small>{$translator("admin.ai.enabledDescription")}</small>
          </span>
          <input type="checkbox" bind:checked={aiSettings.enabled} />
        </label>

        <div class="settings-grid">
          <label>
            <span>{$translator("admin.ai.baseUrl")}</span>
            <input class="input" type="url" bind:value={aiSettings.base_url} placeholder="https://provider.example/v1" />
          </label>
          <label>
            <span>{$translator("admin.ai.model")}</span>
            <input class="input" bind:value={aiSettings.model} placeholder="model-name" />
          </label>
          <label class="settings-wide">
            <span>{$translator("admin.ai.apiKey")}</span>
            <input
              class="input"
              type="password"
              bind:value={aiApiKey}
              autocomplete="new-password"
              placeholder={aiSettings.api_key_configured
                ? $translator("admin.ai.apiKeyConfigured")
                : $translator("admin.ai.apiKeyPlaceholder")}
            />
            <small>{$translator("admin.ai.apiKeyDescription")}</small>
          </label>
        </div>

        <label class="toggle-row">
          <span>
            <strong>{$translator("admin.ai.moderationFallback")}</strong>
            <small>{$translator("admin.ai.moderationFallbackDescription")}</small>
          </span>
          <input type="checkbox" bind:checked={aiSettings.moderation_provider_fallback_enabled} />
        </label>

        <div class:configured={aiSettings.trusted_classifier_configured} class="classifier-status">
          {$translator(aiSettings.trusted_classifier_configured
            ? "admin.ai.classifierConfigured"
            : "admin.ai.classifierMissing")}
        </div>

        <div class="settings-actions">
          <button class="btn btn-secondary" onclick={resetAIProviderSettings} disabled={aiSaving}>
            <RotateCcw size={15} /> {$translator("admin.ai.useEnvironment")}
          </button>
          <button class="btn btn-secondary" onclick={testAIProviderSettings} disabled={aiSaving || aiTesting}>
            {$translator(aiTesting ? "common.processing" : "admin.ai.testConnection")}
          </button>
          <button class="btn btn-primary" onclick={saveAISettings} disabled={aiSaving || aiTesting}>
            {$translator(aiSaving ? "common.processing" : "common.save")}
          </button>
        </div>
      {:else}
        <div class="empty-state"><div class="spinner"></div></div>
      {/if}
    </section>

  {:else if tab === "users"}
    <section class="admin-list" aria-label={$translator("admin.tabs.users")}>
      {#each users as user (user.id)}
        <article class="admin-row user-row">
          <div class="row-main">
            <h2>{user.nickname || user.username}</h2>
            <div class="row-meta">@{user.username} · {user.email}</div>
          </div>
          <div class="row-actions">
            <label class="sr-only" for="role-{user.id}">{$translator("admin.permission")}</label>
            <select
              id="role-{user.id}"
              class="role-select"
              value={user.role}
              onchange={(event) => updateRole(user, (event.target as HTMLSelectElement).value)}
            >
              <option value="super_admin">{$translator("admin.role.super_admin")}</option>
              <option value="moderator">{$translator("admin.role.moderator")}</option>
              <option value="user">{$translator("admin.role.user")}</option>
            </select>
            <button class="btn btn-secondary btn-sm" onclick={() => openBan(user.id, user.username)}>
              <Ban size={15} />
              {$translator("admin.restrict")}
            </button>
            <button class="btn btn-secondary btn-sm" onclick={() => openUnban(user.id, user.username)}>
              <UnlockKeyhole size={15} />
              {$translator("admin.unban")}
            </button>
          </div>
        </article>
      {/each}
    </section>

  {:else if tab === "guilds"}
    <section class="admin-list" aria-label={$translator("admin.tabs.guilds")}>
      {#each guilds as guild (guild.id)}
        <article class="guild-admin-row">
          <div class="admin-row">
            <div class="row-main">
              <h2>{guild.name}</h2>
              <div class="row-meta">
                Lv.{guild.level} · {$translator("guild.membersCount", { count: guild.member_count })}
                · {$translator("guild.presidentName", { name: guild.president_username })}
              </div>
            </div>
            <div class="row-actions">
              <button class="btn btn-secondary btn-sm" onclick={() => toggleGuild(guild)}>
                {#if expandedGuild === guild.id}<ChevronUp size={15} />{:else}<ChevronDown size={15} />{/if}
                {$translator("common.edit")}
              </button>
              <button
                class="btn btn-danger btn-sm"
                onclick={() => requestConfirmation(
                  $translator("admin.deleteGuildTitle"),
                  $translator("admin.deleteDescription", { title: guild.name }),
                  () => deleteGuild(guild),
                )}
              >
                <Trash2 size={15} />
                {$translator("common.delete")}
              </button>
            </div>
          </div>

          {#if expandedGuild === guild.id}
            <div class="guild-editor">
              {#if guildLoading}
                <div class="empty-state"><div class="spinner"></div></div>
              {:else}
                <div class="guild-fields">
                  <label>
                    <span>{$translator("guild.name")}</span>
                    <input class="input" bind:value={guildDraft.name} maxlength="80" />
                  </label>
                  <label>
                    <span>{$translator("guild.logo")}</span>
                    <input class="input" bind:value={guildDraft.logo} maxlength="500" />
                  </label>
                  <label>
                    <span>{$translator("admin.guildLevel")}</span>
                    <input class="input" type="number" min="1" max="5" bind:value={guildDraft.level} />
                  </label>
                  <label class="description-field">
                    <span>{$translator("guild.description")}</span>
                    <textarea class="input" rows="3" bind:value={guildDraft.description} maxlength="2000"></textarea>
                  </label>
                </div>
                <button class="btn btn-primary btn-sm" onclick={() => saveGuild(guild)} disabled={guildSaving}>
                  {$translator("common.save")}
                </button>

                <div class="subsection">
                  <h3>{$translator("guild.tabs.members")} ({guildMembers.length})</h3>
                  {#each guildMembers as member (member.id)}
                    <div class="compact-row">
                      <span>{member.nickname || member.username} · {guildRoleLabel(member.role)}</span>
                      {#if member.role !== "president"}
                        <button
                          class="btn-icon"
                          title={$translator("guild.remove")}
                          aria-label={$translator("guild.remove")}
                          onclick={() => requestConfirmation(
                            $translator("guild.removeMemberTitle"),
                            $translator("guild.removeMemberDescription", {
                              name: member.nickname || member.username,
                            }),
                            () => removeGuildMember(guild.id, member),
                          )}
                        ><Trash2 size={15} /></button>
                      {/if}
                    </div>
                  {/each}
                </div>

                <div class="subsection">
                  <h3>{$translator("guild.tabs.discussions")} ({guildDiscussions.length})</h3>
                  {#if guildDiscussions.length === 0}
                    <p class="row-meta">{$translator("guild.noDiscussions")}</p>
                  {:else}
                    {#each guildDiscussions as discussion (discussion.id)}
                      <div class="compact-row">
                        <span>{discussion.title || $translator("admin.untitled")}</span>
                        <button
                          class="btn-icon"
                          title={$translator("common.delete")}
                          aria-label={$translator("common.delete")}
                          onclick={() => requestConfirmation(
                            $translator("guild.deleteDiscussionTitle"),
                            $translator("guild.deleteDiscussionDescription"),
                            () => deleteGuildDiscussion(guild.id, discussion),
                          )}
                        ><Trash2 size={15} /></button>
                      </div>
                    {/each}
                  {/if}
                </div>
              {/if}
            </div>
          {/if}
        </article>
      {/each}
    </section>

  {:else if tab === "tokens"}
    <section class="token-economy" aria-label={$translator("tokens.admin.title")}>
      {#if tokenLoading}
        <div class="empty-state"><div class="spinner"></div></div>
      {:else}
        <div class="token-section">
          <h3 class="token-section-title"><Coins size={16} aria-hidden="true" /> {$translator("tokens.admin.supply")}</h3>
          {#if tokenSupply}
            <div class="supply-grid">
              <div class="stat-card">
                <span class="stat-label">{$translator("tokens.admin.circulating")}</span>
                <span class="stat-value">{tokenSupply.circulating_supply.toLocaleString()}</span>
              </div>
              <div class="stat-card">
                <span class="stat-label">{$translator("tokens.admin.totalIssued")}</span>
                <span class="stat-value">{tokenSupply.total_issued.toLocaleString()}</span>
              </div>
              <div class="stat-card">
                <span class="stat-label">{$translator("tokens.admin.totalBurned")}</span>
                <span class="stat-value">{tokenSupply.total_burned.toLocaleString()}</span>
              </div>
            </div>
          {:else}
            <p class="row-meta">{$translator("common.loading")}</p>
          {/if}
        </div>

        <div class="token-section">
          <h3 class="token-section-title">{$translator("tokens.admin.monetaryTitle")}</h3>
          <TokenMonetaryPanel onAdjusted={loadMonetaryMetrics} />
        </div>

        <div class="token-section">
          <h3 class="token-section-title">{$translator("tokens.admin.supplyTrend")}</h3>
          <TokenSupplyChart title={$translator("tokens.admin.supplyTrend")} />
        </div>

        <div class="token-section">
          <h3 class="token-section-title">{$translator("tokens.admin.params")}</h3>
          {#if tokenParams}
            <div class="param-grid">
              {#each tokenParamOrder as key (key)}
                <label>
                  <span>{$translator(`tokens.admin.param.${key}`)}</span>
                  <input class="input" type="number" min="0" bind:value={tokenParamDraft[key]} />
                  <span class="param-desc-note">{$translator(`tokens.admin.param.${key}_desc`)}</span>
                </label>
              {/each}
            </div>
            <div class="token-actions">
              <button class="btn btn-primary btn-sm" onclick={saveTokenParams} disabled={tokenSaving}>
                {$translator(tokenSaving ? "common.saving" : "tokens.admin.saveParams")}
              </button>
            </div>
          {:else}
            <p class="row-meta">{$translator("common.loading")}</p>
          {/if}
        </div>

        <div class="token-section">
          <h3 class="token-section-title">{$translator("tokens.admin.mint")}</h3>
          <div class="mint-grid">
            <label>
              <span>{$translator("tokens.admin.mintRecipient")}</span>
              <input
                class="input"
                type="email"
                placeholder={$translator("tokens.admin.mintRecipientPlaceholder")}
                bind:value={mintRecipient}
              />
            </label>
            <label>
              <span>{$translator("tokens.admin.mintAmount")}</span>
              <input class="input" type="number" min="1" bind:value={mintAmount} />
            </label>
          </div>
          <div class="token-actions">
            <button
              class="btn btn-primary btn-sm"
              onclick={submitMint}
              disabled={minting || !mintRecipient.trim() || mintAmount <= 0}
            >
              {$translator(minting ? "common.saving" : "tokens.admin.mint")}
            </button>
          </div>
        </div>

        <div class="token-section">
          <h3 class="token-section-title">{$translator("tokens.admin.history")}</h3>
          {#if tokenParamHistory.length === 0}
            <p class="row-meta">{$translator("tokens.admin.historyEmpty")}</p>
          {:else}
            <ul class="param-history">
              {#each tokenParamHistory as item (item.changed_at + item.key)}
                <li class="param-history-row">
                  <span class="param-history-key">{$translator(`tokens.admin.param.${item.key}`)}</span>
                  <span class="param-history-change">{item.old_value} → {item.new_value}</span>
                  <span class="param-history-meta">
                    {item.changed_by ?? $translator("common.anonymous")} · {formatDate(item.changed_at)}
                  </span>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      {/if}
    </section>
  {/if}
{/if}

<GlassModal
  show={moderationModal}
  title={$translator(
    moderationDecision === "approve"
      ? "admin.moderationApproveTitle"
      : "admin.moderationRejectTitle",
  )}
  onclose={() => (moderationModal = false)}
>
  <div class="modal-stack">
    {#if moderationTarget}
      <p class="moderation-modal-context">
        {moderationTarget.title || moderationTypeLabel(moderationTarget.content_type)}
      </p>
    {/if}
    <label>
      <span class="field-label">{$translator("admin.moderationNote")}</span>
      <textarea
        class="input"
        rows="4"
        maxlength="500"
        bind:value={moderationNote}
        placeholder={$translator("admin.moderationNotePlaceholder")}
      ></textarea>
      <span class="field-note">{$translator("admin.moderationNoteHelp")}</span>
    </label>
    {#if moderationDecision === "reject" && !moderationNote.trim()}
      <p class="validation-note">{$translator("admin.moderationRejectNoteRequired")}</p>
    {/if}
    <div class="modal-actions">
      <button class="btn btn-ghost btn-sm" onclick={() => (moderationModal = false)}>
        {$translator("common.cancel")}
      </button>
      <button
        class={moderationDecision === "approve" ? "btn btn-primary btn-sm" : "btn btn-danger btn-sm"}
        disabled={moderationSaving || (moderationDecision === "reject" && !moderationNote.trim())}
        onclick={submitModerationReview}
      >
        {$translator(
          moderationSaving
            ? "admin.moderationReviewing"
            : moderationDecision === "approve"
              ? "admin.moderationApprove"
              : "admin.moderationReject",
        )}
      </button>
    </div>
  </div>
</GlassModal>

<GlassModal
  show={banModal}
  title={$translator("admin.banTitle", { name: banUsername })}
  onclose={() => (banModal = false)}
>
  <div class="modal-stack">
    <fieldset>
      <legend>{$translator("admin.banType")}</legend>
      <div class="segmented-control">
        {#each banOptions as option (option.value)}
          <button
            class:active={banType === option.value}
            onclick={() => (banType = option.value)}
          >{$translator(option.key)}</button>
        {/each}
      </div>
    </fieldset>

    <fieldset>
      <legend>{$translator("admin.duration")}</legend>
      <div class="duration-grid">
        <label>
          <span>{$translator("admin.days")}</span>
          <input class="input" type="number" min="0" max="3650" bind:value={banDays} />
        </label>
        <label>
          <span>{$translator("admin.hours")}</span>
          <input class="input" type="number" min="0" max="23" bind:value={banHours} />
        </label>
      </div>
      <p class="field-note">
        {banDays === 0 && banHours === 0
          ? $translator("admin.permanent")
          : $translator("admin.totalHours", { hours: banDays * 24 + banHours })}
      </p>
    </fieldset>

    <label>
      <span class="field-label">{$translator("admin.reason")}</span>
      <textarea class="input" rows="3" bind:value={banReason} maxlength="500"></textarea>
    </label>

    <div class="modal-actions">
      <button class="btn btn-ghost btn-sm" onclick={() => (banModal = false)}>
        {$translator("common.cancel")}
      </button>
      <button class="btn btn-danger btn-sm" onclick={submitBan} disabled={banSaving}>
        {$translator(banSaving ? "common.saving" : "common.confirm")}
      </button>
    </div>
  </div>
</GlassModal>

	<!-- Shorten vote modal -->
	<GlassModal
	  show={shortenModal}
	  title={$translator("admin.shortenVote")}
	  onclose={() => (shortenModal = false)}
	>
	  <div class="shorten-modal">
	    <p class="shorten-patch-title">{shortenPatchTitle}</p>

	    {#if shortenResult}
	      <div class="shorten-result">
	        {#if shortenResult.action === "shortened"}
	          <p>{$translator("admin.voteShortened", { hours: String(shortenHours ?? 0) })}</p>
	        {:else}
	          <p>{$translator("admin.voteEnded", { outcome: shortenResult.outcome ?? "" })}</p>
	        {/if}
	      </div>
	      <div class="shorten-actions">
	        <button class="btn btn-primary btn-sm" onclick={() => (shortenModal = false)}>
	          {$translator("common.close")}
	        </button>
	      </div>
	    {:else}
	      <div class="shorten-form">
	        <label class="shorten-label">
	          {$translator("admin.shortenVoteModal")}
	          <input
	            class="input"
	            type="number"
	            min="1"
	            max="168"
	            placeholder="{$translator("admin.shortenVoteModal")}"
	            bind:value={shortenHours}
	          />
	        </label>
	        <p class="field-note">{$translator("common.optional")}</p>
	      </div>
	      <div class="shorten-actions">
<button
          class="btn btn-primary btn-sm"
          onclick={() => { shortenHours = null; handleShortenVote(); }}
          disabled={shortenSubmitting}
        >
          {$translator("admin.endVoteNow")}
        </button>
	        <button
	          class="btn btn-warning btn-sm"
	          onclick={handleShortenVote}
	          disabled={shortenSubmitting || !shortenHours}
	        >
	          {shortenSubmitting ? $translator("common.processing") : $translator("admin.shortenVote")}
	        </button>
	      </div>
	    {/if}
	  </div>
	</GlassModal>

	<GlassModal
	  show={unbanModal}
	  title={$translator("admin.unbanTitle", { name: unbanUsername })}
	  onclose={() => (unbanModal = false)}
	>
  {#if unbanStatuses.length === 0}
    <p>{$translator("admin.noRestrictions")}</p>
  {:else}
    <div class="restriction-list">
      {#each unbanStatuses as status (status.id)}
        <div class="restriction-row">
          <div>
            <strong>{banLabel(status.type)}</strong>
            <p class="field-note">
              {status.expires_at
                ? $translator("admin.expiresAt", { date: formatDate(status.expires_at) })
                : $translator("admin.permanent")}
            </p>
            {#if status.reason}<p class="field-note">{status.reason}</p>{/if}
          </div>
          <button class="btn btn-secondary btn-sm" onclick={() => removeBan(status.type)}>
            {$translator("admin.removeRestriction")}
          </button>
        </div>
      {/each}
      <button class="btn btn-primary btn-sm" onclick={() => removeBan()}>
        {$translator("admin.removeAllRestrictions")}
      </button>
    </div>
  {/if}
</GlassModal>

<ConfirmDialog
  bind:open={confirmOpen}
  title={confirmTitle}
  description={confirmDescription}
  confirmText={confirmText}
  onConfirm={confirmAction}
/>

<style>
  .admin-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--vercel-border);
  }

  .admin-header h1 {
    margin: 0;
    font-size: 1.35rem;
    line-height: 1.25;
  }

  .admin-eyebrow,
  .row-meta,
  .field-note,
  .field-label,
  fieldset legend,
  .guild-fields label > span,
  .duration-grid label > span {
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
  }

  .role-indicator {
    color: var(--vercel-text-secondary);
    font-size: 0.75rem;
  }

  .notice {
    margin-top: 1rem;
    padding: 0.75rem 1rem;
    color: var(--vercel-success);
    background: var(--vercel-success-bg);
    border-left: 3px solid var(--vercel-success);
    font-size: 0.8125rem;
  }

  .notice-error {
    color: var(--vercel-danger);
    background: color-mix(in srgb, var(--vercel-danger) 9%, transparent);
    border-left-color: var(--vercel-danger);
  }

  .settings-panel {
    display: grid;
    gap: 1rem;
    padding: 1.25rem;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius-lg);
    background: var(--vercel-card);
  }

  .settings-heading,
  .settings-actions,
  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .settings-heading h2 {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: var(--vercel-text);
    font-size: 1.05rem;
  }

  .source-badge,
  .classifier-status {
    width: fit-content;
    padding: 0.35rem 0.55rem;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius-sm);
    color: var(--vercel-text-tertiary);
    background: var(--vercel-surface-muted);
    font-size: 0.72rem;
    font-weight: 650;
  }

  .classifier-status.configured {
    color: var(--vercel-success);
    border-color: color-mix(in srgb, var(--vercel-success) 35%, var(--vercel-border));
  }

  .settings-description,
  .toggle-row small,
  .settings-grid small {
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
    line-height: 1.5;
  }

  .settings-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.9rem;
  }

  .settings-grid label {
    display: grid;
    gap: 0.4rem;
    color: var(--vercel-text-secondary);
    font-size: 0.78rem;
    font-weight: 600;
  }

  .settings-wide { grid-column: 1 / -1; }

  .toggle-row {
    padding: 0.85rem;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius-sm);
  }

  .toggle-row span { display: grid; gap: 0.2rem; }
  .toggle-row strong { color: var(--vercel-text); font-size: 0.82rem; }
  .toggle-row input { width: 1.1rem; height: 1.1rem; accent-color: var(--vercel-accent); }
  .settings-actions { justify-content: flex-end; }

  @media (max-width: 40rem) {
    .settings-grid { grid-template-columns: 1fr; }
    .settings-wide { grid-column: auto; }
    .settings-heading { align-items: flex-start; flex-direction: column; }
  }

  .admin-tabs {
    display: flex;
    gap: 0.25rem;
    margin: 1rem 0;
    overflow-x: auto;
    border-bottom: 1px solid var(--vercel-border);
  }

  .admin-tabs :global(.filter-tab) {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    white-space: nowrap;
  }

  .tab-count {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.25rem;
    height: 1.25rem;
    padding: 0 0.3rem;
    color: var(--vercel-warning);
    background: var(--vercel-warning-bg);
    border-radius: var(--vercel-radius-sm);
    font-size: 0.6875rem;
    font-variant-numeric: tabular-nums;
  }

  .admin-list {
    display: grid;
    border-top: 1px solid var(--vercel-border);
  }

  .admin-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 1rem;
    padding: 1rem 0;
    border-bottom: 1px solid var(--vercel-border);
  }

  .admin-row h2,
  .subsection h3 {
    margin: 0;
    font-size: 0.875rem;
    line-height: 1.4;
  }

  .row-main {
    min-width: 0;
  }

  .row-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .report-row {
    align-items: start;
  }

  .moderation-row {
    align-items: start;
  }

  .moderation-reason {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    margin: 0.55rem 0 0;
    color: var(--vercel-warning);
    font-size: 0.75rem;
  }

  .moderation-poll {
    max-width: 65ch;
    margin-top: 0.55rem;
    padding-left: 0.75rem;
    border-left: 2px solid var(--vercel-border-hover);
    color: var(--vercel-text-secondary);
    font-size: 0.75rem;
    line-height: 1.5;
  }

  .moderation-poll strong {
    color: var(--vercel-text);
    font-weight: 650;
  }

  .moderation-poll ul {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 0.9rem;
    margin: 0.25rem 0 0;
    padding-left: 1rem;
  }

  .moderation-modal-context {
    margin: 0;
    color: var(--vercel-text-secondary);
    font-size: 0.8125rem;
    line-height: 1.5;
  }

  .validation-note {
    margin: -0.5rem 0 0;
    color: var(--vercel-danger);
    font-size: 0.75rem;
  }

  .inline-error {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    color: var(--vercel-danger);
    background: var(--vercel-danger-bg);
    border-left: 3px solid var(--vercel-danger);
    font-size: 0.8125rem;
  }

  .resolved {
    opacity: 0.62;
  }

  .report-reason {
    margin: 0.45rem 0 0;
    color: var(--vercel-text);
    font-size: 0.875rem;
  }

  .report-target-link {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    max-width: 100%;
    color: var(--vercel-text);
  }

  .report-target-link:hover {
    color: var(--vercel-accent);
    text-decoration: underline;
    text-underline-offset: 0.18em;
  }

  .content-excerpt {
    display: -webkit-box;
    max-width: 65ch;
    overflow: hidden;
    margin: 0.35rem 0 0;
    color: var(--vercel-text-secondary);
    font-size: 0.8125rem;
    line-height: 1.5;
    overflow-wrap: anywhere;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
  }

  .status-text {
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
  }

  .role-select {
    min-height: 2rem;
    padding: 0 0.5rem;
    color: var(--vercel-text);
    background: var(--vercel-surface);
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius-sm);
    font: inherit;
    font-size: 0.75rem;
  }

  .guild-admin-row {
    border-bottom: 1px solid var(--vercel-border);
  }

  .guild-admin-row > .admin-row {
    border-bottom: 0;
  }

  .guild-editor {
    padding: 1rem 0 1.5rem;
    border-top: 1px solid var(--vercel-border);
  }

  .guild-fields {
    display: grid;
    grid-template-columns: minmax(9rem, 1fr) minmax(8rem, 1fr) 6rem;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .guild-fields label,
  .duration-grid label {
    display: grid;
    gap: 0.35rem;
  }

  .description-field {
    grid-column: 1 / -1;
  }

  .subsection {
    margin-top: 1.5rem;
  }

  .subsection h3 {
    margin-bottom: 0.5rem;
    color: var(--vercel-text-secondary);
  }

  .compact-row,
  .restriction-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    min-height: 2.5rem;
    padding: 0.375rem 0;
    border-top: 1px solid var(--vercel-border);
    color: var(--vercel-text-secondary);
    font-size: 0.8125rem;
  }

  .modal-stack,
  .restriction-list {
    display: grid;
    gap: 1rem;
  }

  fieldset {
    min-width: 0;
    margin: 0;
    padding: 0;
    border: 0;
  }

  fieldset legend {
    margin-bottom: 0.4rem;
  }

  .segmented-control {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    padding: 0.2rem;
    background: var(--vercel-surface);
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius-sm);
  }

  .segmented-control button {
    min-height: 2.25rem;
    padding: 0.35rem;
    color: var(--vercel-text-secondary);
    background: transparent;
    border: 0;
    border-radius: calc(var(--vercel-radius-sm) - 2px);
    cursor: pointer;
    font: inherit;
    font-size: 0.75rem;
  }

  .segmented-control button.active {
    color: var(--vercel-text);
    background: var(--vercel-hover-strong);
  }

  .duration-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
  }

  .restriction-row strong {
    color: var(--vercel-text);
    font-size: 0.8125rem;
  }

  .token-economy {
    display: grid;
    gap: 1.5rem;
  }

  .token-section {
    padding: 1rem;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius);
    background: var(--vercel-surface);
  }

  .token-section-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0 0 0.75rem;
    font-size: 0.875rem;
    color: var(--vercel-text);
  }

  .supply-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
  }

  .stat-card {
    display: grid;
    gap: 0.25rem;
    padding: 0.75rem;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius-sm);
    background: var(--vercel-background);
  }

  .stat-label {
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
  }

  .stat-value {
    color: var(--vercel-text);
    font-size: 1.125rem;
    font-weight: 600;
  }

  .param-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .param-grid label,
  .mint-grid label {
    display: grid;
    gap: 0.35rem;
  }

  .param-grid label > span,
  .mint-grid label > span {
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
  }

  .param-desc-note {
    color: var(--vercel-text-tertiary);
    font-size: 0.65rem;
    line-height: 1.3;
    opacity: 0.75;
  }

  .mint-grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .token-actions {
    display: flex;
    justify-content: flex-end;
  }

  .param-history {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .param-history-row {
    display: grid;
    gap: 0.15rem;
    padding: 0.625rem 0;
    border-top: 1px solid var(--vercel-border);
    font-size: 0.8125rem;
  }

  .param-history-row:first-child {
    border-top: 0;
    padding-top: 0;
  }

  .param-history-key {
    color: var(--vercel-text-secondary);
  }

  .param-history-change {
    color: var(--vercel-text);
    font-variant-numeric: tabular-nums;
  }

  .param-history-meta {
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
  }

  @media (max-width: 42rem) {
    .admin-row {
      grid-template-columns: 1fr;
    }

    .row-actions {
      justify-content: flex-start;
    }

    .guild-fields {
      grid-template-columns: 1fr 1fr;
    }

    .description-field {
      grid-column: 1 / -1;
    }

    .supply-grid,
    .param-grid {
      grid-template-columns: 1fr 1fr;
    }
  }

  @media (max-width: 28rem) {
    .admin-header {
      align-items: flex-start;
      flex-direction: column;
    }

    .guild-fields,
    .segmented-control {
      grid-template-columns: 1fr;
    }

    .description-field {
      grid-column: auto;
    }

    .supply-grid,
    .param-grid,
    .mint-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
