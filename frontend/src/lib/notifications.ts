import { API_BASE } from "./config";

export interface Notification {
  id: string;
  type: string;
  title: string;
  message: string;
  link: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationList {
  items: Notification[];
  total: number;
  page: number;
  page_size: number;
  unread_count: number;
}

export async function listNotifications(page = 1): Promise<NotificationList> {
  const res = await fetch(`${API_BASE}/notifications?page=${page}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to load notifications");
  return res.json();
}

export async function getUnreadCount(): Promise<number> {
  const res = await fetch(`${API_BASE}/notifications/unread-count`, {
    credentials: "include",
  });
  if (!res.ok) return 0;
  const data = await res.json();
  return data.count ?? 0;
}

export async function markAllRead(): Promise<void> {
  await fetch(`${API_BASE}/notifications/read-all`, {
    method: "PATCH",
    credentials: "include",
  });
}

export async function markRead(id: string): Promise<void> {
  await fetch(`${API_BASE}/notifications/${id}/read`, {
    method: "PATCH",
    credentials: "include",
  });
}
