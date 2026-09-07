<script>
  import { onMount, onDestroy } from 'svelte';
  import { _ } from '../lib/i18n.js';
  import { auth } from '../lib/auth.js';
  import { StatsAPI, TunnelsAPI } from '../lib/api.js';
  import { wsMessages } from '../lib/ws.js';
  import Card from '../lib/components/Card.svelte';
  import ChartCard from '../lib/components/ChartCard.svelte';
  import TunnelCard from '../lib/components/TunnelCard.svelte';
  import StatusBadge from '../lib/components/StatusBadge.svelte';
  import LoadingSpinner from '../lib/components/LoadingSpinner.svelte';
  import { Plus, Activity, Gauge, Zap, Network, AlertTriangle, CheckCircle } from 'lucide-svelte';

  let { onNavigate = () => {} } = $props();

  let stats = $state(null);
  let activity = $state([]);
  let tunnels = $state([]);
  let loading = $state(true);

  const wsEvents = wsMessages('/ws/events');
  let realtimeTraffic = $state({ rx: 0, tx: 0, history: [] });

  $effect(() => {
    const last = $wsEvents[$wsEvents.length - 1];
    if (!last) return;
    if (last.type === 'traffic') {
      realtimeTraffic = last.payload;
      realtimeTraffic.history = [...realtimeTraffic.history, last.payload].slice(-30);
    } else if (last.type === 'tunnel_update') {
      tunnels = tunnels.map((t) => (t.id === last.payload.id ? { ...t, ...last.payload } : t));
    }
  });

  onMount(async () => {
    try {
      const [s, a, t] = await Promise.allSettled([
        StatsAPI.dashboard(),
        StatsAPI.activity({ limit: 10 }),
        TunnelsAPI.list()
      ]);
      if (s.status === 'fulfilled') stats = s.value;
      if (a.status === 'fulfilled') activity = a.value.items || a.value || [];
      if (t.status === 'fulfilled') tunnels = Array.isArray(t.value) ? t.value : t.value.items || [];
    } finally {
      loading = false;
    }
  });

  const trafficChart = $derived({
    labels: realtimeTraffic.history.map((_, i) => `${i + 1}`),
    datasets: [
      {
        label: 'RX (MB/s)',
        data: realtimeTraffic.history.map((p) => p.rx),
        borderColor: '#34d399',
        backgroundColor: 'rgba(52, 211, 153, 0.1)',
        tension: 0.4,
        fill: true
      },
      {
        label: 'TX (MB/s)',
        data: realtimeTraffic.history.map((p) => p.tx),
        borderColor: '#22d3ee',
        backgroundColor: 'rgba(34, 211, 238, 0.1)',
        tension: 0.4,
        fill: true
      }
    ]
  });

  function fmt(num) {
    if (num == null) return '—';
    return Number(num).toLocaleString();
  }
</script>

<div class="space-y-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div>
      <h1 class="text-2xl font-bold text-slate-100">{$_('dashboard.welcome')}، {$auth.user?.username}</h1>
      <p class="text-sm text-slate-400 mt-1">{$_('dashboard.title')}</p>
    </div>
    <div class="flex gap-2">
      <button class="btn-secondary" onclick={() => onNavigate('/health')}>
        <Activity class="w-4 h-4" /> {$_('dashboard.run_health')}
      </button>
      <button class="btn-primary" onclick={() => onNavigate('/tunnels/create')}>
        <Plus class="w-4 h-4" /> {$_('dashboard.create_tunnel')}
      </button>
    </div>
  </div>

  {#if loading}
    <LoadingSpinner centered text={$_('common.loading')} />
  {:else}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {@const s = stats || {}}
      <div class="card">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs text-slate-500">{$_('dashboard.stats.total_tunnels')}</p>
            <p class="text-3xl font-bold text-slate-100 mt-1">{fmt(s.total_tunnels ?? tunnels.length)}</p>
          </div>
          <div class="w-12 h-12 rounded-lg bg-primary-500/15 text-primary-400 flex items-center justify-center">
            <Network class="w-6 h-6" />
          </div>
        </div>
      </div>

      <div class="card">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs text-slate-500">{$_('dashboard.stats.running')}</p>
            <p class="text-3xl font-bold text-emerald-400 mt-1">{fmt(s.running ?? tunnels.filter((t) => t.status === 'running').length)}</p>
          </div>
          <div class="w-12 h-12 rounded-lg bg-emerald-500/15 text-emerald-400 flex items-center justify-center">
            <CheckCircle class="w-6 h-6" />
          </div>
        </div>
      </div>

      <div class="card">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs text-slate-500">{$_('dashboard.stats.errors')}</p>
            <p class="text-3xl font-bold text-red-400 mt-1">{fmt(s.errors ?? tunnels.filter((t) => t.status === 'error').length)}</p>
          </div>
          <div class="w-12 h-12 rounded-lg bg-red-500/15 text-red-400 flex items-center justify-center">
            <AlertTriangle class="w-6 h-6" />
          </div>
        </div>
      </div>

      <div class="card">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs text-slate-500">{$_('dashboard.stats.traffic')}</p>
            <p class="text-3xl font-bold text-cyan-400 mt-1">{s.traffic ?? '0 GB'}</p>
          </div>
          <div class="w-12 h-12 rounded-lg bg-cyan-500/15 text-cyan-400 flex items-center justify-center">
            <Zap class="w-6 h-6" />
          </div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2 space-y-6">
        <ChartCard title={$_('tunnels.detail.traffic_chart')} data={trafficChart} type="line" />

        <Card title={$_('dashboard.tunnel_grid')} subtitle={`${tunnels.length} ${$_('nav.tunnels')}`}>
          {#if tunnels.length === 0}
            <div class="text-center py-10">
              <p class="text-slate-500 mb-4">{$_('dashboard.no_tunnels')}</p>
              <button class="btn-primary" onclick={() => onNavigate('/tunnels/create')}>
                <Plus class="w-4 h-4" /> {$_('dashboard.create_tunnel')}
              </button>
            </div>
          {:else}
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {#each tunnels.slice(0, 6) as t}
                <TunnelCard tunnel={t} />
              {/each}
            </div>
          {/if}
        </Card>
      </div>

      <Card title={$_('dashboard.activity')}>
        {#if activity.length === 0}
          <p class="text-slate-500 text-sm text-center py-6">{$_('common.empty')}</p>
        {:else}
          <ul class="space-y-3">
            {#each activity as a}
              <li class="flex items-start gap-3 pb-3 border-b border-slate-800 last:border-0">
                <div class="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center flex-shrink-0">
                  {#if a.level === 'error'}<AlertTriangle class="w-4 h-4 text-red-400" />{:else}<Activity class="w-4 h-4 text-primary-400" />{/if}
                </div>
                <div class="min-w-0 flex-1">
                  <p class="text-sm text-slate-200">{a.message || a.action}</p>
                  <p class="text-xs text-slate-500 mt-0.5">{a.created_at || a.time}</p>
                </div>
              </li>
            {/each}
          </ul>
        {/if}
      </Card>
    </div>
  {/if}
</div>
