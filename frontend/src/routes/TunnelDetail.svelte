<script>
  import { onMount, onDestroy } from 'svelte';
  import { _ } from '../lib/i18n.js';
  import { TunnelsAPI, HealthAPI, SpeedAPI, CryptoAPI } from '../lib/api.js';
  import { wsMessages, closeChannel } from '../lib/ws.js';
  import Card from '../lib/components/Card.svelte';
  import Button from '../lib/components/Button.svelte';
  import StatusBadge from '../lib/components/StatusBadge.svelte';
  import ChartCard from '../lib/components/ChartCard.svelte';
  import QRCode from '../lib/components/QRCode.svelte';
  import Modal from '../lib/components/Modal.svelte';
  import LoadingSpinner from '../lib/components/LoadingSpinner.svelte';
  import { ArrowLeft, Play, Square, RotateCw, Trash2, Copy, QrCode, RefreshCw, Network, Activity, Gauge, Lock, Server as ServerIcon } from 'lucide-svelte';
  import { toast } from '../lib/toast.js';

  let { id, onNavigate = () => {} } = $props();

  let tunnel = $state(null);
  let loading = $state(true);
  let activeTab = $state('overview');
  let logs = $state([]);
  let status = $state(null);
  let health = $state(null);
  let speed = $state(null);
  let crypto = $state(null);
  let qrOpen = $state(false);
  let autoRefresh = $state(true);
  let trafficHistory = $state([]);

  const wsChannel = `/ws/tunnels/${id}`;
  const ws = wsMessages(wsChannel);

  $effect(() => {
    const last = $ws[$ws.length - 1];
    if (!last) return;
    if (last.type === 'log') logs = [...logs, last.payload].slice(-500);
    if (last.type === 'status') status = last.payload;
    if (last.type === 'traffic') trafficHistory = [...trafficHistory, last.payload].slice(-30);
  });

  let refreshTimer;
  onMount(async () => {
    await load();
    refreshTimer = setInterval(() => { if (autoRefresh) refresh(); }, 5000);
  });

  onDestroy(() => {
    if (refreshTimer) clearInterval(refreshTimer);
    closeChannel(wsChannel);
  });

  async function load() {
    try {
      tunnel = await TunnelsAPI.get(id);
    } catch (e) {
      tunnel = null;
    } finally {
      loading = false;
    }
  }

  async function refresh() {
    if (!id) return;
    try {
      status = await TunnelsAPI.status(id);
      const logsData = await TunnelsAPI.logs(id, { tail: 100 });
      logs = Array.isArray(logsData) ? logsData : logsData.items || [];
    } catch (_) {}
  }

  async function loadTab() {
    if (activeTab === 'health') health = await HealthAPI.tunnel(id).catch(() => null);
    if (activeTab === 'speed') speed = await SpeedAPI.history({ tunnel_id: id, limit: 5 }).catch(() => null);
    if (activeTab === 'crypto' && tunnel?.psk_id) crypto = await CryptoAPI.pskList().catch(() => null);
  }

  $effect(() => { activeTab; loadTab(); });

  const trafficChart = $derived({
    labels: trafficHistory.map((_, i) => `${i + 1}`),
    datasets: [
      { label: 'RX', data: trafficHistory.map((p) => p.rx), borderColor: '#34d399', tension: 0.4 },
      { label: 'TX', data: trafficHistory.map((p) => p.tx), borderColor: '#22d3ee', tension: 0.4 }
    ]
  });

  async function action(cmd) {
    if (cmd === 'start') await TunnelsAPI.start(id);
    if (cmd === 'stop') await TunnelsAPI.stop(id);
    if (cmd === 'restart') await TunnelsAPI.restart(id);
    await refresh();
  }

  async function remove() {
    if (!confirm($_('tunnels.delete_confirm'))) return;
    await TunnelsAPI.delete(id);
    toast.success($_('common.delete'));
    onNavigate('/tunnels');
  }

  function copy(text, label) {
    navigator.clipboard?.writeText(text || '');
    toast.success($_('common.copied'));
  }

  const TABS = ['overview', 'status', 'logs', 'crypto', 'health', 'speed'];
</script>

