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
  id: string; content_id: string; content_title: string; content_body: string;
  content_author: string; content_author_id: string; reporter_username: string; reason: string;
  status: string; created_at: string; report_count?: number;
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

export async function setUserRole(userId: string, role: string) {
  return req(`/users/${userId}/role?role=${role}`, { method: "POST" });
}

export async function seedSuperAdmin() {
  return req("/seed-super-admin", { method: "POST" });
}

// Reports
export async function createReport(contentId: string, reason: string) {
  return req(`/reports?content_id=${contentId}&reason=${encodeURIComponent(reason)}`, { method: "POST" });
}

export async function listReports(status?: string): Promise<ReportItem[]> {
  const qs = status ? `?status=${status}` : "";
  return req(`/reports${qs}`);
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
