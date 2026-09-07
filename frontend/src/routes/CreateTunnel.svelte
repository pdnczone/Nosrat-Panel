<script>
  import { onMount } from 'svelte';
  import { _ } from '../lib/i18n.js';
  import { TunnelsAPI, CryptoAPI } from '../lib/api.js';
  import { loadServers } from '../stores/servers.js';
  import { createTunnel } from '../stores/tunnels.js';
  import Card from '../lib/components/Card.svelte';
  import Button from '../lib/components/Button.svelte';
  import Select from '../lib/components/Select.svelte';
  import Input from '../lib/components/Input.svelte';
  import LoadingSpinner from '../lib/components/LoadingSpinner.svelte';
  import { toast } from '../lib/toast.js';
  import { ArrowLeft, ArrowRight, Check, Network, Server as ServerIcon, Settings, Eye, CheckCircle2, Lock } from 'lucide-svelte';

  let { onNavigate = () => {} } = $props();

  let step = $state(0);
  let data = $state({
    type: '',
    server_id: '',
    name: '',
    description: '',
    listen_port: '',
    remote_host: '',
    remote_port: '',
    psk_id: '',
    mtu: 1400,
    ttl: 64,
    encryption: 'aes-256-gcm',
    auth_method: 'psk',
    auto_start: false
  });

  let servers = $state([]);
  let psks = $state([]);
  let loadingServers = $state(true);
  let creating = $state(false);
  let created = $state(null);

  onMount(async () => {
    try {
      await loadServers();
      const { servers: s } = await import('../stores/servers.js');
      servers = $state.snapshot(await new Promise((resolve) => {
        const unsub = s.subscribe((v) => { resolve(v); unsub(); });
      }));
      psks = await CryptoAPI.pskList();
    } finally {
      loadingServers = false;
    }
  });

  // ---------- Schema-driven fields per tunnel type ----------
  const TYPE_SCHEMA = {
    ipsec: {
      icon: Lock,
      fields: ['listen_port', 'remote_host', 'remote_port', 'psk_id', 'encryption', 'mtu', 'ttl', 'auto_start']
    },
    gre: {
      icon: Network,
      fields: ['listen_port', 'remote_host', 'remote_port', 'mtu', 'ttl', 'auto_start']
    },
    ghost: {
      icon: Network,
      fields: ['listen_port', 'remote_host', 'remote_port', 'psk_id', 'mtu', 'ttl', 'auto_start']
    },
    vpn: {
      icon: Network,
      fields: ['listen_port', 'remote_host', 'remote_port', 'psk_id', 'encryption', 'auto_start']
    },
    wireguard: {
      icon: Network,
      fields: ['listen_port', 'remote_host', 'remote_port', 'mtu', 'auto_start']
    }
  };

  const ALL_FIELDS = {
    name: { type: 'text', required: true, label: $_('tunnels.wizard.fields.name') },
    description: { type: 'text', label: $_('tunnels.wizard.fields.description') },
    listen_port: { type: 'number', required: true, label: $_('tunnels.wizard.fields.listen_port') },
    remote_host: { type: 'text', required: true, label: $_('tunnels.wizard.fields.remote_host') },
    remote_port: { type: 'number', required: true, label: $_('tunnels.wizard.fields.remote_port') },
    psk_id: {
      type: 'select',
      label: $_('tunnels.wizard.fields.psk'),
      optionsFrom: 'psks'
    },
    mtu: { type: 'number', label: $_('tunnels.wizard.fields.mtu') },
    ttl: { type: 'number', label: $_('tunnels.wizard.fields.ttl') },
    encryption: {
      type: 'select',
      label: $_('tunnels.wizard.fields.encryption'),
      options: [
        { value: 'aes-256-gcm', label: 'AES-256-GCM' },
        { value: 'aes-128-gcm', label: 'AES-128-GCM' },
        { value: 'chacha20-poly1305', label: 'ChaCha20-Poly1305' }
      ]
    },
    auth_method: {
      type: 'select',
      label: $_('tunnels.wizard.fields.auth_method'),
      options: [
        { value: 'psk', label: 'PSK' },
        { value: 'cert', label: 'Certificate' },
        { value: 'key', label: 'SSH Key' }
      ]
    },
    auto_start: { type: 'toggle', label: $_('tunnels.wizard.fields.auto_start') }
  };

  const STEPS = [
    { key: 'type', icon: Network, label: $_('tunnels.wizard.step_type') },
    { key: 'server', icon: ServerIcon, label: $_('tunnels.wizard.step_server') },
    { key: 'form', icon: Settings, label: $_('tunnels.wizard.step_form') },
    { key: 'review', icon: Eye, label: $_('tunnels.wizard.step_review') },
    { key: 'done', icon: CheckCircle2, label: $_('tunnels.wizard.step_done') }
  ];

  const canNext = $derived.by(() => {
    if (step === 0) return Boolean(data.type);
    if (step === 1) return Boolean(data.server_id);
    if (step === 2) {
      const required = ['name', 'listen_port', 'remote_host', 'remote_port'];
      return required.every((k) => data[k]);
    }
    return true;
  });

  async function finish() {
    creating = true;
    try {
      created = await createTunnel({ ...data, status: 'creating' });
      step = 4;
    } catch (e) {
      toast.error(e.message);
    } finally {
      creating = false;
    }
  }

  function fieldValue(field, key) {
    if (field.optionsFrom === 'psks') {
      return psks.map((p) => ({ value: p.id, label: `${p.label} (${p.algorithm})` }));
    }
    return field.options;
  }
