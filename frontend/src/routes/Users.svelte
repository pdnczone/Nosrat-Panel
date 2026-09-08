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
  let newUser = $state({ username: '', password: '', role: 'user', active: true, quota_gb: '', expiry_at: '' });

  onMount(load);

  async function load() {
    loading = true;
    try { users = await UsersAPI.list(); }
    finally { loading = false; }
  }

  async function create() {
    try {
      const payload = {
        username: newUser.username,
        password: newUser.password,
        role: newUser.role,
        is_active: newUser.active,
      };
      if (newUser.quota_gb) payload.quota_gb = Number(newUser.quota_gb);
      if (newUser.expiry_at) payload.expiry_at = newUser.expiry_at;
      await UsersAPI.create(payload);
      createOpen = false;
      newUser = { username: '', password: '', role: 'user', active: true, quota_gb: '', expiry_at: '' };
      toast.success($_('common.create'));
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
    }
  }

  async function toggleActive(u) {
    await UsersAPI.update(u.id, { is_active: !u.is_active });
    await load();
  }

  async function remove() {
    await UsersAPI.delete(confirmDelete.id);
    users = users.filter((u) => u.id !== confirmDelete.id);
  }

  function fmtExpiry(val) {
    if (!val) return '—';
    return new Date(val).toLocaleDateString('fa-IR');
  }
  function fmtQuota(val) {
    if (val == null) return 'نامحدود';
    return `${val} GB`;
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
              <th class="px-4 py-3 text-start font-medium">نام کاربری</th>
              <th class="px-4 py-3 text-start font-medium">نقش</th>
              <th class="px-4 py-3 text-start font-medium">وضعیت</th>
              <th class="px-4 py-3 text-start font-medium">سقف حجم</th>
              <th class="px-4 py-3 text-start font-medium">تاریخ انقضا</th>
              <th class="px-4 py-3 text-start font-medium">آخرین ورود</th>
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
                <td class="px-4 py-3">
                  <span class="badge {u.role === 'admin' ? 'bg-red-500/15 text-red-300 border-red-500/30 border' : 'bg-amber-500/15 text-amber-300 border border-amber-500/30'}">
                    <ShieldCheck class="w-3 h-3" />
                    {u.role === 'admin' ? 'ادمین' : 'کاربر'}
                  </span>
                </td>
                <td class="px-4 py-3">
                  <button
                    class="w-10 h-5 rounded-full transition-colors relative {u.is_active ? 'bg-emerald-500' : 'bg-slate-700'}"
                    onclick={() => toggleActive(u)}
                  >
                    <span class="absolute top-0.5 w-4 h-4 bg-white rounded-full transition-all {u.is_active ? 'start-5' : 'start-0.5'}"></span>
                  </button>
                </td>
                <td class="px-4 py-3 text-slate-300 text-xs">{fmtQuota(u.quota_gb)}</td>
                <td class="px-4 py-3 text-slate-300 text-xs">{fmtExpiry(u.expiry_at)}</td>
                <td class="px-4 py-3 text-slate-400 text-xs">{u.last_login ? new Date(u.last_login).toLocaleString() : '—'}</td>
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
    <Input label="نام کاربری" bind:value={newUser.username} required />
    <Input label="رمز عبور" type="password" bind:value={newUser.password} required />
    <Select label="نقش" bind:value={newUser.role} options={[
      { value: 'admin', label: 'ادمین' },
      { value: 'user', label: 'کاربر' },
    ]} />
    <Input label="سقف حجم (GB، خالی = نامحدود)" type="number" bind:value={newUser.quota_gb} placeholder="مثلاً 50" />
    <Input label="تاریخ انقضا" type="date" bind:value={newUser.expiry_at} />
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
