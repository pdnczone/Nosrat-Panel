<!--
  Terminal.svelte — xterm.js based terminal that talks to a backend WebSocket.

  Props:
    - ``url``  (string) — fully qualified WebSocket URL (including ?token=…).

  The component renders an xterm Terminal into the bound DOM node, opens the
  WebSocket, and pipes:
    - WS text frames  -> terminal.write()
    - terminal input  -> ws.send()
    - terminal resize -> ws.send("RESIZE:rowsxcols")

  The component is self-contained: it imports xterm via a dynamic ``import()``
  so Svelte/Vite code-splits it out of the main bundle.
-->
<script>
  import { onMount, onDestroy } from 'svelte';

  let { url = '', cols = 80, rows = 24, onclose = () => {}, class: cls = '' } = $props();

  let container;
  let term;
  let fitAddon;
  let ws = null;
  let mounted = false;

  async function loadXterm() {
    // The xterm bundles live in node_modules.  Use dynamic imports so the
    // Svelte compiler doesn't choke on package.json `exports` mapping.
    const [{ Terminal }, { FitAddon }] = await Promise.all([
      import('@xterm/xterm'),
      import('@xterm/addon-fit').then((m) => ({ FitAddon: m.FitAddon })),
    ]);
    // CSS is loaded once; safe to call repeatedly thanks to <link> dedup.
    if (!document.querySelector('link[data-xterm-css]')) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = '/xterm/xterm.css';
      link.dataset.xtermCss = 'true';
      document.head.appendChild(link);
    }
    const t = new Terminal({
      cols,
      rows,
      cursorBlink: true,
      convertEol: true,
      fontFamily: '"JetBrains Mono", "Fira Code", "Menlo", monospace',
      fontSize: 13,
      theme: {
        background: '#0f172a',
        foreground: '#e2e8f0',
        cursor: '#22d3ee',
        black: '#0f172a',
        red: '#ef4444',
        green: '#22c55e',
        yellow: '#f59e0b',
        blue: '#3b82f6',
        magenta: '#a855f7',
        cyan: '#06b6d4',
        white: '#cbd5e1',
        brightBlack: '#475569',
        brightRed: '#f87171',
        brightGreen: '#4ade80',
        brightYellow: '#fbbf24',
        brightBlue: '#60a5fa',
        brightMagenta: '#c084fc',
        brightCyan: '#22d3ee',
        brightWhite: '#f8fafc',
      },
    });
    const fa = new FitAddon();
    t.loadAddon(fa);
    t.open(container);
    fa.fit();
    return { term: t, fitAddon: fa };
  }

  function connect() {
    if (!url || !term) return;
    try {
      ws = new WebSocket(url);
    } catch (err) {
      term.write(`\r\n\x1b[31mws error: ${err.message}\x1b[0m\r\n`);
      return;
    }
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      term.write('\x1b[2mconnecting…\x1b[0m\r\n');
    };
    ws.onmessage = (ev) => {
      try {
        term.write(typeof ev.data === 'string' ? ev.data : '');
      } catch {
        /* noop */
      }
    };
    ws.onclose = (ev) => {
      term.write(`\r\n\x1b[33m[closed code=${ev.code}]\x1b[0m\r\n`);
      onclose(ev);
    };
    ws.onerror = () => {
      term.write('\r\n\x1b[31m[connection error]\x1b[0m\r\n');
    };
  }

  function disconnect() {
    if (ws) {
      try { ws.close(); } catch {}
      ws = null;
    }
  }

  onMount(async () => {
    try {
      const r = await loadXterm();
      term = r.term;
      fitAddon = r.fitAddon;
      mounted = true;
      term.onData((data) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(data);
        }
      });
      term.onResize(({ cols: nc, rows: nr }) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(`RESIZE:${nr}x${nc}`);
        }
      });
      connect();
      const ro = new ResizeObserver(() => {
        try { fitAddon?.fit(); } catch {}
      });
      ro.observe(container);
      return () => ro.disconnect();
    } catch (err) {
      console.error('xterm init failed', err);
    }
  });

  onDestroy(() => {
    disconnect();
    try { term?.dispose(); } catch {}
  });

  export function reconnect() {
    disconnect();
    if (term) term.write('\r\n\x1b[36mreconnecting…\x1b[0m\r\n');
    connect();
  }

  export function clear() {
    term?.clear();
  }
</script>

<div bind:this={container} class="terminal-host bg-slate-950 {cls}"></div>

<style>
  .terminal-host {
    width: 100%;
    height: 100%;
    min-height: 280px;
    padding: 8px;
    border-radius: 0.5rem;
    overflow: hidden;
  }
  :global(.terminal-host .xterm) {
    height: 100%;
  }
  :global(.terminal-host .xterm-viewport) {
    background: transparent !important;
  }
</style>