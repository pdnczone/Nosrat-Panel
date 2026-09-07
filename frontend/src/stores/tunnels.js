import { writable, derived } from 'svelte/store';
import { TunnelsAPI } from '../lib/api.js';
import { toast } from '../lib/toast.js';

export const tunnels = writable([]);
export const tunnelsLoading = writable(false);
export const tunnelsError = writable(null);

export async function loadTunnels(params) {
  tunnelsLoading.set(true);
  tunnelsError.set(null);
  try {
    const data = await TunnelsAPI.list(params);
    tunnels.set(Array.isArray(data) ? data : data.items || []);
  } catch (e) {
    tunnelsError.set(e.message || 'خطا در بارگذاری تانل‌ها');
  } finally {
    tunnelsLoading.set(false);
  }
}

export async function startTunnel(id) {
  await TunnelsAPI.start(id);
  toast.success('تانل در حال راه‌اندازی...');
  await loadTunnels();
}

export async function stopTunnel(id) {
  await TunnelsAPI.stop(id);
  toast.success('تانل متوقف شد');
  await loadTunnels();
}

export async function deleteTunnel(id) {
  await TunnelsAPI.delete(id);
  toast.success('تانل حذف شد');
  tunnels.update((arr) => arr.filter((t) => t.id !== id));
}

export async function createTunnel(payload) {
  const t = await TunnelsAPI.create(payload);
  toast.success('تانل ساخته شد');
  tunnels.update((arr) => [...arr, t]);
  return t;
}

export const tunnelStats = derived(tunnels, ($t) => ({
  total: $t.length,
  running: $t.filter((t) => t.status === 'running').length,
  stopped: $t.filter((t) => t.status === 'stopped').length,
  error: $t.filter((t) => t.status === 'error').length
}));
