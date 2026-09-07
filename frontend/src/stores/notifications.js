import { writable } from 'svelte/store';

export const notifications = writable([]);

let counter = 0;

export function notify(message, level = 'info', ttl = 5000) {
  const id = ++counter;
  const item = { id, message, level, createdAt: Date.now(), read: false };
  notifications.update((arr) => [item, ...arr].slice(0, 100));
  if (ttl > 0) setTimeout(() => dismiss(id), ttl);
  return id;
}

export function dismiss(id) {
  notifications.update((arr) => arr.filter((n) => n.id !== id));
}

export function markAllRead() {
  notifications.update((arr) => arr.map((n) => ({ ...n, read: true })));
}

export function unreadCount(notifs) {
  return notifs.filter((n) => !n.read).length;
}
