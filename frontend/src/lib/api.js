import axios from 'axios';
import { getToken, clearAuth } from './auth.js';
import { toast } from './toast.js';

export const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err.response?.status;
    const message = err.response?.data?.message || err.response?.data?.error || err.message;

    if (status === 401) {
      clearAuth();
      if (location.pathname !== '/login') location.href = '/login';
    } else if (status === 403) {
      toast('error', message || 'دسترسی غیرمجاز');
    } else if (status >= 500) {
      toast('error', 'خطای سرور: ' + message);
    } else if (status === 429) {
      toast('warning', 'تعداد درخواست‌ها زیاد است، کمی صبر کنید');
    } else if (message && err.config?.method !== 'get') {
      toast('error', message);
    }
    return Promise.reject(err);
  }
);

// ---------- Tunnel endpoints ----------
export const TunnelsAPI = {
  list: (params) => api.get('/tunnels', { params }).then((r) => r.data),
  get: (id) => api.get(`/tunnels/${id}`).then((r) => r.data),
  create: (payload) => api.post('/tunnels', payload).then((r) => r.data),
  update: (id, payload) => api.put(`/tunnels/${id}`, payload).then((r) => r.data),
  delete: (id) => api.delete(`/tunnels/${id}`).then((r) => r.data),
  start: (id) => api.post(`/tunnels/${id}/start`).then((r) => r.data),
  stop: (id) => api.post(`/tunnels/${id}/stop`).then((r) => r.data),
  restart: (id) => api.post(`/tunnels/${id}/restart`).then((r) => r.data),
  status: (id) => api.get(`/tunnels/${id}/status`).then((r) => r.data),
  logs: (id, params) => api.get(`/tunnels/${id}/logs`, { params }).then((r) => r.data),
  qrcode: (id) => api.get(`/tunnels/${id}/qrcode`, { responseType: 'blob' }).then((r) => r.data)
};

// ---------- Server endpoints ----------
export const ServersAPI = {
  list: () => api.get('/servers').then((r) => r.data),
  get: (id) => api.get(`/servers/${id}`).then((r) => r.data),
  create: (payload) => api.post('/servers', payload).then((r) => r.data),
  update: (id, payload) => api.put(`/servers/${id}`, payload).then((r) => r.data),
  delete: (id) => api.delete(`/servers/${id}`).then((r) => r.data),
  test: (id) => api.post(`/servers/${id}/test`).then((r) => r.data)
};

// ---------- Crypto endpoints ----------
export const CryptoAPI = {
  pskList: () => api.get('/crypto/psk').then((r) => r.data),
  pskCreate: (payload) => api.post('/crypto/psk', payload).then((r) => r.data),
  pskRotate: (id, payload) => api.post(`/crypto/psk/${id}/rotate`, payload).then((r) => r.data),
  pskDelete: (id) => api.delete(`/crypto/psk/${id}`).then((r) => r.data),
  export: (id) => api.get(`/crypto/psk/${id}/export`, { responseType: 'blob' }).then((r) => r.data)
};

// ---------- Health endpoints ----------
export const HealthAPI = {
  quick: () => api.get('/health/quick').then((r) => r.data),
  detailed: () => api.get('/health/detailed').then((r) => r.data),
  monitoring: (params) => api.get('/health/monitoring', { params }).then((r) => r.data),
  tunnel: (id) => api.get(`/health/tunnel/${id}`).then((r) => r.data)
};

// ---------- Speed endpoints ----------
export const SpeedAPI = {
  ping: (target) => api.post('/speed/ping', { target }).then((r) => r.data),
  full: (target) => api.post('/speed/full', { target }).then((r) => r.data),
  iperf3: (target, params) => api.post('/speed/iperf3', { target, ...params }).then((r) => r.data),
  history: (params) => api.get('/speed/history', { params }).then((r) => r.data)
};

// ---------- User endpoints ----------
export const UsersAPI = {
  list: () => api.get('/users').then((r) => r.data),
  get: (id) => api.get(`/users/${id}`).then((r) => r.data),
  create: (payload) => api.post('/users', payload).then((r) => r.data),
  update: (id, payload) => api.put(`/users/${id}`, payload).then((r) => r.data),
  delete: (id) => api.delete(`/users/${id}`).then((r) => r.data),
  me: () => api.get('/users/me').then((r) => r.data)
};

// ---------- Settings endpoints ----------
export const SettingsAPI = {
  get: () => api.get('/settings').then((r) => r.data),
  update: (section, payload) => api.put(`/settings/${section}`, payload).then((r) => r.data),
  backup: () => api.get('/settings/backup', { responseType: 'blob' }).then((r) => r.data),
  restore: (formData) =>
    api.post('/settings/restore', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data)
};

// ---------- Auth endpoints ----------
export const AuthAPI = {
  login: (username, password) => api.post('/auth/login', { username, password }).then((r) => r.data),
  logout: () => api.post('/auth/logout').then((r) => r.data),
  refresh: () => api.post('/auth/refresh').then((r) => r.data)
};

// ---------- Stats ----------
export const StatsAPI = {
  dashboard: () => api.get('/stats/dashboard').then((r) => r.data),
  activity: (params) => api.get('/stats/activity', { params }).then((r) => r.data)
};
