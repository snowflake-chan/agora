import { writable, derived } from "svelte/store";
import * as api from "../lib/auth";
import type { User } from "../lib/auth";

export { type User };

export const currentUser = writable<User | null>(null);
export const isAuthenticated = derived(currentUser, ($u) => $u !== null);

export async function initAuth() {
  currentUser.set(await api.getMe());
}

export async function login(email: string, password: string) {
  const user = await api.login(email, password);
  currentUser.set(user);
  return user;
}

export async function register(email: string, password: string) {
  const user = await api.register(email, password);
  currentUser.set(user);
  return user;
}

export async function logout() {
  await api.logout();
  currentUser.set(null);
}
