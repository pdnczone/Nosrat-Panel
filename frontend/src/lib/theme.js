import { writable } from 'svelte/store';

const STORAGE_KEY = 'nosrat_theme';
const VALID = ['dark', 'light'];

function detect() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (VALID.includes(saved)) return saved;
  } catch (_) {}
  return 'dark';
}

export const theme = writable(detect());

export function initTheme() {
  theme.subscribe((t) => {
    try { localStorage.setItem(STORAGE_KEY, t); } catch (_) {}
    document.documentElement.classList.toggle('dark', t === 'dark');
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = t === 'dark' ? '#06b6d4' : '#0891b2';
  });
}

export function toggleTheme() {
  theme.update((t) => (t === 'dark' ? 'light' : 'dark'));
}

export function setTheme(t) {
  if (VALID.includes(t)) theme.set(t);
}
