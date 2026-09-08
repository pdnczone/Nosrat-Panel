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
  import { api } from '../lib/api.js';
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
  import Input from '../lib/components/Input.svelte';
  import {
    Cpu,
    MemoryStick,
    HardDrive,
    Activity,
    TerminalSquare,
    Send,
    History,
    FileText,
    Plus
  } from 'lucide-svelte';

  let loading = $state(false);
  let terminalOpen = $state({ open: false, serverId: null, serverName: '' });
  let commandOpen = $state({ open: false, serverId: null, serverName: '' });
  let logsOpen = $state({ open: false, serverId: null, serverName: '' });
  let commandsOpen = $state({ open: false, serverId: null, serverName: '' });
  let addNodeOpen = $state(false);
  let addNodeForm = $state({ name: '', host: '', ssh_port: 22, ssh_user: 'root', node_name: '', node_location: 'external' });
  let addNodeLoading = $state(false);

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

  async function addNode() {
    addNodeLoading = true;
    try {
      const payload = { ...addNodeForm };
      if (!payload.node_name) delete payload.node_name;
      if (payload.node_location === 'external' && !payload.node_name) {
        payload.node_name = payload.name;
      }
      await api.post('/nodes', payload);
      toast.success('نود اضافه شد');
      addNodeOpen = false;
      addNodeForm = { name: '', host: '', ssh_port: 22, ssh_user: 'root', node_name: '', node_location: 'external' };
      await loadNodes();
    } catch (err) {
      toast.error(err?.response?.data?.error || err.message);
    } finally {
      addNodeLoading = false;
    }
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
    <div class="flex gap-2">
      <Button variant="secondary" onclick={async () => { await loadNodes(); }}>
        <Activity class="w-4 h-4" /> بروزرسانی
      </Button>
      <Button onclick={() => (addNodeOpen = true)}>
        <Plus class="w-4 h-4" /> اضافه کردن نود
      </Button>
    </div>
  </div>

  {#if loading}
    <LoadingSpinner centered />
  {:else if $nodes.length === 0}
    <Card>
      <div class="text-center py-6">
        <p class="text-slate-500 mb-4">هنوز نودی نصب نشده.</p>
        <Button onclick={() => (addNodeOpen = true)}>
          <Plus class="w-4 h-4" /> اضافه کردن نود
        </Button>
      </div>
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
                · loc: {n.node_location || '—'}
              </p>
            </div>
            <StatusBadge status={n.online ? 'online' : 'offline'} />
          </div>

          {#if n.latest}
            <div class="grid grid-cols-3 gap-2 text-xs mb-3">
              <div>
                <Cpu class="w-3.5 h-3.5 text-slate-500" />
                <span class="text-slate-300">{fmtPercent(n.latest.cpu_percent)}</span>
              </div>
              <div>
                <MemoryStick class="w-3.5 h-3.5 text-slate-500" />
                <span class="text-slate-300">{fmtPercent(n.latest.memory_percent)}</span>
              </div>
              <div>
                <HardDrive class="w-3.5 h-3.5 text-slate-500" />
                <span class="text-slate-300">{fmtBytes(n.latest.disk_used)}</span>
              </div>
            </div>
          {/if}

          <div class="flex gap-2 flex-wrap">
            {#if n.online}
              <button class="btn-sm" onclick={() => openTerminal(n)}>
                <TerminalSquare class="w-3.5 h-3.5" /> ترمینال
              </button>
              <button class="btn-sm" onclick={() => openCommand(n)}>
                <Send class="w-3.5 h-3.5" /> دستور
              </button>
              <button class="btn-sm" onclick={() => openLogs(n)}>
                <FileText class="w-3.5 h-3.5" /> لاگ
              </button>
              <button class="btn-sm" onclick={() => openCommands(n)}>
                <History class="w-3.5 h-3.5" /> تاریخچه
              </button>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<!-- Add Node Modal -->
<Modal bind:open={addNodeOpen} title="اضافه کردن نود">
  <div class="space-y-4">
    <Input label="نام سرور" bind:value={addNodeForm.name} placeholder="e.g. iran-server-1" />
    <Input label="آیپی / هاست" bind:value={addNodeForm.host} placeholder="1.2.3.4" />
    <div class="grid grid-cols-2 gap-4">
      <Input label="SSH Port" type="number" bind:value={addNodeForm.ssh_port} />
      <Input label="SSH User" bind:value={addNodeForm.ssh_user} />
    </div>
    <Input label="نام نود (اختیاری)" bind:value={addNodeForm.node_name} placeholder="e.g. node-1" />
    <Input label="لوکیشن" bind:value={addNodeForm.node_location} placeholder="e.g. iran, external" />
  </div>

  {#snippet actions()}
    <Button variant="secondary" onclick={() => (addNodeOpen = false)}>انصراف</Button>
    <Button onclick={addNode} disabled={addNodeLoading || !addNodeForm.name || !addNodeForm.host}>
      {addNodeLoading ? 'در حال اضافه کردن...' : 'اضافه کردن'}
    </Button>
  {/snippet}
</Modal>

<!-- Terminal Modal -->
{#if terminalOpen.open}
  <Terminal serverId={terminalOpen.serverId} serverName={terminalOpen.serverName} bind:open={terminalOpen.open} />
{/if}

<!-- Command Modal -->
<Modal bind:open={commandOpen.open} title="ارسال دستور — {commandOpen.serverName}">
  <div class="space-y-3">
    <Input label="دستور" bind:value={commandForm.command} placeholder="status" />
    <Input label="آرگومان‌ها (JSON)" bind:value={commandForm.args} placeholder="empty for none" />
    <Input label="تایم‌اوت (ثانیه)" type="number" bind:value={commandForm.timeout} />
    <Button onclick={sendCommand}>ارسال</Button>
    {#if commandLog.length}
      <pre class="bg-slate-900 p-3 rounded text-xs text-slate-300 overflow-auto max-h-60">{JSON.stringify(commandLog, null, 2)}</pre>
    {/if}
  </div>
</Modal>

<!-- Logs Modal -->
<Modal bind:open={logsOpen.open} title="لاگ نود — {logsOpen.serverName}">
  <div class="max-h-96 overflow-auto">
    {#if logsData.length}
      <pre class="bg-slate-900 p-3 rounded text-xs text-slate-300">{logsData.map(l => `${l.timestamp} ${l.message}`).join('\n')}</pre>
    {:else}
      <p class="text-slate-500 text-sm">لاگی یافت نشد.</p>
    {/if}
  </div>
</Modal>

<!-- Commands History Modal -->
<Modal bind:open={commandsOpen.open} title="تاریخچه دستورات — {commandsOpen.serverName}">
  <div class="max-h-96 overflow-auto space-y-2">
    {#if commandsData.length}
      {#each commandsData as cmd}
        <div class="bg-slate-900 p-3 rounded text-xs">
          <span class="text-slate-400">{cmd.timestamp}</span>
          <span class="text-blue-400 font-mono">{cmd.command}</span>
          <span class:text-green-400={cmd.status === 'success'} class:text-red-400={cmd.status === 'error'}>
            [{cmd.status}]
          </span>
        </div>
      {/each}
    {:else}
      <p class="text-slate-500 text-sm">دستوری اجرا نشده.</p>
    {/if}
  </div>
</Modal>
