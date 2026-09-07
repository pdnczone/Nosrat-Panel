<script>
  import { _ } from '../lib/i18n.js';
  import { SpeedAPI } from '../lib/api.js';
  import Card from '../lib/components/Card.svelte';
  import Button from '../lib/components/Button.svelte';
  import Input from '../lib/components/Input.svelte';
  import LoadingSpinner from '../lib/components/LoadingSpinner.svelte';
  import { toast } from '../lib/toast.js';
  import { Play, History } from 'lucide-svelte';

  let activeTab = $state('ping');
  let target = $state('1.1.1.1');
  let packetCount = $state(10);
  let duration = $state(10);
  let parallel = $state(1);
  let reverse = $state(false);
  let running = $state(false);
  let result = $state(null);
  let history = $state([]);

  const TABS = ['ping', 'full', 'iperf3'];

  async function run() {
    if (!target) { toast.warning($_('speed.target')); return; }
    running = true;
    result = null;
    try {
      if (activeTab === 'ping') result = await SpeedAPI.ping(target);
      else if (activeTab === 'full') result = await SpeedAPI.full(target);
      else if (activeTab === 'iperf3') result = await SpeedAPI.iperf3(target, { duration, parallel, reverse });
      history = [result, ...history].slice(0, 10);
    } catch (e) {} finally {
      running = false;
    }
  }
</script>

<div class="space-y-5">
  <h1 class="text-2xl font-bold text-slate-100">{$_('speed.title')}</h1>

  <div class="border-b border-slate-800 flex gap-1">
    {#each TABS as t}
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors {activeTab === t ? 'border-primary-500 text-primary-400' : 'border-transparent text-slate-400 hover:text-slate-200'}"
        onclick={() => (activeTab = t)}
      >{$_(`speed.tabs.${t}`)}</button>
    {/each}
  </div>

  <Card>
    <div class="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
      <div class="md:col-span-2">
        <Input label={$_('speed.target')} bind:value={target} placeholder={$_('speed.target_placeholder')} required />
      </div>
      {#if activeTab === 'ping'}
        <Input label={$_('speed.packet_count')} type="number" bind:value={packetCount} />
      {:else if activeTab === 'iperf3'}
        <Input label={$_('speed.duration')} type="number" bind:value={duration} />
        <Input label={$_('speed.parallel')} type="number" bind:value={parallel} />
      {:else}
        <div></div><div></div>
      {/if}
      <Button onclick={run} loading={running} disabled={running} fullWidth>
        {#snippet icon()}<Play class="w-4 h-4" />{/snippet}
        {running ? $_('speed.running') : $_('speed.start')}
      </Button>
    </div>

    {#if activeTab === 'iperf3'}
      <label class="flex items-center gap-2 mt-3 text-sm text-slate-300">
        <input type="checkbox" bind:checked={reverse} />
        {$_('speed.reverse')}
      </label>
    {/if}
  </Card>

  {#if running}
    <Card><LoadingSpinner centered text={$_('speed.running')} /></Card>
  {:else if result}
    <Card title={$_('speed.results')}>
      <pre class="text-xs font-mono text-slate-300 overflow-x-auto bg-slate-950 p-4 rounded-lg">{JSON.stringify(result, null, 2)}</pre>
    </Card>
  {/if}

  {#if history.length > 0}
    <Card title={$_('speed.history')} subtitle={`${history.length} تست اخیر`}>
      <ul class="space-y-2">
        {#each history as h, i}
          <li class="flex items-center justify-between p-3 bg-slate-950 rounded-lg border border-slate-800 text-sm">
            <span class="text-slate-400">#{history.length - i} · {h.target || target}</span>
            <span class="font-mono text-slate-300">{h.summary || h.avg_latency || h.bitrate || JSON.stringify(h).slice(0, 60)}</span>
          </li>
        {/each}
      </ul>
    </Card>
  {/if}
</div>
