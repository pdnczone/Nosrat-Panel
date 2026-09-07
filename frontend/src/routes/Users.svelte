<script>
  import { onMount } from 'svelte';
  import { _ } from '../lib/i18n.js';
  import { isAdmin } from '../lib/auth.js';
  import { UsersAPI } from '../lib/api.js';
  import Card from '../lib/components/Card.svelte';
  import Button from '../lib/components/Button.svelte';
  import Modal from '../lib/components/Modal.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import Input from '../lib/components/Input.svelte';
  import Select from '../lib/components/Select.svelte';
  import LoadingSpinner from '../lib/components/LoadingSpinner.svelte';
  import { Plus, Trash2, Edit, User as UserIcon, ShieldCheck } from 'lucide-svelte';
  import { toast } from '../lib/toast.js';

  let users = $state([]);
  let loading = $state(true);
  let createOpen = $state(false);
  let confirmDelete = $state({ open: false, id: null, name: '' });
  let newUser = $state({ username: '', email: '', password: '', role: 'viewer', active: true });

  onMount(load);

  async function load() {
    loading = true;
    try { users = await UsersAPI.list(); }
    finally { loading = false; }
  }

  async function create() {
    try {
      await UsersAPI.create(newUser);
      createOpen = false;
      newUser = { username: '', email: '', password: '', role: 'viewer', active: true };
      toast.success($_('common.create'));
      await load();
    } catch (_) {}
  }

  async function toggleActive(u) {
    await UsersAPI.update(u.id, { ...u, active: !u.active });
    await load();
  }

  async function remove() {
    await UsersAPI.delete(confirmDelete.id);
    users = users.filter((u) => u.id !== confirmDelete.id);
  }
</script>

<div class="space-y-5">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-bold text-slate-100">{$_('users.title')}</h1>
    {#if $isAdmin}
      <Button onclick={() => (createOpen = true)}>
        {#snippet icon()}<Plus class="w-4 h-4" />{/snippet}
        {$_('users.new_user')}
      </Button>
    {/if}
  </div>

  {#if !$isAdmin}
    <Card><p class="text-slate-500 text-center py-6">{$_('errors.forbidden')}</p></Card>
  {:else if loading}
    <LoadingSpinner centered />
  {:else if users.length === 0}
    <Card><p class="text-center py-6 text-slate-500">{$_('common.empty')}</p></Card>
  {:else}
    <div class="card">
      <div class="overflow-x-auto -mx-5">
        <table class="w-full text-sm">
          <thead class="bg-slate-900/80 text-slate-400 text-xs uppercase">
            <tr>
              <th class="px-4 py-3 text-start font-medium">{$_('users.fields.username')}</th>
              <th class="px-4 py-3 text-start font-medium">{$_('users.fields.email')}</th>
              <th class="px-4 py-3 text-start font-medium">{$_('users.fields.role')}</th>
              <th class="px-4 py-3 text-start font-medium">{$_('users.fields.active')}</th>
              <th class="px-4 py-3 text-start font-medium">{$_('users.fields.last_login')}</th>
              <th class="px-4 py-3 text-start font-medium">{$_('common.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {#each users as u (u.id)}
              <tr class="border-t border-slate-800">
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <div class="w-8 h-8 rounded-full bg-primary-500/15 text-primary-400 flex items-center justify-center text-sm font-semibold">{u.username?.[0]?.toUpperCase()}</div>
                    <span class="text-slate-200">{u.username}</span>
                  </div>
                </td>
                <td class="px-4 py-3 text-slate-300">{u.email ?? '—'}</td>
                <td class="px-4 py-3">
                  <span class="badge {u.role === 'admin' ? 'bg-red-500/15 text-red-300 border-red-500/30 border' : u.role === 'operator' ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30' : 'bg-slate-700/40 text-slate-300'}">
                    <ShieldCheck class="w-3 h-3" />
                    {$_(`users.roles.${u.role}`)}
                  </span>
                </td>
                <td class="px-4 py-3">
                  <button
                    class="w-10 h-5 rounded-full transition-colors relative {u.active ? 'bg-emerald-500' : 'bg-slate-700'}"
                    onclick={() => toggleActive(u)}
                  >
                    <span class="absolute top-0.5 w-4 h-4 bg-white rounded-full transition-all {u.active ? 'start-5' : 'start-0.5'}"></span>
                  </button>
                </td>
                <td class="px-4 py-3 text-slate-400 text-xs">{u.last_login ?? '—'}</td>
                <td class="px-4 py-3">
                  <button class="btn-ghost p-1.5 text-red-400" onclick={() => (confirmDelete = { open: true, id: u.id, name: u.username })}>
                    <Trash2 class="w-4 h-4" />
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
</div>

<Modal bind:open={createOpen} title={$_('users.new_user')} size="sm">
  <div class="space-y-3">
    <Input label={$_('users.fields.username')} bind:value={newUser.username} required />
    <Input label={$_('users.fields.email')} type="email" bind:value={newUser.email} />
    <Input label={$_('users.fields.password')} type="password" bind:value={newUser.password} required />
    <Select label={$_('users.fields.role')} bind:value={newUser.role} options={[
      { value: 'admin', label: $_('users.roles.admin') },
      { value: 'operator', label: $_('users.roles.operator') },
      { value: 'viewer', label: $_('users.roles.viewer') }
    ]} />
  </div>
  {#snippet footer()}
    <Button variant="ghost" onclick={() => (createOpen = false)}>{$_('common.cancel')}</Button>
    <Button onclick={create}>{$_('common.create')}</Button>
  {/snippet}
</Modal>

<ConfirmDialog
  bind:open={confirmDelete.open}
  title={$_('common.delete')}
  message={$_('users.delete_confirm')}
  confirmText={$_('common.delete')}
  onConfirm={remove}
/>
