/**
 * Svelte stores for the node-agent integration.
 *
 * - ``nodes``: live snapshot of all servers with a node token configured.
 * - ``nodeEvents``: writable stream of messages coming from /api/nodes/ws.
 * - ``loadNodes`` / ``reloadNode`` helpers for one-shot fetches.
 */
import { writable, derived, get } from 'svelte/store';
import { NodesAPI, ServersAPI } from '../lib/api.js';
import { getToken } from '../lib/auth.js';
import { openChannel } from '../lib/ws.js';

export const nodes = writable([]);
export const nodesLoading = writable(false);
export const nodeEvents = writable([]);
export const nodeConnection = writable({ open: false, error: null });

/** Map server_id -> latest online state, derived from ``nodes`` + WS bus. */
export const onlineNodes = derived(nodes, ($nodes) =>
  $nodes.filter((n) => n.online)
);

export async function loadNodes() {
  nodesLoading.set(true);
  try {
    const data = await NodesAPI.list();
    nodes.set(Array.isArray(data) ? data : data.items || []);
  } finally {
    nodesLoading.set(false);
  }
}

export async function reloadNode(serverId) {
  const data = await NodesAPI.get(serverId);
  nodes.update((arr) => {
    const idx = arr.findIndex((n) => n.server_id === serverId);
    if (idx === -1) return [...arr, data];
    const copy = arr.slice();
    copy[idx] = data;
    return copy;
  });
  return data;
}

export async function installNode(serverId, payload) {
  const job = await ServersAPI.installNode(serverId, payload);
  return job;
}

export async function fetchInstallStatus(serverId, afterLine = 0) {
  return ServersAPI.installStatus(serverId, afterLine);
}

export async function testSSH(serverId, payload) {
  return ServersAPI.testSSH(serverId, payload);
}

export async function nodeInfo(serverId) {
  return ServersAPI.nodeInfo(serverId);
}

/** Start (or return the singleton) event stream. Idempotent. */
let started = false;
export function startNodeEventStream() {
  if (started) return;
  started = true;
  const url = `${NodesAPI.eventsUrl()}?token=${encodeURIComponent(getToken() || '')}`;
  const ch = openChannel(url);
  ch.subscribe((msg) => {
    if (!msg || typeof msg !== 'object') return;
    nodeEvents.update((arr) => [...arr.slice(-200), msg]);
    if (msg.type === 'node_snapshot' && Array.isArray(msg.nodes)) {
      nodes.update((arr) => {
        const map = new Map(arr.map((n) => [n.server_id, n]));
        for (const snap of msg.nodes) {
          const existing = map.get(snap.server_id);
          if (existing) {
            map.set(snap.server_id, { ...existing, online: true, ...snap });
          }
        }
        return Array.from(map.values());
      });
    }
  });
}