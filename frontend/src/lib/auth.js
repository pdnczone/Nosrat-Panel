import { writable, derived, get } from 'svelte/store';

const TOKEN_KEY = 'nosrat_token';
const USER_KEY = 'nosrat_user';

export const auth = writable({
  token: null,
  user: null,
  ready: false
});

function loadFromStorage() {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    const userRaw = localStorage.getItem(USER_KEY);
    if (token && userRaw) {
      auth.set({ token, user: JSON.parse(userRaw), ready: true });
      return;
    }
  } catch (_) {}
  auth.set({ token: null, user: null, ready: true });
}

loadFromStorage();

export function getToken() {
  return get(auth).token;
}

export function getUser() {
  return get(auth).user;
}

export function setAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  auth.set({ token, user, ready: true });
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  auth.set({ token: null, user: null, ready: true });
}

export const isAuthenticated = derived(auth, ($a) => Boolean($a.token && $a.user));

export const isAdmin = derived(auth, ($a) => $a.user?.role === 'admin');

export function hasRole(...roles) {
  const u = get(auth).user;
  return u && roles.includes(u.role);
}
