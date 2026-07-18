import { writable } from "svelte/store";
import type { Notification } from "../lib/notifications";
import * as api from "../lib/notifications";

export const unreadCount = writable<number>(0);
export const notifications = writable<Notification[]>([]);

let eventSource: EventSource | null = null;

export function initNotificationStore() {
  // Fetch initial unread count
  api.getUnreadCount().then((c) => unreadCount.set(c)).catch(() => {});

  // Connect SSE
  connectSSE();
}

function connectSSE() {
  if (eventSource) eventSource.close();

  eventSource = new EventSource("/api/v1/notifications/stream");

  eventSource.addEventListener("notification", (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);
      // Bump unread count
      unreadCount.update((n) => n + 1);
      // Prepend to notifications list (max 50)
      notifications.update((list) => {
        const next = [
          {
            id: data.id,
            type: data.type,
            title: data.title,
            message: data.message,
            link: data.link,
            is_read: false,
            created_at: data.created_at,
          } as Notification,
          ...list,
        ];
        return next.slice(0, 50);
      });
    } catch {
      // ignore parse errors
    }
  });

  eventSource.onerror = () => {
    // EventSource auto-reconnects; no action needed
  };
}

export async function openNotifications() {
  // Fetch fresh list and mark all as read
  const [list] = await Promise.all([
    api.listNotifications(1),
    api.markAllRead(),
  ]);
  notifications.set(list.items);
  unreadCount.set(0);
}

export function cleanupNotificationStore() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}
