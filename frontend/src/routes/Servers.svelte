<script>
  import { onMount } from 'svelte';
  import { _ } from '../lib/i18n.js';
  import { servers, serversLoading, loadServers, deleteServer, createServer, testServer } from '../stores/servers.js';
  import Card from '../lib/components/Card.svelte';
  import Button from '../lib/components/Button.svelte';
  import Modal from '../lib/components/Modal.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import Input from '../lib/components/Input.svelte';
  import Select from '../lib/components/Select.svelte';
  import StatusBadge from '../lib/components/StatusBadge.svelte';
  import LoadingSpinner from '../lib/components/LoadingSpinner.svelte';
  import { Plus, Trash2, TestTube, Server as ServerIcon } from 'lucide-svelte';

  let createOpen = $state(false);
  let confirmDelete = $state({ open: false, id: null, name: '' });
  let newServer = $state({ name: '', host: '', port: 22, username: 'root', auth_method: 'key', private_key: '', password: '' });

  onMount(loadServers);

  async function create() {
    await createServer(newServer);
    createOpen = false;
    newServer = { name: '', host: '', port: 22, username: 'root', auth_method: 'key', private_key: '', password: '' };
  }

  async function test(id) { await testServer(id); }

  async function remove() {
    await deleteServer(confirmDelete.id);
  }
</script>

<div class="space-y-5">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-bold text-slate-100">{$_('servers.title')}</h1>
    <Button onclick={() => (createOpen = true)}>
      {#snippet icon()}<Plus class="w-4 h-4" />{/snippet}
      {$_('servers.new_server')}
    </Button>
  </div>

  {#if $serversLoading}
    <LoadingSpinner centered />
  {:else if $servers.length === 0}
    <Card><p class="text-center py-6 text-slate-500">{$_('common.empty')}</p></Card>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {#each $servers as s (s.id)}
        <div class="card">
          <div class="flex items-start justify-between mb-3">
            <div class="flex items-center gap-2 min-w-0">
              <ServerIcon class="w-5 h-5 text-primary-400 flex-shrink-0" />
              <h3 class="font-semibold text-slate-100 truncate">{s.name}</h3>
            </div>
            <StatusBadge status={s.status ?? 'unknown'} />
          </div>
          <dl class="text-sm space-y-1">
            <div class="flex justify-between"><dt class="text-slate-500">{$_('servers.fields.host')}</dt><dd class="font-mono text-slate-200">{s.host}:{s.port}</dd></div>
            <div class="flex justify-between"><dt class="text-slate-500">{$_('servers.fields.username')}</dt><dd class="text-slate-200">{s.username}</dd></div>
            <div class="flex justify-between"><dt class="text-slate-500">{$_('servers.fields.auth_method')}</dt><dd class="text-slate-200">{$_(`servers.auth_methods.${s.auth_method}`)}</dd></div>
          </dl>
          <div class="flex gap-2 mt-4 pt-3 border-t border-slate-800">
            <button class="btn-ghost text-xs flex-1" onclick={() => test(s.id)}><TestTube class="w-3 h-3 me-1" />{$_('servers.test_connection')}</button>
            <button class="btn-ghost text-xs text-red-400" onclick={() => (confirmDelete = { open: true, id: s.id, name: s.name })}><Trash2 class="w-3 h-3" /></button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<Modal bind:open={createOpen} title={$_('servers.new_server')} size="md">
  <div class="space-y-3">
    <Input label={$_('servers.fields.name')} bind:value={newServer.name} required />
    <div class="grid grid-cols-3 gap-3">
      <div class="col-span-2"><Input label={$_('servers.fields.host')} bind:value={newServer.host} required placeholder="192.168.1.1" /></div>
      <Input label={$_('servers.fields.port')} type="number" bind:value={newServer.port} />
    </div>
    <Input label={$_('servers.fields.username')} bind:value={newServer.username} required />
    <Select label={$_('servers.fields.auth_method')} bind:value={newServer.auth_method} options={[
      { value: 'key', label: $_('servers.auth_methods.key') },
      { value: 'password', label: $_('servers.auth_methods.password') },
      { value: 'agent', label: $_('servers.auth_methods.agent') }
    ]} />
    {#if newServer.auth_method === 'key'}
      <label class="block">
        <span class="label">{$_('servers.fields.private_key')}</span>
        <textarea bind:value={newServer.private_key} rows="4" class="input font-mono text-xs"></textarea>
      </label>
    {:else if newServer.auth_method === 'password'}
      <Input label={$_('servers.fields.password')} type="password" bind:value={newServer.password} />
    {/if}
  </div>
  {#snippet footer()}
    <Button variant="ghost" onclick={() => (createOpen = false)}>{$_('common.cancel')}</Button>
    <Button onclick={create}>{$_('common.create')}</Button>
  {/snippet}
</Modal>

<ConfirmDialog
  bind:open={confirmDelete.open}
  title={$_('common.delete')}
  message={`حذف سرور «${confirmDelete.name}»؟`}
  confirmText={$_('common.delete')}
  onConfirm={remove}
/>