</script>

<div class="space-y-5 max-w-4xl mx-auto">
  <div>
    <button class="btn-ghost text-sm mb-2" onclick={() => onNavigate('/tunnels')}>
      <ArrowLeft class="w-4 h-4" /> {$_('common.back')}
    </button>
    <h1 class="text-2xl font-bold text-slate-100">{$_('tunnels.create')}</h1>
  </div>

  <!-- Stepper -->
  <div class="flex items-center justify-between">
    {#each STEPS as s, i}
      <div class="flex-1 flex items-center {i < STEPS.length - 1 ? 'after:content-[\"\"] after:flex-1 after:h-0.5 after:bg-slate-800 after:mx-2' : ''}">
        <div class="flex flex-col items-center gap-1">
          <div class="w-10 h-10 rounded-full flex items-center justify-center border-2 transition-colors {step >= i ? 'bg-primary-500 border-primary-500 text-slate-950' : 'border-slate-700 text-slate-500'}">
            {#if step > i}<Check class="w-5 h-5" />{:else}<s.icon class="w-5 h-5" />{/if}
          </div>
          <span class="text-xs {step >= i ? 'text-primary-400' : 'text-slate-500'} hidden sm:block">{s.label}</span>
        </div>
      </div>
    {/each}
  </div>

  <Card>
    {#if step === 0}
      <h2 class="text-lg font-semibold text-slate-100 mb-4">{$_('tunnels.wizard.type_question')}</h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {#each ['ipsec', 'gre', 'ghost', 'vpn', 'wireguard'] as t}
          <button
            type="button"
            onclick={() => (data.type = t)}
            class="text-start p-4 rounded-lg border-2 transition-all {data.type === t ? 'border-primary-500 bg-primary-500/10' : 'border-slate-800 hover:border-slate-700 bg-slate-900'}"
          >
            <div class="flex items-center gap-2 mb-1">
              <Network class="w-4 h-4 text-primary-400" />
              <span class="font-semibold text-slate-100 uppercase">{t}</span>
            </div>
            <p class="text-xs text-slate-400">{$_(`tunnels.wizard.types.${t}`)}</p>
          </button>
        {/each}
      </div>
    {:else if step === 1}
      <h2 class="text-lg font-semibold text-slate-100 mb-4">{$_('tunnels.wizard.server_question')}</h2>
      {#if loadingServers}
        <LoadingSpinner />
      {:else if servers.length === 0}
        <p class="text-slate-400 text-center py-6">{$_('common.empty')}</p>
        <Button variant="secondary" onclick={() => onNavigate('/servers')}>
          {$_('servers.new_server')}
        </Button>
      {:else}
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {#each servers as s}
            <button
              type="button"
              onclick={() => (data.server_id = s.id)}
              class="text-start p-4 rounded-lg border-2 transition-all {data.server_id === s.id ? 'border-primary-500 bg-primary-500/10' : 'border-slate-800 hover:border-slate-700 bg-slate-900'}"
            >
              <div class="flex items-center gap-2 mb-1">
                <ServerIcon class="w-4 h-4 text-primary-400" />
                <span class="font-semibold text-slate-100">{s.name}</span>
              </div>
              <p class="text-xs text-slate-400 font-mono">{s.host}:{s.port}</p>
            </button>
          {/each}
        </div>
      {/if}
    {:else if step === 2}
      <h2 class="text-lg font-semibold text-slate-100 mb-4">{$_('tunnels.wizard.step_form')}</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input label={$_('tunnels.wizard.fields.name')} bind:value={data.name} required placeholder="my-tunnel" />
        <Input label={$_('tunnels.wizard.fields.description')} bind:value={data.description} />
        {#each TYPE_SCHEMA[data.type]?.fields ?? [] as fieldKey}
          {@const field = ALL_FIELDS[fieldKey]}
          {#if field.type === 'select'}
            <Select
              label={field.label}
              bind:value={data[fieldKey]}
              options={fieldValue(field, fieldKey) || []}
            />
          {:else if field.type === 'toggle'}
            <label class="flex items-center gap-2 pt-6">
              <input type="checkbox" bind:checked={data[fieldKey]} class="rounded" />
              <span class="text-sm text-slate-300">{field.label}</span>
            </label>
          {:else}
            <Input label={field.label} type={field.type} bind:value={data[fieldKey]} required={field.required} />
          {/if}
        {/each}
      </div>
    {:else if step === 3}
      <h2 class="text-lg font-semibold text-slate-100 mb-4">{$_('tunnels.wizard.review_intro')}</h2>
      <dl class="grid grid-cols-2 gap-3 text-sm">
        {#each Object.entries(data) as [k, v]}
          {#if v !== '' && v !== null && v !== undefined}
            <div class="flex flex-col p-3 bg-slate-950 rounded-lg border border-slate-800">
              <dt class="text-xs text-slate-500">{k}</dt>
              <dd class="text-slate-200 font-mono mt-1 break-all">{String(v)}</dd>
            </div>
          {/if}
        {/each}
      </dl>
    {:else if step === 4}
      <div class="text-center py-10">
        <div class="inline-flex w-16 h-16 rounded-full bg-emerald-500/15 text-emerald-400 items-center justify-center mb-4">
          <CheckCircle2 class="w-8 h-8" />
        </div>
        <h2 class="text-xl font-semibold text-slate-100">{$_('tunnels.wizard.created')}</h2>
        <p class="text-slate-400 mt-2">{created?.name}</p>
        <div class="flex justify-center gap-2 mt-6">
          <Button variant="secondary" onclick={() => onNavigate(`/tunnels/${created?.id}`)}>
            {$_('common.details')}
          </Button>
          <Button onclick={() => onNavigate('/tunnels')}>{$_('common.finish')}</Button>
        </div>
      </div>
    {/if}

    {#if step < 4}
      <div class="flex items-center justify-between mt-6 pt-4 border-t border-slate-800">
        <Button variant="ghost" disabled={step === 0} onclick={() => step--}>
          {#snippet icon()}<ArrowRight class="w-4 h-4 rtl:rotate-180" />{/snippet}
          {$_('common.previous')}
        </Button>
        {#if step < 3}
          <Button disabled={!canNext} onclick={() => step++}>
            {$_('common.next')}
            {#snippet icon()}<ArrowLeft class="w-4 h-4 rtl:rotate-180" />{/snippet}
          </Button>
        {:else}
          <Button disabled={creating} loading={creating} onclick={finish}>
            {$_('tunnels.wizard.creating')}
          </Button>
        {/if}
      </div>
    {/if}
  </Card>
</div>
