import { writable } from 'svelte/store';

export const toasts = writable([]);

let nextId = 1;

function push(type, message, ttl = 4000) {
  const id = nextId++;
  toasts.update((arr) => [...arr, { id, type, message, createdAt: Date.now() }]);
  if (ttl > 0) setTimeout(() => dismiss(id), ttl);
  return id;
}

export function dismiss(id) {
  toasts.update((arr) => arr.filter((t) => t.id !== id));
}

export const toast = {
  success: (msg, ttl) => push('success', msg, ttl),
  error: (msg, ttl) => push('error', msg, ttl ?? 6000),
  info: (msg, ttl) => push('info', msg, ttl),
  warning: (msg, ttl) => push('warning', msg, ttl ?? 5000)
};

export const ICONS = {
  success: '✓',
  error: '✕',
  info: 'ℹ',
  warning: '⚠'
};

export const COLORS = {
  success: 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300',
  error: 'bg-red-500/15 border-red-500/40 text-red-300',
  info: 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300',
  warning: 'bg-amber-500/15 border-amber-500/40 text-amber-300'
};
