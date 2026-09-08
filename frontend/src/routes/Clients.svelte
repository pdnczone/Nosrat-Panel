<script>
  import { onMount } from 'svelte';
  import { _ } from '../lib/i18n.js';
  import { ClientsAPI, TunnelsAPI, ServersAPI } from '../lib/api.js';
  import Card from '../lib/components/Card.svelte';
  import Button from '../lib/components/Button.svelte';
  import Modal from '../lib/components/Modal.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import Input from '../lib/components/Input.svelte';
  import Select from '../lib/components/Select.svelte';
  import LoadingSpinner from '../lib/components/LoadingSpinner.svelte';
  import { Plus, Trash2, RefreshCw, Gauge } from 'lucide-svelte';
  import { toast } from '../lib/toast.js';

  let clients = $state([]);
  let tunnels = $state([]);
  let servers = $state([]);
  let loading = $state(true);
  let createOpen = $state(false);
  let usageFor = $state(null);
  let usageOpen = $state(false);
  let usageData = $state(null);
  let confirmDelete = $state({ open: false, id: null, name: '' });

  const empty = () => ({ name: '', tunnel_id: '', server_id: '', peer_identifier: '', quota_gb: '', expires_at: '' });
  let form = $state(empty());

  onMount(async () => {
    try {
      const [c, t, s] = await Promise.allSettled([
        ClientsAPI.list(),
        TunnelsAPI.list(),
        ServersAPI.list(),
      ]);
      clients = c.status === 'fulfilled' ? c.value : [];
      tunnels = t.status === 'fulfilled' ? t.value : [];
      servers = s.status === 'fulfilled' ? s.value : [];
    } finally {
      loading = false;
    }
  });

  async function create() {
    try {
      const payload = {
        name: form.name,
        peer_identifier: form.peer_identifier || null,
      };
      if (form.tunnel_id) payload.tunnel_id = Number(form.tunnel_id);
      if (form.server_id) payload.server_id = Number(form.server_id);
      if (form.quota_gb) payload.quota_bytes = Math.round(Number(form.quota_gb) * 1024 ** 3);
      if (form.expires_at) payload.expires_at = form.expires_at;
      await ClientsAPI.create(payload);
      createOpen = false;
      form = empty();
      toast.success($_('common.create'));
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
    }
  }

  async function load() {
    try { clients = await ClientsAPI.list(); } catch {}
  }

  async function openUsage(c) {
    usageFor = c;
    usageData = null;
    usageOpen = true;
    try {
      usageData = await ClientsAPI.usage(c.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
    }
  }

  async function topup() {
    try {
      const payload = {};
      if (usageTopup.gb) payload.quota_bytes = Math.round(Number(usageTopup.gb) * 1024 ** 3);
      if (usageTopup.expires_at) payload.expires_at = usageTopup.expires_at;
      await ClientsAPI.topup(usageFor.id, payload);
      toast.success('تمدید/افزایش حجم ثبت شد');
      usageOpen = false;
      usageFor = null;
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
    }
  }
  let usageTopup = $state({ gb: '', expires_at: '' });

  async function remove() {
    await ClientsAPI.delete(confirmDelete.id);
    clients = clients.filter((c) => c.id !== confirmDelete.id);
  }

  function fmtBytes(b) {
    if (b == null) return '—';
    if (b >= 1024 ** 3) return (b / 1024 ** 3).toFixed(2) + ' GB';
    if (b >= 1024 ** 2) return (b / 1024 ** 2).toFixed(1) + ' MB';
    return b + ' B';
  }
  function fmtExpiry(val) {
    if (!val) return 'نامحدود';
    return new Date(val).toLocaleDateString('fa-IR');
  }
  const statusLabels = {
    active: 'فعال',
    over_quota: 'سقف مصرف',
    expired: 'منقضی',
    disabled: 'غیرفعال',
  };
  const statusColor = {
    active: 'bg-emerald-500/15 text-emerald-400',
    over_quota: 'bg-red-500/15 text-red-400',
    expired: 'bg-amber-500/15 text-amber-400',
    disabled: 'bg-slate-500/15 text-slate-400',
  };
</script>

<div class="space-y-5">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-bold text-slate-100">کلاینت‌ها</h1>
    <Button onclick={() => (createOpen = true)}>
      {#snippet icon()}<Plus class="w-4 h-4" />{/snippet}
      کلاینت جدید
    </Button>
  </div>

  {#if loading}
    <LoadingSpinner centered />
  {:else}
    <Card>
      <table class="w-full text-sm">
        <thead>
          <tr class="text-start text-slate-400 border-b border-slate-800">
            <th class="text-start py-2">نام</th>
            <th class="text-start py-2">مصرف / سقف</th>
            <th class="text-start py-2">وضعیت</th>
            <th class="text-start py-2">انقضا</th>
            <th class="text-start py-2"></th>
          </tr>
        </thead>
        <tbody>
          {#each clients as c}
            <tr class="border-b border-slate-800/60">
              <td class="py-2">{c.name}</td>
              <td class="py-2">
                <div class="flex items-center gap-2">
                  <span>{fmtBytes(c.used_bytes)} / {c.quota_bytes ? fmtBytes(c.quota_bytes) : 'نامحدود'}</span>
                </div>
              </td>
              <td class="py-2">
                <span class="px-2 py-0.5 rounded-full text-xs {statusColor[c.status] || 'bg-slate-500/15'}">
                  {statusLabels[c.status] || c.status}
                </span>
              </td>
              <td class="py-2">{fmtExpiry(c.expires_at)}</td>
              <td class="py-2 text-end whitespace-nowrap">
                <button class="p-1 text-slate-400 hover:text-primary-300" onclick={() => { usageTopup = { gb: '', expires_at: '' }; openUsage(c); }} title="مصرف">
                  <Gauge class="w-4 h-4" />
                </button>
                <button class="p-1 text-red-400 hover:text-red-300" onclick={() => (confirmDelete = { open: true, id: c.id, name: c.name })} title="حذف">
                  <Trash2 class="w-4 h-4" />
                </button>
              </td>
            </tr>
          {:else}
            <tr><td colspan="5" class="py-6 text-center text-slate-500">کلاینتی ثبت نشده</td></tr>
          {/each}
        </tbody>
      </table>
    </Card>
  {/if}
</div>

{#if createOpen}
  <Modal bind:open={createOpen} title="کلاینت جدید" size="sm">
    <div class="space-y-3">
      <Input bind:value={form.name} label="نام کلاینت" placeholder="مثلاً Ali" required />
      <Select
        label="اتصال به تونل"
        bind:value={form.tunnel_id}
        options={[{ value: '', label: '— بدون تونل —' }, ...tunnels.map((t) => ({ value: String(t.id), label: t.name }))]}
      />
      <Select
        label="اتصال به سرور"
        bind:value={form.server_id}
        options={[{ value: '', label: '— بدون سرور —' }, ...servers.map((s) => ({ value: String(s.id), label: s.name }))]}
      />
      <Input bind:value={form.peer_identifier} label="شناسه پیر (اختیاری)" placeholder="مثلاً کلید عمومی WireGuard" />
      <Input bind:value={form.quota_gb} label="سقف حجم (GB، خالی = نامحدود)" type="number" placeholder="مثلاً 50" />
      <Input bind:value={form.expires_at} label="تاریخ انقضا" type="datetime-local" placeholder="خالی = بدون انقضا" />
    </div>
    {#snippet footer()}
      <Button variant="ghost" onclick={() => (createOpen = false)}>{$_('common.cancel')}</Button>
      <Button onclick={create}>{$_('common.create')}</Button>
    {/snippet}
  </Modal>
{/if}

{#if usageFor}
  <Modal bind:open={usageOpen} title={`مصرف ${usageFor.name}`} size="md">
    {#if usageData}
      <div class="space-y-4">
        <div>
          <div class="flex justify-between text-sm mb-1">
            <span class="text-slate-400">مصرف</span>
            <span class="text-slate-200">{fmtBytes(usageData.used_bytes)} / {usageData.quota_bytes ? fmtBytes(usageData.quota_bytes) : 'نامحدود'}</span>
          </div>
          <div class="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
            <div class="h-full bg-primary-500" style="width: {Math.min(100, usageData.pct_used)}%"></div>
          </div>
          <p class="text-xs text-slate-500 mt-1">٪{usageData.pct_used} از سقف · باقی‌مانده {fmtBytes(usageData.remaining_bytes)}</p>
        </div>

        {#if usageData.samples?.length}
          <div>
            <p class="text-sm text-slate-400 mb-1">نمونه‌های مصرف</p>
            <ul class="space-y-1 text-xs text-slate-400">
              {#each usageData.samples as s}
                <li class="flex justify-between">
                  <span>{new Date(s.sampled_at).toLocaleString('fa-IR')}</span>
                  <span>{fmtBytes(s.total_bytes)}</span>
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        <div class="border-t border-slate-800 pt-3 space-y-3">
          <p class="text-sm font-semibold text-slate-200">تمدید / افزایش حجم</p>
          <Input bind:value={usageTopup.gb} label="سقف جدید (GB)" type="number" />
          <Input bind:value={usageTopup.expires_at} label="انقضای جدید" type="datetime-local" />
        </div>
      </div>
    {:else}
      <LoadingSpinner centered />
    {/if}
    {#snippet footer()}
      <Button onclick={topup}><RefreshCw class="w-4 h-4" /> اعمال تمدید</Button>
    {/snippet}
  </Modal>
{/if}

{#if confirmDelete.open}
  <ConfirmDialog
    bind:open={confirmDelete.open}
    title="حذف کلاینت"
    message={`کلاینت «${confirmDelete.name}» حذف شود؟`}
    confirmText="حذف"
    onConfirm={remove}
  />
{/if}
