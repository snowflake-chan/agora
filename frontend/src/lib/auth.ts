import { API_BASE } from "./config";
import type { VotingWindowKind } from "./governance";

export interface User {
  id: string;
  email: string;
  username: string;
  nickname: string | null;
  bio: string | null;
  role: "user" | "moderator" | "super_admin";
  is_active: boolean;
}

export interface UserPublic {
  id: string;
  username: string;
  nickname: string | null;
  bio: string | null;
  follower_count: number;
  following_count: number;
  is_following: boolean;
}

export interface FollowState {
  follower_count: number;
  following_count: number;
  is_following: boolean;
}

export interface UserContentItem {
  id: string;
  type: "post" | "comment" | "patch";
  title: string | null;
  content: string;
  created_at: string;
  root_type: "post" | "patch" | null;
  root_id: string | null;
  root_title: string | null;
  replying_to_id: string | null;
  replying_to_username: string | null;
  replying_to_content: string | null;
  reply_count: number;
  like_count: number;
  pr_number: number | null;
  status: string | null;
  voting_started_at: string | null;
  voting_ends_at: string | null;
  voting_period_hours: number | null;
  voting_window_kind: VotingWindowKind | null;
  can_delete: boolean;
}

export interface UserUpdateData {
  email?: string;
  username?: string;
  nickname?: string;
  bio?: string;
  password?: string;
}

export class ApiError extends Error {
  code: string;

  constructor(detail: string) {
    super(detail);
    this.name = "ApiError";
    this.code = detail;
  }
}

export async function login(email: string, password: string): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    credentials: "include",
  });
  if (!res.ok) throw new ApiError((await res.json()).detail);
  return res.json();
}

export async function register(email: string, username: string, password: string): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, username, password }),
    credentials: "include",
  });
  if (!res.ok) throw new ApiError((await res.json()).detail);
  return res.json();
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

export async function getMe(): Promise<User | null> {
  try {
    const res = await fetch(`${API_BASE}/users/me`, { credentials: "include" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function updateProfile(data: UserUpdateData): Promise<User> {
  const res = await fetch(`${API_BASE}/users/me`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    credentials: "include",
  });
  if (!res.ok) throw new ApiError((await res.json()).detail);
  return res.json();
}

export async function getUser(userId: string): Promise<UserPublic> {
  const res = await fetch(`${API_BASE}/users/${userId}`, { credentials: "include" });
  if (!res.ok) throw new Error("User not found");
  return res.json();
}

export async function getUserPosts(userId: string): Promise<import("./posts").Post[]> {
  const res = await fetch(`${API_BASE}/users/${userId}/posts`, { credentials: "include" });
  if (!res.ok) throw new Error("Failed to load");
  return res.json();
}

export async function getUserPatches(userId: string): Promise<import("./patches").Patch[]> {
  const res = await fetch(`${API_BASE}/users/${userId}/patches`, { credentials: "include" });
  if (!res.ok) throw new Error("Failed to load");
  return res.json();
}

export async function getUserContent(userId: string): Promise<UserContentItem[]> {
  const res = await fetch(`${API_BASE}/users/${userId}/content`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to load user content");
  return res.json();
}

async function setFollow(userId: string, following: boolean): Promise<FollowState> {
  const res = await fetch(`${API_BASE}/users/${userId}/follow`, {
    method: following ? "PUT" : "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new ApiError((await res.json()).detail);
  return res.json();
}

export const followUser = (userId: string) => setFollow(userId, true);
export const unfollowUser = (userId: string) => setFollow(userId, false);
