<!--
  Nodes.svelte — overview of all node agents registered with the panel.

  Each card shows live state (CPU/RAM/Disk), the last metrics sample,
  and quick actions: open terminal, send command, view logs.
-->
<script>
  import { onMount, onDestroy } from 'svelte';
  import { _ } from '../lib/i18n.js';
  import { getToken } from '../lib/auth.js';
  import { toast } from '../lib/toast.js';
  import {
    nodes,
    loadNodes,
    nodeEvents,
    reloadNode,
    startNodeEventStream
  } from '../stores/nodes.js';
  import { NodesAPI, ServersAPI } from '../lib/api.js';

  import Card from '../lib/components/Card.svelte';
  import Button from '../lib/components/Button.svelte';
  import Modal from '../lib/components/Modal.svelte';
  import LoadingSpinner from '../lib/components/LoadingSpinner.svelte';
  import StatusBadge from '../lib/components/StatusBadge.svelte';
  import Terminal from '../lib/components/Terminal.svelte';
  import {
    Cpu,
    MemoryStick,
    HardDrive,
    Activity,
    TerminalSquare,
    Send,
    History,
    FileText
  } from 'lucide-svelte';

  let loading = $state(false);
  let terminalOpen = $state({ open: false, serverId: null, serverName: '' });
  let commandOpen = $state({ open: false, serverId: null, serverName: '' });
  let logsOpen = $state({ open: false, serverId: null, serverName: '' });
  let commandsOpen = $state({ open: false, serverId: null, serverName: '' });

  let commandForm = $state({ command: 'status', args: '{}', timeout: 60 });
  let commandLog = $state([]);
  let logsData = $state([]);
  let commandsData = $state([]);
  let metricTimer = null;

  onMount(async () => {
    loading = true;
    startNodeEventStream();
    try {
      await loadNodes();
      startMetricPolling();
    } finally {
      loading = false;
    }
  });

  onDestroy(() => {
    if (metricTimer) clearInterval(metricTimer);
  });

  function startMetricPolling() {
    if (metricTimer) clearInterval(metricTimer);
    metricTimer = setInterval(async () => {
      for (const n of $nodes) {
        try {
          const latest = await NodesAPI.latestMetric(n.server_id);
          if (latest) {
            nodes.update((arr) =>
              arr.map((x) => (x.server_id === n.server_id ? { ...x, latest } : x))
            );
          }
        } catch (err) {
          /* noop */
        }
      }
    }, 5000);
  }

  function openTerminal(n) {
    terminalOpen = { open: true, serverId: n.server_id, serverName: n.server_name || `server-${n.server_id}` };
  }

  async function openCommand(n) {
    commandOpen = { open: true, serverId: n.server_id, serverName: n.server_name || `server-${n.server_id}` };
    commandLog = [];
  }

  async function sendCommand() {
    let args = {};
    try {
      args = commandForm.args ? JSON.parse(commandForm.args) : {};
    } catch (err) {
      toast.error('Invalid JSON in args');
      return;
    }
    try {
      const ack = await NodesAPI.command(commandOpen.serverId, {
        command: commandForm.command,
        args,
        timeout: Number(commandForm.timeout) || 60
      });
      commandLog = [...commandLog, { type: 'ack', payload: ack }];
      // poll the command list to fetch the result
      const list = await NodesAPI.commands(commandOpen.serverId, { limit: 1 });
      if (list && list[0]) {
        commandLog = [...commandLog, { type: 'result', payload: list[0] }];
      }
    } catch (err) {
      commandLog = [...commandLog, { type: 'error', payload: err?.response?.data || { error: err.message } }];
    }
  }

  async function openLogs(n) {
    logsOpen = { open: true, serverId: n.server_id, serverName: n.server_name };
    try {
      logsData = await NodesAPI.logs(n.server_id, { since_minutes: 30, limit: 200 });
    } catch (err) {
      toast.error('failed to fetch logs');
    }
  }

  async function openCommands(n) {
    commandsOpen = { open: true, serverId: n.server_id, serverName: n.server_name };
    try {
      commandsData = await NodesAPI.commands(n.server_id, { limit: 50 });
    } catch (err) {
      toast.error('failed to fetch commands');
    }
  }

  function fmtPercent(value) {
    return value == null ? '—' : `${value.toFixed(1)}%`;
  }
  function fmtBytes(n) {
    if (n == null) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    let v = n;
    while (v >= 1024 && i < units.length - 1) {
      v /= 1024;
      i += 1;
    }
    return `${v.toFixed(1)} ${units[i]}`;
  }
</script>

