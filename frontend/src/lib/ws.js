/**
 * WebSocket manager with auto-reconnect, channel multiplexing, and reactive store.
 */
import { writable } from 'svelte/store';

const STATUS = {
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  DISCONNECTED: 'disconnected',
  RECONNECTING: 'reconnecting'
};

const status = writable(STATUS.DISCONNECTED);
export const wsStatus = { subscribe: status.subscribe };

function buildUrl(path) {
  if (path.startsWith('ws://') || path.startsWith('wss://')) return path;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}${path}`;
}

class WSChannel {
  constructor(path) {
    this.path = path;
    this.url = buildUrl(path);
    this.ws = null;
    this.listeners = new Set();
    this.reconnectAttempts = 0;
    this.shouldReconnect = true;
    this.lastError = null;
    this.queue = [];
    this.connect();
  }

  connect() {
    status.set(this.reconnectAttempts === 0 ? STATUS.CONNECTING : STATUS.RECONNECTING);
    try {
      this.ws = new WebSocket(this.url);
    } catch (e) {
      this.lastError = e;
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      status.set(STATUS.CONNECTED);
      while (this.queue.length) this.ws.send(this.queue.shift());
    };

    this.ws.onmessage = (ev) => {
      let data = ev.data;
      try { data = JSON.parse(ev.data); } catch (_) {}
      for (const fn of this.listeners) {
        try { fn(data); } catch (e) { console.error('ws listener error', e); }
      }
    };

    this.ws.onerror = (e) => {
      this.lastError = e;
    };

    this.ws.onclose = () => {
      status.set(STATUS.DISCONNECTED);
      if (this.shouldReconnect) this.scheduleReconnect();
    };
  }

  scheduleReconnect() {
    this.reconnectAttempts += 1;
    const delay = Math.min(30000, 1000 * Math.pow(2, this.reconnectAttempts));
    setTimeout(() => this.shouldReconnect && this.connect(), delay);
  }

  send(data) {
    const payload = typeof data === 'string' ? data : JSON.stringify(data);
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(payload);
    else this.queue.push(payload);
  }

  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  close() {
    this.shouldReconnect = false;
    this.ws?.close();
  }
}

const channels = new Map();

export function openChannel(path) {
  if (channels.has(path)) return channels.get(path);
  const ch = new WSChannel(path);
  channels.set(path, ch);
  return ch;
}

export function closeChannel(path) {
  const ch = channels.get(path);
  if (ch) {
    ch.close();
    channels.delete(path);
  }
}

export function closeAll() {
  for (const ch of channels.values()) ch.close();
  channels.clear();
}

/** Reactive store for messages on a given path. */
export function wsMessages(path) {
  const store = writable([]);
  const ch = openChannel(path);
  const unsub = ch.subscribe((msg) => {
    store.update((arr) => [...arr, msg].slice(-200));
  });
  store.close = () => unsub();
  return store;
}
