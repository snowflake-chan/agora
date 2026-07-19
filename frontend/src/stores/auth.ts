import { writable } from "svelte/store";
import * as api from "../lib/auth";
import type { User, UserUpdateData } from "../lib/auth";

export { type User, type UserUpdateData };

export const currentUser = writable<User | null>(null);
let authInitialization: Promise<User | null> | null = null;

export async function initAuth() {
  authInitialization ??= api.getMe();
  const user = await authInitialization;
  currentUser.set(user);
  return user;
}

export async function login(email: string, password: string) {
  const user = await api.login(email, password);
  authInitialization = Promise.resolve(user);
  currentUser.set(user);
  return user;
}

export async function register(email: string, username: string, password: string) {
  const user = await api.register(email, username, password);
  authInitialization = Promise.resolve(user);
  currentUser.set(user);
  return user;
}

export async function logout() {
  await api.logout();
  authInitialization = Promise.resolve(null);
  currentUser.set(null);
}

export async function updateProfile(data: UserUpdateData) {
  const user = await api.updateProfile(data);
  authInitialization = Promise.resolve(user);
  currentUser.set(user);
  return user;
}
