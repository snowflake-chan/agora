import { API_BASE } from "./config";

export interface User {
  id: string;
  email: string;
  username: string;
  nickname: string | null;
  bio: string | null;
  is_active: boolean;
  points: number;
  first_guild_id: string | null;
}

export interface UserPublic {
  id: string;
  username: string;
  nickname: string | null;
  bio: string | null;
  points: number;
  first_guild_id: string | null;
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
