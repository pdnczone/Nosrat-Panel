<script>
  import { onMount } from 'svelte';
  import { _ } from '../lib/i18n.js';
  import { CryptoAPI } from '../lib/api.js';
  import Card from '../lib/components/Card.svelte';
  import Button from '../lib/components/Button.svelte';
  import Modal from '../lib/components/Modal.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import Input from '../lib/components/Input.svelte';
  import LoadingSpinner from '../lib/components/LoadingSpinner.svelte';
  import { toast } from '../lib/toast.js';
  import { Plus, RotateCw, Download, Trash2, KeyRound } from 'lucide-svelte';

  let psks = $state([]);
  let loading = $state(true);
  let createOpen = $state(false);
  let confirmDelete = $state({ open: false, id: null, label: '' });
  let newKey = $state({ bits: 256 });

  onMount(load);

  async function load() {
    loading = true;
    try {
      psks = await CryptoAPI.pskList();
    } finally {
      loading = false;
    }
  }

  async function create() {
    try {
      await CryptoAPI.pskCreate({ bits: newKey.bits });
      createOpen = false;
      newKey = { bits: 256 };
      toast.success($_('common.create'));
      await load();
    } catch (e) {}
  }

  async function rotate(id) {
    await CryptoAPI.pskRotate(id, {});
    toast.success($_('crypto.rotate'));
    await load();
  }

  async function exportKey(id) {
    const blob = await CryptoAPI.export(id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `psk-${id}.key`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function remove() {
    await CryptoAPI.pskDelete(confirmDelete.id);
    psks = psks.filter((p) => p.id !== confirmDelete.id);
    toast.success($_('common.delete'));
  }
</script>

<div class="space-y-5">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-bold text-slate-100">{$_('crypto.title')}</h1>
    <Button onclick={() => (createOpen = true)}>
      {#snippet icon()}<Plus class="w-4 h-4" />{/snippet}
      {$_('crypto.new_psk')}
    </Button>
  </div>

  {#if loading}
    <LoadingSpinner centered />
  {:else if psks.length === 0}
    <Card>
      <p class="text-slate-500 text-center py-6">{$_('common.empty')}</p>
    </Card>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {#each psks as p (p.id)}
        <div class="card">
          <div class="flex items-start justify-between mb-3">
            <div class="flex items-center gap-2 min-w-0">
              <KeyRound class="w-5 h-5 text-primary-400 flex-shrink-0" />
              <h3 class="font-semibold text-slate-100 truncate">{p.name}</h3>
            </div>
          </div>
          <dl class="space-y-2 text-sm">
            <div class="flex justify-between"><dt class="text-slate-500">{$_('crypto.fields.length')}</dt><dd class="text-slate-200">{p.length ?? p.bits ?? 256} bit</dd></div>
            <div class="flex justify-between items-center gap-2"><dt class="text-slate-500">{$_('crypto.fields.key')}</dt><dd class="text-slate-200 font-mono text-xs truncate">{p.masked ?? p.preview ?? '—'}</dd></div>
            {#if p.path}
              <div class="flex justify-between gap-2"><dt class="text-slate-500">{$_('crypto.fields.path')}</dt><dd class="text-slate-300 text-xs truncate">{p.path}</dd></div>
            {/if}
          </dl>
          <div class="flex gap-1 mt-4 pt-3 border-t border-slate-800">
            <button class="btn-ghost text-xs flex-1" onclick={() => rotate(p.id)}><RotateCw class="w-3 h-3 me-1" />{$_('crypto.rotate')}</button>
            <button class="btn-ghost text-xs flex-1" onclick={() => exportKey(p.id)}><Download class="w-3 h-3 me-1" />{$_('crypto.export')}</button>
            <button class="btn-ghost text-xs text-red-400" onclick={() => (confirmDelete = { open: true, id: p.id, label: p.name })}><Trash2 class="w-3 h-3" /></button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<Modal bind:open={createOpen} title={$_('crypto.new_psk')} size="sm">
  <div class="space-y-3">
    <Input label={$_('crypto.fields.length')} type="number" bind:value={newKey.bits} />
  </div>
  {#snippet footer()}
    <Button variant="ghost" onclick={() => (createOpen = false)}>{$_('common.cancel')}</Button>
    <Button onclick={create}>{$_('common.create')}</Button>
  {/snippet}
</Modal>

<ConfirmDialog
  bind:open={confirmDelete.open}
  title={$_('common.delete')}
  message={$_('crypto.delete_confirm')}
  confirmText={$_('common.delete')}
  onConfirm={remove}
/>