<div class="space-y-5">
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold text-slate-100">{$_('nodes.title')}</h1>
      <p class="text-sm text-slate-400 mt-1">نمایش و کنترل agent های نصب شده بر روی سرورها</p>
    </div>
    <Button variant="secondary" onclick={async () => { await loadNodes(); }}>
      <Activity class="w-4 h-4" /> بروزرسانی
    </Button>
  </div>

  {#if loading}
    <LoadingSpinner centered />
  {:else if $nodes.length === 0}
    <Card>
      <p class="text-center py-6 text-slate-500">
        هنوز نودی نصب نشده. از بخش «سرورها» اقدام کنید.
      </p>
    </Card>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {#each $nodes as n (n.server_id)}
        <div class="card">
          <div class="flex items-start justify-between gap-2 mb-3">
            <div>
              <h3 class="font-semibold text-slate-100">{n.server_name}</h3>
              <p class="text-xs text-slate-500 font-mono">{n.host}</p>
              <p class="text-xs text-slate-400">
                node: <span class="font-mono">{n.node_name || '—'}</span>
                · {n.node_location || '—'}
                · v{n.node_version || '?'}
              </p>
            </div>
            <StatusBadge status={n.online ? 'online' : (n.node_status || 'offline')} />
          </div>

          {#if n.latest}
            <div class="grid grid-cols-3 gap-2 text-center text-xs">
              <div class="bg-slate-800/60 rounded p-2">
                <Cpu class="w-4 h-4 mx-auto mb-1 text-primary-400" />
                <div class="font-mono text-slate-100">{fmtPercent(n.latest.cpu_percent)}</div>
              </div>
              <div class="bg-slate-800/60 rounded p-2">
                <MemoryStick class="w-4 h-4 mx-auto mb-1 text-amber-400" />
                <div class="font-mono text-slate-100">{fmtPercent(n.latest.ram_percent)}</div>
                <div class="text-[10px] text-slate-500">{n.latest.ram_used_mb}/{n.latest.ram_total_mb} MB</div>
              </div>
              <div class="bg-slate-800/60 rounded p-2">
                <HardDrive class="w-4 h-4 mx-auto mb-1 text-emerald-400" />
                <div class="font-mono text-slate-100">{fmtPercent(n.latest.disk_percent)}</div>
                <div class="text-[10px] text-slate-500">{n.latest.disk_used_gb} GB</div>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-2 mt-2 text-xs text-slate-400">
              <div>↑ TX: <span class="font-mono text-slate-200">{fmtBytes(n.latest.network_tx_bytes)}</span></div>
              <div>↓ RX: <span class="font-mono text-slate-200">{fmtBytes(n.latest.network_rx_bytes)}</span></div>
              <div>load: <span class="font-mono text-slate-200">
                {n.latest.load_avg_1m?.toFixed(2)} / {n.latest.load_avg_5m?.toFixed(2)}
              </span></div>
              <div>up: <span class="font-mono text-slate-200">
                {Math.floor((n.latest.uptime_seconds || 0) / 3600)}h
              </span></div>
            </div>
          {:else}
            <p class="text-xs text-slate-500">{$_('nodes.metrics.no_data')}</p>
          {/if}

          <div class="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border-slate-800">
            <button class="btn-ghost text-xs" onclick={() => openTerminal(n)} disabled={!n.online}>
              <TerminalSquare class="w-3 h-3" /> ترمینال
            </button>
            <button class="btn-ghost text-xs" onclick={() => openCommand(n)} disabled={!n.online}>
              <Send class="w-3 h-3" /> ارسال دستور
            </button>
            <button class="btn-ghost text-xs" onclick={() => openLogs(n)} disabled={!n.node_installed}>
              <FileText class="w-3 h-3" /> {$_('nodes.actions.view_logs')}
            </button>
            <button class="btn-ghost text-xs" onclick={() => openCommands(n)}>
              <History class="w-3 h-3" /> {$_('nodes.actions.view_commands')}
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<!-- ── Terminal modal ─────────────────────────────────────────────────── -->
<Modal
  open={terminalOpen.open}
  onclose={() => (terminalOpen = { open: false })}
  title={`${$_('nodes.terminal.title')} — ${terminalOpen.serverName}`}
  size="xl"
>
  <div style="height: 480px;">
    <Terminal
      url={
        ServersAPI.terminalUrl(terminalOpen.serverId) +
        `&token=${encodeURIComponent(getToken() || '')}`
      }
      cols={80}
      rows={24}
    />
  </div>
  {#snippet footer()}
    <Button variant="ghost" onclick={() => (terminalOpen = { open: false })}>بستن</Button>
  {/snippet}
</Modal>

<!-- ── Command modal ──────────────────────────────────────────────────── -->
<Modal
  open={commandOpen.open}
  onclose={() => (commandOpen = { open: false })}
  title={`${$_('nodes.actions.send_command')} — ${commandOpen.serverName}`}
  size="lg"
>
  <div class="space-y-3">
    <label class="block">
      <span class="label">{$_('nodes.fields.command')}</span>
      <input class="input font-mono" bind:value={commandForm.command} />
    </label>
    <label class="block">
      <span class="label">{$_('nodes.fields.args')}</span>
      <textarea bind:value={commandForm.args} rows="4" class="input font-mono text-xs"></textarea>
    </label>
    <label class="block">
      <span class="label">{$_('nodes.fields.timeout')}</span>
      <input class="input" type="number" bind:value={commandForm.timeout} />
    </label>
    <div class="bg-slate-950 border border-slate-800 rounded-lg p-3 max-h-72 overflow-y-auto font-mono text-xs whitespace-pre-wrap text-slate-200">
      {#each commandLog as entry}
        <div class="mb-2">
          <span class={entry.type === 'error' ? 'text-red-400' : 'text-emerald-400'}>
            [{entry.type}]
          </span>
          <pre class="inline whitespace-pre-wrap">{JSON.stringify(entry.payload, null, 2)}</pre>
        </div>
      {/each}
    </div>
  </div>
  {#snippet footer()}
    <Button variant="ghost" onclick={() => (commandOpen = { open: false })}>بستن</Button>
    <Button onclick={sendCommand}><Send class="w-3 h-3" /> ارسال</Button>
  {/snippet}
</Modal>

<!-- ── Logs modal ─────────────────────────────────────────────────────── -->
<Modal
  open={logsOpen.open}
  onclose={() => (logsOpen = { open: false })}
  title={`${$_('nodes.actions.view_logs')} — ${logsOpen.serverName}`}
  size="lg"
>
  <div class="bg-slate-950 border border-slate-800 rounded-lg p-3 h-96 overflow-y-auto font-mono text-xs whitespace-pre-wrap text-slate-200">
    {#each logsData as l}
      <div class="flex gap-2">
        <span class="text-slate-500">{new Date(l.timestamp).toLocaleTimeString()}</span>
        <span class={
          l.level === 'error' ? 'text-red-400' :
          l.level === 'warn'  ? 'text-amber-400' :
          l.level === 'debug' ? 'text-slate-500' : 'text-slate-300'
        }>[{l.level}]</span>
        <span class="flex-1 break-all">{l.message}</span>
      </div>
    {/each}
    {#if logsData.length === 0}
      <div class="text-slate-500">{$_('nodes.metrics.no_data')}</div>
    {/if}
  </div>
  {#snippet footer()}
    <Button variant="ghost" onclick={() => (logsOpen = { open: false })}>بستن</Button>
  {/snippet}
</Modal>

<!-- ── Commands history modal ─────────────────────────────────────────── -->
<Modal
  open={commandsOpen.open}
  onclose={() => (commandsOpen = { open: false })}
  title={`${$_('nodes.actions.view_commands')} — ${commandsOpen.serverName}`}
  size="lg"
>
  <div class="space-y-2 max-h-96 overflow-y-auto">
    {#each commandsData as c}
      <div class="border border-slate-800 rounded-lg p-3 text-xs">
        <div class="flex items-center justify-between mb-1">
          <span class="font-mono text-slate-100">{c.command}</span>
          <span class={
            c.status === 'success' ? 'text-emerald-400' :
            c.status === 'failed'  ? 'text-red-400' : 'text-amber-400'
          }>{c.status}</span>
        </div>
        <div class="text-slate-500">{new Date(c.issued_at).toLocaleString()}</div>
        {#if c.stdout}
          <pre class="bg-slate-950 p-2 mt-1 rounded text-slate-200 whitespace-pre-wrap">{c.stdout}</pre>
        {/if}
        {#if c.stderr}
          <pre class="bg-red-950/40 p-2 mt-1 rounded text-red-200 whitespace-pre-wrap">{c.stderr}</pre>
        {/if}
      </div>
    {/each}
    {#if commandsData.length === 0}
      <div class="text-slate-500">{$_('nodes.metrics.no_data')}</div>
    {/if}
  </div>
  {#snippet footer()}
    <Button variant="ghost" onclick={() => (commandsOpen = { open: false })}>بستن</Button>
  {/snippet}
</Modal>