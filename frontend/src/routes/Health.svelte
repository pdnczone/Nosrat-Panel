<script>
  import { onMount, onDestroy } from 'svelte';
  import { _ } from '../lib/i18n.js';
  import { HealthAPI } from '../lib/api.js';
  import Card from '../lib/components/Card.svelte';
  import ChartCard from '../lib/components/ChartCard.svelte';
  import Button from '../lib/components/Button.svelte';
  import LoadingSpinner from '../lib/components/LoadingSpinner.svelte';
  import { toast } from '../lib/toast.js';
  import { Cpu, MemoryStick, HardDrive, Network, Activity, AlertCircle, RefreshCw } from 'lucide-svelte';

  let activeTab = $state('quick');
  let quick = $state(null);
  let detailed = $state(null);
  let monitoringHistory = $state({ cpu: [], mem: [], net_rx: [], net_tx: [] });
  let loading = $state(true);
  let monitoringInterval = $state(5);

  let timer;
  onMount(async () => {
    await loadAll();
    timer = setInterval(refreshMonitoring, monitoringInterval * 1000);
  });

  onDestroy(() => {
    if (timer) clearInterval(timer);
  });

  async function loadAll() {
    loading = true;
    try {
      [quick, detailed] = await Promise.all([
        HealthAPI.quick(),
        HealthAPI.detailed()
      ]);
    } finally {
      loading = false;
    }
  }

  async function refreshMonitoring() {
    try {
      const data = await HealthAPI.monitoring({ limit: 1 });
      const m = data?.items?.[0] || data;
      if (m) {
        monitoringHistory = {
          cpu: [...monitoringHistory.cpu, m.cpu ?? 0].slice(-30),
          mem: [...monitoringHistory.mem, m.memory ?? 0].slice(-30),
          net_rx: [...monitoringHistory.net_rx, m.net_rx ?? 0].slice(-30),
          net_tx: [...monitoringHistory.net_tx, m.net_tx ?? 0].slice(-30)
        };
      }
    } catch (_) {}
  }

  const cpuChart = $derived({
    labels: monitoringHistory.cpu.map((_, i) => `${i + 1}`),
    datasets: [{ label: 'CPU %', data: monitoringHistory.cpu, borderColor: '#22d3ee', tension: 0.3, fill: true, backgroundColor: 'rgba(34, 211, 238, 0.1)' }]
  });

  const memChart = $derived({
    labels: monitoringHistory.mem.map((_, i) => `${i + 1}`),
    datasets: [{ label: 'Memory %', data: monitoringHistory.mem, borderColor: '#a78bfa', tension: 0.3, fill: true, backgroundColor: 'rgba(167, 139, 250, 0.1)' }]
  });

  const netChart = $derived({
    labels: monitoringHistory.net_rx.map((_, i) => `${i + 1}`),
    datasets: [
      { label: 'RX (KB/s)', data: monitoringHistory.net_rx, borderColor: '#34d399', tension: 0.3 },
      { label: 'TX (KB/s)', data: monitoringHistory.net_tx, borderColor: '#f59e0b', tension: 0.3 }
    ]
  });

  const TABS = ['quick', 'detailed', 'monitoring'];

  function pct(v) {
    if (v == null) return 0;
    return Math.min(100, Math.max(0, Number(v)));
  }
  function barColor(v) {
    if (v > 80) return 'bg-red-500';
    if (v > 60) return 'bg-amber-500';
    return 'bg-emerald-500';
  }
</script>

<div class="space-y-5">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-bold text-slate-100">{$_('health.title')}</h1>
    <Button variant="ghost" onclick={loadAll}>
      {#snippet icon()}<RefreshCw class="w-4 h-4" />{/snippet}
      {$_('common.refresh')}
    </Button>
  </div>

  <div class="border-b border-slate-800 flex gap-1">
    {#each TABS as t}
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors {activeTab === t ? 'border-primary-500 text-primary-400' : 'border-transparent text-slate-400 hover:text-slate-200'}"
        onclick={() => (activeTab = t)}
      >{$_(`health.tabs.${t}`)}</button>
    {/each}
  </div>

  {#if loading}
    <LoadingSpinner centered />
  {:else if activeTab === 'quick'}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <Card>
        <div class="flex items-center gap-3 mb-2"><Cpu class="w-5 h-5 text-primary-400" /><span class="text-sm text-slate-400">{$_('health.metrics.cpu')}</span></div>
        <div class="text-3xl font-bold text-slate-100">{quick?.cpu ?? 0}%</div>
        <div class="mt-3 h-2 bg-slate-800 rounded-full overflow-hidden">
          <div class="h-full {barColor(quick?.cpu ?? 0)} transition-all" style="width: {pct(quick?.cpu)}%"></div>
        </div>
      </Card>
      <Card>
        <div class="flex items-center gap-3 mb-2"><MemoryStick class="w-5 h-5 text-purple-400" /><span class="text-sm text-slate-400">{$_('health.metrics.memory')}</span></div>
        <div class="text-3xl font-bold text-slate-100">{quick?.memory ?? 0}%</div>
        <div class="mt-3 h-2 bg-slate-800 rounded-full overflow-hidden">
          <div class="h-full {barColor(quick?.memory ?? 0)} transition-all" style="width: {pct(quick?.memory)}%"></div>
        </div>
      </Card>
      <Card>
        <div class="flex items-center gap-3 mb-2"><HardDrive class="w-5 h-5 text-emerald-400" /><span class="text-sm text-slate-400">{$_('health.metrics.disk')}</span></div>
        <div class="text-3xl font-bold text-slate-100">{quick?.disk ?? 0}%</div>
        <div class="mt-3 h-2 bg-slate-800 rounded-full overflow-hidden">
          <div class="h-full {barColor(quick?.disk ?? 0)} transition-all" style="width: {pct(quick?.disk)}%"></div>
        </div>
      </Card>
      <Card>
        <div class="flex items-center gap-3 mb-2"><Network class="w-5 h-5 text-cyan-400" /><span class="text-sm text-slate-400">{$_('health.metrics.network')}</span></div>
        <div class="text-3xl font-bold text-slate-100">{quick?.connections ?? 0}</div>
        <p class="text-xs text-slate-500 mt-2">{$_('health.metrics.connections')}</p>
      </Card>
    </div>
  {:else if activeTab === 'detailed'}
    <Card title={$_('health.metrics.load')}>
      <pre class="text-xs font-mono text-slate-300 overflow-x-auto bg-slate-950 p-4 rounded-lg">{JSON.stringify(detailed ?? {}, null, 2)}</pre>
    </Card>
  {:else if activeTab === 'monitoring'}
    <div class="flex items-center gap-3 mb-3">
      <label class="text-sm text-slate-400">{$_('health.interval')}:</label>
      <input type="number" bind:value={monitoringInterval} min="1" max="60" class="input w-20" />
      <span class="text-sm text-slate-500">{$_('common.seconds')}</span>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <ChartCard title="CPU" data={cpuChart} type="line" />
      <ChartCard title="Memory" data={memChart} type="line" />
      <div class="lg:col-span-2">
        <ChartCard title="Network" data={netChart} type="line" />
      </div>
    </div>
  {/if}
</div>
