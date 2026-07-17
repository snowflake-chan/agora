const BASE = "/api/v1";

export interface User {
  id: string;
  email: string;
  is_active: boolean;
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
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    credentials: "include",
  });
  if (!res.ok) throw new ApiError((await res.json()).detail);
  return res.json();
}

export async function register(email: string, password: string): Promise<User> {
  const res = await fetch(`${BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    credentials: "include",
  });
  if (!res.ok) throw new ApiError((await res.json()).detail);
  return res.json();
}

export async function logout(): Promise<void> {
  await fetch(`${BASE}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

export async function getMe(): Promise<User | null> {
  try {
    const res = await fetch(`${BASE}/users/me`, { credentials: "include" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
