import { API_BASE } from "./config";
import type { ModerationFields } from "./moderation";

export interface Guild {
  id: string;
  name: string;
  logo: string | null;
  description: string | null;
  president_id: string;
  president_username: string;
  member_count: number;
  level: number;
  created_at: string;
}

export interface GuildMember {
  id: string;
  user_id: string;
  username: string;
  nickname: string | null;
  role: string; // "president" | "vice_president" | "member"
  status: string; // "pending" | "approved" | "rejected"
  joined_at: string;
}

export interface GuildDiscussion extends ModerationFields {
  id: string;
  title: string | null;
  content: string;
  author_id: string;
  author_username: string;
  created_at: string;
}

export interface UserGuildBadge {
  guild_id: string;
  guild_name: string;
  guild_level: number;
  role: string;
}

export interface GuildLevelDetail {
  guild_id: string;
  proposal_score: number;
  current_level: number;
  next_level: number | null;
  next_threshold: number | null;
  progress_to_next: number | null;
}

export interface GuildProposalContribution {
  proposal_id: string;
  title: string;
  username: string;
  counted_at: string;
}

export interface GuildProposalList {
  items: GuildProposalContribution[];
  total: number;
  page: number;
  page_size: number;
}

async function req(path: string, options?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include", ...options });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  if (res.status === 204) return null;
  return res.json();
}

const userGuildCache = new Map<string, Promise<UserGuildBadge | null>>();

// ── Guilds ──

export async function listGuilds(): Promise<Guild[]> {
  return req("/guilds");
}

export async function getGuild(id: string): Promise<Guild> {
  return req(`/guilds/${id}`);
}

export async function createGuild(data: { name: string; logo?: string | null; description?: string | null }): Promise<Guild> {
  return req("/guilds", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
}

export async function updateGuild(id: string, data: { name?: string; logo?: string | null; description?: string | null }) {
  return req(`/guilds/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
}

export async function deleteGuild(id: string): Promise<void> {
  await req(`/guilds/${id}`, { method: "DELETE" });
}

export async function joinGuild(id: string): Promise<void> {
  await req(`/guilds/${id}/join`, { method: "POST" });
}

export async function leaveGuild(id: string): Promise<void> {
  await req(`/guilds/${id}/leave`, { method: "POST" });
}

// ── Members ──

export async function listMembers(guildId: string): Promise<GuildMember[]> {
  return req(`/guilds/${guildId}/members`);
}

export async function getMyMembership(guildId: string): Promise<GuildMember | null> {
  return req(`/guilds/${guildId}/membership`);
}

// ── Patches ──

export async function listGuildPatches(guildId: string): Promise<import("./patches").Patch[]> {
  return req(`/guilds/${guildId}/patches`);
}

// ── Discussions ──

export async function listDiscussions(guildId: string): Promise<GuildDiscussion[]> {
  return req(`/guilds/${guildId}/discussions`);
}

export async function createDiscussion(guildId: string, data: { title?: string | null; content: string }): Promise<GuildDiscussion> {
  return req(`/guilds/${guildId}/discussions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
}

export async function deleteDiscussion(guildId: string, postId: string): Promise<void> {
  await req(`/guilds/${guildId}/discussions/${postId}`, { method: "DELETE" });
}

// ── My Guild ──

export async function getMyGuild(): Promise<UserGuildBadge | null> {
  return req("/guilds/-/my");
}

// ── User Guild ──

export async function getUserGuild(userId: string): Promise<UserGuildBadge | null> {
  let request = userGuildCache.get(userId);
  if (!request) {
    request = req(`/users/${userId}/guild`).catch((error) => {
      userGuildCache.delete(userId);
      throw error;
    });
    userGuildCache.set(userId, request);
  }
  return request;
}

// ── Guild Leveling ──

export async function getGuildLevel(guildId: string): Promise<GuildLevelDetail> {
  return req(`/guilds/${guildId}/level`);
}

export async function listGuildProposals(
  guildId: string,
  page: number = 1,
  pageSize: number = 20,
): Promise<GuildProposalList> {
  return req(`/guilds/${guildId}/proposals?page=${page}&page_size=${pageSize}`);
}
