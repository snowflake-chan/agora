import type { ModerationStatus } from "./moderation";

const API = "/api/v1/admin";

async function req(path: string, options?: RequestInit) {
  const res = await fetch(`${API}${path}`, { credentials: "include", ...options });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  if (res.status === 204) return null;
  return res.json();
}

export interface ReportItem {
  id: string;
  target_type: "content" | "patch" | "deleted";
  target_id: string | null;
  target_href?: string | null;
  target_deleted?: boolean;
  content_id: string | null;
  patch_id: string | null;
  content_title: string;
  content_body: string;
  content_author: string;
  content_author_deleted?: boolean;
  content_author_id: string | null;
  patch_title?: string | null;
  reporter_username: string;
  reason: string;
  status: string;
  created_at: string;
  report_count?: number;
}

export interface AdminUser {
  id: string; username: string; email: string; nickname: string | null;
  is_active: boolean; role: string; created_at: string;
}

export interface AdminPost {
  id: string;
  title: string | null;
  content: string;
  author_username: string;
  author_id: string;
  created_at: string;
}

export interface AdminPatch {
  id: string;
  title: string;
  pr_number: number;
  status: string;
  author_username: string;
  author_id: string;
  created_at: string;
}

export interface AdminGuildDiscussion {
  id: string;
  title: string | null;
  content: string;
  author_username: string;
  created_at: string;
}

export type ModerationContentType = "post" | "comment" | "guild_post";

export interface AdminModerationItem {
  id: string;
  content_type: ModerationContentType;
  title: string | null;
  content: string;
  revision_number: number;
  author_id: string;
  author_username: string | null;
  moderation_status: ModerationStatus;
  moderation_reason: string | null;
  moderation_review_note: string | null;
  moderation_reviewed_by: string | null;
  moderation_reviewed_at: string | null;
  created_at: string;
  target_href: string;
  poll_question: string | null;
  poll_options: string[];
}

export async function setUserRole(userId: string, role: string) {
  return req(`/users/${userId}/role?role=${role}`, { method: "POST" });
}

export async function seedSuperAdmin() {
  return req("/seed-super-admin", { method: "POST" });
}

// Reports
export type ReportTargetType = "content" | "patch";

export async function createReport(
  targetId: string,
  reason: string,
  targetType: ReportTargetType = "content",
) {
  return req("/reports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      reason,
      [targetType === "patch" ? "patch_id" : "content_id"]: targetId,
    }),
  });
}

export async function listReports(status?: string): Promise<ReportItem[]> {
  const qs = status ? `?status=${status}` : "";
  return req(`/reports${qs}`);
}

export async function listModerationReviews(
  status: ModerationStatus = "pending_review",
): Promise<AdminModerationItem[]> {
  const params = new URLSearchParams({ status });
  return req(`/moderation?${params}`);
}

export async function reviewModerationItem(
  contentId: string,
  decision: "approve" | "reject",
  note: string,
  revisionNumber: number,
): Promise<AdminModerationItem> {
  return req(`/moderation/${contentId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      decision,
      note: note.trim() || null,
      revision_number: revisionNumber,
    }),
  });
}

export async function listAdminPosts(): Promise<AdminPost[]> {
  return req("/posts");
}

export async function listAdminPatches(): Promise<AdminPatch[]> {
  return req("/patches");
}

export async function resolveReport(reportId: string, action: string) {
  return req(`/reports/${reportId}/resolve?action=${action}`, { method: "POST" });
}

// Posts management
export async function deletePostAdmin(postId: string) {
  return req(`/posts/${postId}`, { method: "DELETE" });
}

export async function mutePostAdmin(postId: string, hours: number) {
  return req(`/posts/${postId}/mute?hours=${hours}`, { method: "POST" });
}

// User management
export async function banUser(userId: string, hours: number, type: string = "ban_user", reason: string = "") {
  const params = new URLSearchParams({ hours: String(hours), type });
  if (reason) params.set("reason", reason);
  return req(`/users/${userId}/ban?${params}`, { method: "POST" });
}

export async function unbanUser(userId: string, type?: string) {
  const qs = type ? `?type=${type}` : "";
  return req(`/users/${userId}/unban${qs}`, { method: "POST" });
}

export async function getBanStatus(userId: string): Promise<Array<{id:string;type:string;reason:string|null;duration_hours:number|null;expires_at:string|null;created_at:string}>> {
  return req(`/users/${userId}/ban-status`);
}

export async function listUsers(): Promise<AdminUser[]> {
  return req("/users");
}

// Patches management
export async function deletePatchAdmin(patchId: string) {
  return req(`/patches/${patchId}`, { method: "DELETE" });
}

// Guild admin
export async function adminUpdateGuild(guildId: string, data: { name?: string; logo?: string; description?: string; level?: number }) {
  const params = new URLSearchParams();
  if (data.name) params.set("name", data.name);
  if (data.logo !== undefined) params.set("logo", data.logo);
  if (data.description !== undefined) params.set("description", data.description);
  if (data.level !== undefined) params.set("level", String(data.level));
  return req(`/guilds/${guildId}?${params}`, { method: "PATCH" });
}

export async function adminDeleteGuild(guildId: string) {
  return req(`/guilds/${guildId}`, { method: "DELETE" });
}

export async function adminRemoveMember(guildId: string, userId: string) {
  return req(`/guilds/${guildId}/members/${userId}`, { method: "DELETE" });
}

export async function listAdminGuildDiscussions(guildId: string): Promise<AdminGuildDiscussion[]> {
  return req(`/guilds/${guildId}/discussions`);
}

export async function adminDeleteGuildDiscussion(guildId: string, postId: string) {
  return req(`/guilds/${guildId}/discussions/${postId}`, { method: "DELETE" });
}

export async function checkAdmin(): Promise<boolean> {
  try {
    await req("/reports?status=pending");
    return true;
  } catch {
    return false;
  }
}


export interface AdminAISettings {
  enabled: boolean;
  base_url: string;
  model: string;
  api_key_configured: boolean;
  moderation_provider_fallback_enabled: boolean;
  trusted_classifier_configured: boolean;
  source: "database" | "environment";
}

export interface AdminAISettingsUpdate {
  enabled: boolean;
  base_url: string;
  model: string;
  api_key?: string;
  moderation_provider_fallback_enabled: boolean;
}

export async function getAISettings(): Promise<AdminAISettings> {
  return req("/ai-settings");
}

export async function updateAISettings(data: AdminAISettingsUpdate): Promise<AdminAISettings> {
  return req("/ai-settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function resetAISettings(): Promise<void> {
  await req("/ai-settings", { method: "DELETE" });
}