{#if loading}
  <LoadingSpinner centered />
{:else if !tunnel}
  <Card title={$_('tunnels.detail.not_found')}>
    <Button onclick={() => onNavigate('/tunnels')}>
      {#snippet icon()}<ArrowLeft class="w-4 h-4" />{/snippet}
      {$_('common.back')}
    </Button>
  </Card>
{:else}
  <div class="space-y-5">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <button class="btn-ghost text-sm mb-2" onclick={() => onNavigate('/tunnels')}>
          <ArrowLeft class="w-4 h-4" /> {$_('common.back')}
        </button>
        <h1 class="text-2xl font-bold text-slate-100 flex items-center gap-3">
          {tunnel.name}
          <StatusBadge status={status?.status ?? tunnel.status} />
        </h1>
        <p class="text-sm text-slate-400 mt-1">
          <span class="badge bg-slate-800 text-slate-300 me-2">{tunnel.type}</span>
          {tunnel.server ?? '—'}
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <Button variant="ghost" onclick={() => (qrOpen = true)}>{#snippet icon()}<QrCode class="w-4 h-4" />{/snippet}QR</Button>
        <Button variant="secondary" onclick={() => action('start')}>{#snippet icon()}<Play class="w-4 h-4" />{/snippet}{$_(`tunnels.actions.start`)}</Button>
        <Button variant="secondary" onclick={() => action('stop')}>{#snippet icon()}<Square class="w-4 h-4" />{/snippet}{$_(`tunnels.actions.stop`)}</Button>
        <Button variant="secondary" onclick={() => action('restart')}>{#snippet icon()}<RotateCw class="w-4 h-4" />{/snippet}{$_(`tunnels.actions.restart`)}</Button>
        <Button variant="danger" onclick={remove}>{#snippet icon()}<Trash2 class="w-4 h-4" />{/snippet}{$_(`common.delete`)}</Button>
      </div>
    </div>

    <div class="border-b border-slate-800 flex gap-1 overflow-x-auto">
      {#each TABS as t}
        <button
          class="px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap {activeTab === t ? 'border-primary-500 text-primary-400' : 'border-transparent text-slate-400 hover:text-slate-200'}"
          onclick={() => (activeTab = t)}
        >{$_(`tunnels.detail.tabs.${t}`)}</button>
      {/each}
    </div>

    {#if activeTab === 'overview'}
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div class="lg:col-span-2 space-y-5">
          <ChartCard title={$_('tunnels.detail.traffic_chart')} data={trafficChart} type="line" />
          <Card title={$_('tunnels.detail.info')}>
            <dl class="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
              {#each Object.entries(tunnel) as [k, v]}
                {#if !['logs','history'].includes(k) && typeof v !== 'object'}
                  <div>
                    <dt class="text-slate-500 text-xs">{k}</dt>
                    <dd class="text-slate-200 font-mono mt-0.5 break-all">{String(v)}</dd>
                  </div>
                {/if}
              {/each}
            </dl>
          </Card>
        </div>
        <Card title={$_('tunnels.detail.live_status')}>
          <div class="space-y-3">
            {#if status}
              <div class="flex justify-between"><span class="text-slate-400">{$_('tunnels.columns.status')}</span><StatusBadge status={status.status} /></div>
              <div class="flex justify-between"><span class="text-slate-400">{$_('tunnels.columns.latency')}</span><span class="font-mono text-slate-200">{status.latency ?? '—'}</span></div>
              <div class="flex justify-between"><span class="text-slate-400">RX</span><span class="font-mono text-emerald-300">{status.rx ?? '0'}</span></div>
              <div class="flex justify-between"><span class="text-slate-400">TX</span><span class="font-mono text-cyan-300">{status.tx ?? '0'}</span></div>
              <div class="flex justify-between"><span class="text-slate-400">Uptime</span><span class="font-mono text-slate-200">{status.uptime ?? '—'}</span></div>
              <div class="flex justify-between"><span class="text-slate-400">Peers</span><span class="font-mono text-slate-200">{status.peers ?? '—'}</span></div>
            {:else}
              <p class="text-slate-500 text-sm">{$_('common.loading')}</p>
            {/if}
          </div>
          <label class="flex items-center gap-2 mt-4 text-sm text-slate-400">
            <input type="checkbox" bind:checked={autoRefresh} class="rounded" />
            {$_('tunnels.detail.auto_refresh')}
          </label>
        </Card>
      </div>
    {:else if activeTab === 'status'}
      <Card title={$_('tunnels.detail.live_status')}>
        <pre class="text-xs font-mono text-slate-300 overflow-x-auto">{JSON.stringify(status ?? tunnel, null, 2)}</pre>
        <Button variant="ghost" onclick={refresh}>{#snippet icon()}<RefreshCw class="w-4 h-4" />{/snippet}{$_(`common.refresh`)}</Button>
      </Card>
    {:else if activeTab === 'logs'}
      <Card title={$_('tunnels.detail.logs_live')}>
        <div class="bg-slate-950 rounded-lg border border-slate-800 p-3 h-96 overflow-y-auto font-mono text-xs">
          {#each logs as line, i}
            <div class="text-slate-300 leading-5">
              <span class="text-slate-600">{String(i).padStart(4, '0')}</span>
              <span class="ms-2">{line.message || line}</span>
            </div>
          {:else}
            <p class="text-slate-500">{$_('common.empty')}</p>
          {/each}
        </div>
      </Card>
    {:else if activeTab === 'crypto'}
      <Card title={$_('crypto.title')}>
        <pre class="text-xs font-mono text-slate-300 overflow-x-auto">{JSON.stringify(crypto ?? { psk_id: tunnel.psk_id, algorithm: tunnel.algorithm }, null, 2)}</pre>
      </Card>
    {:else if activeTab === 'health'}
      <Card title={$_('nav.health')}>
        <pre class="text-xs font-mono text-slate-300 overflow-x-auto">{JSON.stringify(health ?? {}, null, 2)}</pre>
      </Card>
    {:else if activeTab === 'speed'}
      <Card title={$_('nav.speed')}>
        <pre class="text-xs font-mono text-slate-300 overflow-x-auto">{JSON.stringify(speed ?? {}, null, 2)}</pre>
      </Card>
    {/if}
  </div>

  <Modal bind:open={qrOpen} title="QR Code" size="sm">
    <div class="flex justify-center">
      <QRCode data={JSON.stringify({ name: tunnel.name, type: tunnel.type, server: tunnel.server })} size={220} />
    </div>
  </Modal>
{/if}
