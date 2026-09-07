import { writable } from 'svelte/store';
import { ServersAPI } from '../lib/api.js';
import { toast } from '../lib/toast.js';

export const servers = writable([]);
export const serversLoading = writable(false);

export async function loadServers() {
  serversLoading.set(true);
  try {
    const data = await ServersAPI.list();
    servers.set(Array.isArray(data) ? data : data.items || []);
  } finally {
    serversLoading.set(false);
  }
}

export async function deleteServer(id) {
  await ServersAPI.delete(id);
  toast.success('سرور حذف شد');
  servers.update((arr) => arr.filter((s) => s.id !== id));
}

export async function createServer(payload) {
  const s = await ServersAPI.create(payload);
  toast.success('سرور اضافه شد');
  servers.update((arr) => [...arr, s]);
  return s;
}

export async function testServer(id) {
  const res = await ServersAPI.test(id);
  toast[res.ok ? 'success' : 'error'](res.message || (res.ok ? 'اتصال موفق' : 'اتصال ناموفق'));
  return res;
}
