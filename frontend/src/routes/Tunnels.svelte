<script>
  import { onMount } from 'svelte';
  import { _ } from '../lib/i18n.js';
  import { TunnelsAPI } from '../lib/api.js';
  import Card from '../lib/components/Card.svelte';
  import Button from '../lib/components/Button.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import StatusBadge from '../lib/components/StatusBadge.svelte';
  import LoadingSpinner from '../lib/components/LoadingSpinner.svelte';
  import { toast } from '../lib/toast.js';
  import { Play, Square, RotateCw, Trash2, Plus, Search, Eye } from 'lucide-svelte';

  let { onNavigate = () => {} } = $props();

  let tunnels = $state([]);
  let loading = $state(true);
  let search = $state('');
  let typeFilter = $state('');
  let statusFilter = $state('');
  let confirmDelete = $state({ open: false, id: null, name: '' });

  const TYPES = ['ipsec', 'gre', 'ghost', 'vpn', 'wireguard'];
  const STATUSES = ['running', 'stopped', 'error', 'starting'];

  onMount(async () => { await load(); });

  async function load() {
    loading = true;
    try {
      const data = await TunnelsAPI.list();
      tunnels = Array.isArray(data) ? data : data.items || [];
    } finally {
      loading = false;
    }
  }

  const filtered = $derived(tunnels.filter((t) => {
    if (typeFilter && t.type !== typeFilter) return false;
    if (statusFilter && t.status !== statusFilter) return false;
    if (search && !t.name?.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  }));

  async function start(id) { await TunnelsAPI.start(id); await load(); }
  async function stop(id) { await TunnelsAPI.stop(id); await load(); }
  async function restart(id) { await TunnelsAPI.restart(id); await load(); }
  function askDelete(t) { confirmDelete = { open: true, id: t.id, name: t.name }; }
  async function doDelete() {
    await TunnelsAPI.delete(confirmDelete.id);
    tunnels = tunnels.filter((t) => t.id !== confirmDelete.id);
    toast.success($_('common.delete'));
  }
</script>

<div class="space-y-5">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <h1 class="text-2xl font-bold text-slate-100">{$_('tunnels.title')}</h1>
    <Button onclick={() => onNavigate('/tunnels/create')}>
      {#snippet icon()}<Plus class="w-4 h-4" />{/snippet}
      {$_('tunnels.create')}
    </Button>
  </div>

  <Card>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
      <div class="relative">
        <Search class="w-4 h-4 absolute start-3 top-1/2 -translate-y-1/2 text-slate-500" />
        <input bind:value={search} class="input ps-10" placeholder={$_('tunnels.search_placeholder')} />
      </div>
      <select bind:value={typeFilter} class="input">
        <option value="">{$_('tunnels.all_types')}</option>
        {#each TYPES as t}<option value={t}>{t.toUpperCase()}</option>{/each}
      </select>
      <select bind:value={statusFilter} class="input">
        <option value="">{$_('tunnels.all_statuses')}</option>
        {#each STATUSES as s}<option value={s}>{s}</option>{/each}
      </select>
    </div>
  </Card>

  {#if loading}
    <LoadingSpinner centered />
  {:else}
    <div class="card">
      <div class="overflow-x-auto -mx-5">
        <table class="w-full text-sm">
          <thead class="bg-slate-900/80 text-slate-400 text-xs uppercase">
            <tr>
              <th class="px-4 py-3 text-start font-medium">{$_('tunnels.columns.name')}</th>
              <th class="px-4 py-3 text-start font-medium">{$_('tunnels.columns.type')}</th>
              <th class="px-4 py-3 text-start font-medium">{$_('tunnels.columns.server')}</th>
              <th class="px-4 py-3 text-start font-medium">{$_('tunnels.columns.status')}</th>
              <th class="px-4 py-3 text-start font-medium">{$_('tunnels.columns.traffic')}</th>
              <th class="px-4 py-3 text-start font-medium">{$_('tunnels.columns.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {#if filtered.length === 0}
              <tr><td colspan="6" class="text-center py-10 text-slate-500">{$_('common.empty')}</td></tr>
            {:else}
              {#each filtered as t (t.id)}
                <tr class="border-t border-slate-800 hover:bg-slate-800/40">
                  <td class="px-4 py-3">
                    <button class="text-primary-400 hover:underline font-medium" onclick={() => onNavigate(`/tunnels/${t.id}`)}>{t.name}</button>
                  </td>
                  <td class="px-4 py-3"><span class="badge bg-slate-800 text-slate-300">{t.type ?? '—'}</span></td>
                  <td class="px-4 py-3 text-slate-300">{t.server ?? '—'}</td>
                  <td class="px-4 py-3"><StatusBadge status={t.status} /></td>
                  <td class="px-4 py-3 font-mono text-xs text-slate-300">↑ {t.tx ?? '0'} · ↓ {t.rx ?? '0'}</td>
                  <td class="px-4 py-3">
                    <div class="flex items-center gap-1">
                      <button class="btn-ghost p-1.5" title={$_('tunnels.actions.view')} onclick={() => onNavigate(`/tunnels/${t.id}`)}><Eye class="w-4 h-4" /></button>
                      {#if t.status === 'running'}
                        <button class="btn-ghost p-1.5 text-amber-400" title={$_('tunnels.actions.stop')} onclick={() => stop(t.id)}><Square class="w-4 h-4" /></button>
                      {:else}
                        <button class="btn-ghost p-1.5 text-emerald-400" title={$_('tunnels.actions.start')} onclick={() => start(t.id)}><Play class="w-4 h-4" /></button>
                      {/if}
                      <button class="btn-ghost p-1.5 text-cyan-400" title={$_('tunnels.actions.restart')} onclick={() => restart(t.id)}><RotateCw class="w-4 h-4" /></button>
                      <button class="btn-ghost p-1.5 text-red-400" title={$_('tunnels.actions.delete')} onclick={() => askDelete(t)}><Trash2 class="w-4 h-4" /></button>
                    </div>
                  </td>
                </tr>
              {/each}
            {/if}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
</div>

<ConfirmDialog
  bind:open={confirmDelete.open}
  title={$_('common.delete')}
  message={$_('tunnels.delete_confirm')}
  confirmText={$_('common.delete')}
  onConfirm={doDelete}
/>
