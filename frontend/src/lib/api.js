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
      if (location.hash !== '#/login') location.hash = '#/login';
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
  test: (id) => api.post(`/servers/${id}/test`).then((r) => r.data),
  testSSH: (id, payload) => api.post(`/servers/${id}/test-ssh`, payload || {}).then((r) => r.data),
  nodeInfo: (id) => api.get(`/servers/${id}/node-info`).then((r) => r.data),
  installNode: (id, payload) => api.post(`/servers/${id}/install-node`, payload || {}).then((r) => r.data),
  installStatus: (id, afterLine = 0) =>
    api.get(`/servers/${id}/install-status`, { params: { after_line: afterLine } }).then((r) => r.data),
  terminalUrl: (id, cols = 80, rows = 24) =>
    `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/servers/${id}/terminal?cols=${cols}&rows=${rows}`
};

// ---------- Node endpoints ----------
export const NodesAPI = {
  list: () => api.get('/nodes').then((r) => r.data),
  get: (id) => api.get(`/nodes/${id}`).then((r) => r.data),
  command: (id, payload) => api.post(`/nodes/${id}/command`, payload).then((r) => r.data),
  metrics: (id, params) => api.get(`/nodes/${id}/metrics`, { params }).then((r) => r.data),
  latestMetric: (id) => api.get(`/nodes/${id}/metrics/latest`).then((r) => r.data),
  logs: (id, params) => api.get(`/nodes/${id}/logs`, { params }).then((r) => r.data),
  commands: (id, params) => api.get(`/nodes/${id}/commands`, { params }).then((r) => r.data),
  eventsUrl: () =>
    `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/nodes/ws`
};

// ---------- Crypto endpoints ----------
export const CryptoAPI = {
  pskList: () => api.get('/crypto/psk/list').then((r) => r.data),
  pskCreate: (payload) => api.post('/crypto/psk/generate', payload).then((r) => r.data),
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
  full: (target) => api.post('/speed/test', { target, duration_sec: 10, parallel: 4 }).then((r) => r.data),
  iperf3: (target, params = {}) => api.post('/speed/test', { target, duration_sec: params.duration || 10, parallel: params.parallel || 4 }).then((r) => r.data),
  history: (params) => api.get('/speed/history', { params }).then((r) => r.data)
};

// ---------- Clients (VPN subscribers) endpoints ----------
export const ClientsAPI = {
  list: (params) => api.get('/clients', { params }).then((r) => r.data),
  get: (id) => api.get(`/clients/${id}`).then((r) => r.data),
  create: (payload) => api.post('/clients', payload).then((r) => r.data),
  update: (id, payload) => api.patch(`/clients/${id}`, payload).then((r) => r.data),
  topup: (id, payload) => api.post(`/clients/${id}/topup`, payload).then((r) => r.data),
  usage: (id, params) => api.get(`/clients/${id}/usage`, { params }).then((r) => r.data),
  delete: (id) => api.delete(`/clients/${id}`).then((r) => r.data)
};

// ---------- User endpoints ----------
export const UsersAPI = {
  list: () => api.get('/users').then((r) => r.data),
  get: (id) => api.get(`/users/${id}`).then((r) => r.data),
  create: (payload) => api.post('/users', payload).then((r) => r.data),
  update: (id, payload) => api.patch(`/users/${id}`, payload).then((r) => r.data),
  delete: (id) => api.delete(`/users/${id}`).then((r) => r.data),
  me: () => api.get('/auth/me').then((r) => r.data)
};

// ---------- Settings endpoints ----------
export const SettingsAPI = {
  get: () => api.get('/settings').then((r) => r.data),
  update: (section, payload) =>
    api
      .put('/settings', { items: Object.fromEntries(Object.entries(payload).map(([k, v]) => [`${section}.${k}`, v])) })
      .then((r) => r.data),
  backup: () => api.get('/settings/backup', { responseType: 'blob' }).then((r) => r.data),
  restore: (formData) =>
    api.post('/settings/restore', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data)
};

// ---------- Auth endpoints ----------
export const AuthAPI = {
  login: (username, password) => api.post('/auth/login', { username, password }).then((r) => r.data),
  logout: () => api.post('/auth/logout').then((r) => r.data),
  refresh: () => api.post('/auth/refresh').then((r) => r.data),
  me: () => api.get('/auth/me').then((r) => r.data),
};

// ---------- Stats ----------
export const StatsAPI = {
  dashboard: () => api.get('/stats/dashboard').then((r) => r.data),
  activity: (params) => api.get('/stats/activity', { params }).then((r) => r.data)
};
