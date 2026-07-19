import { writable } from "svelte/store";
import * as api from "../lib/auth";
import type { User, UserUpdateData } from "../lib/auth";

export { type User, type UserUpdateData };

export const currentUser = writable<User | null>(null);

export async function initAuth() {
  currentUser.set(await api.getMe());
}

export async function login(email: string, password: string) {
  const user = await api.login(email, password);
  currentUser.set(user);
  return user;
}

export async function register(email: string, username: string, password: string) {
  const user = await api.register(email, username, password);
  currentUser.set(user);
  return user;
}

export async function logout() {
  await api.logout();
  currentUser.set(null);
}

export async function updateProfile(data: UserUpdateData) {
  const user = await api.updateProfile(data);
  currentUser.set(user);
  return user;
}
