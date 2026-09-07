<!--
  Servers.svelte — manage remote hosts and their node agents.
-->
<script>
  import { onMount } from 'svelte';
  import { _ } from '../lib/i18n.js';
  import { api, ServersAPI } from '../lib/api.js';
  import { getToken } from '../lib/auth.js';
  import { toast } from '../lib/toast.js';
  import {
    installNode,
    testSSH,
    loadNodes,
    startNodeEventStream
  } from '../stores/nodes.js';

  import Card from '../lib/components/Card.svelte';
  import Button from '../lib/components/Button.svelte';
  import Modal from '../lib/components/Modal.svelte';
  import ConfirmDialog from '../lib/components/ConfirmDialog.svelte';
  import Input from '../lib/components/Input.svelte';
  import Select from '../lib/components/Select.svelte';
  import StatusBadge from '../lib/components/StatusBadge.svelte';
  import LoadingSpinner from '../lib/components/LoadingSpinner.svelte';
  import Terminal from '../lib/components/Terminal.svelte';
  import InstallProgress from '../lib/components/InstallProgress.svelte';
  import {
    Plus,
    Trash2,
    TestTube,
    Server as ServerIcon,
    TerminalSquare,
    Download,
    Edit,
    Cpu
  } from 'lucide-svelte';

  let servers = $state([]);
  let loading = $state(false);
  let createOpen = $state(false);
  let editOpen = $state(false);
  let confirmDelete = $state({ open: false, id: null, name: '' });
  let installOpen = $state({ open: false, serverId: null, serverName: '', jobId: null });
  let terminalOpen = $state({ open: false, serverId: null, serverName: '' });

  let draft = $state(emptyDraft());
  let editTargetId = $state(null);
  let editDraft = $state(emptyDraft());
  let testResults = $state({});

  function emptyDraft() {
    return {
      name: '',
      host: '',
      ssh_port: 22,
      ssh_user: 'root',
      auth_method: 'key',
      ssh_key_path: '',
      ssh_private_key: '',
      ssh_password: '',
      node_name: '',
      node_location: 'external',
      metadata: {}
    };
  }

  onMount(async () => {
    loading = true;
    try {
      await load();
    } finally {
      loading = false;
    }
    startNodeEventStream();
  });

  async function load() {
    const data = await ServersAPI.list();
    servers = Array.isArray(data) ? data : data.items || [];
  }

  async function create() {
    try {
      const payload = { ...draft };
      if (!payload.ssh_private_key) delete payload.ssh_private_key;
      if (!payload.ssh_password) delete payload.ssh_password;
      await api.post('/servers', payload);
      toast.success('سرور اضافه شد');
      createOpen = false;
      draft = emptyDraft();
      await load();
    } catch (err) {
      toast.error(err?.response?.data?.error || err.message);
    }
  }

  function openEdit(s) {
    editTargetId = s.id;
    editDraft = {
      name: s.name,
      host: s.host,
      ssh_port: s.ssh_port,
      ssh_user: s.ssh_user,
      auth_method: s.ssh_key_path ? 'key' : 'password',
      ssh_key_path: s.ssh_key_path || '',
      ssh_private_key: '',
      ssh_password: '',
      node_name: s.node_name || '',
      node_location: s.node_location || 'external',
      metadata: {}
    };
    editOpen = true;
  }

  async function saveEdit() {
    try {
      const { name, ...patch } = editDraft;
      await ServersAPI.update(editTargetId, patch);
      toast.success('ذخیره شد');
      editOpen = false;
      await load();
    } catch (err) {
      toast.error(err?.response?.data?.error || err.message);
    }
  }

  async function testOne(s) {
    testResults = { ...testResults, [s.id]: { pending: true } };
    try {
      const res = await testSSH(s.id);
      testResults = { ...testResults, [s.id]: res };
    } catch (err) {
      testResults = { ...testResults, [s.id]: { ssh_ok: false, detail: err.message } };
    }
  }

  async function startInstall(s) {
    const payload = {
      node_name: s.node_name || `${s.name}-node`,
      location: s.node_location || 'external',
      force: false
    };
    try {
      const job = await installNode(s.id, payload);
      installOpen = { open: true, serverId: s.id, serverName: s.name, jobId: job.job_id };
    } catch (err) {
      toast.error(err?.response?.data?.error || err.message);
    }
  }

  async function removeConfirmed() {
    try {
      await ServersAPI.delete(confirmDelete.id);
      servers = servers.filter((x) => x.id !== confirmDelete.id);
      toast.success('حذف شد');
    } catch (err) {
      toast.error(err?.response?.data?.error || err.message);
    }
  }

  function openTerminal(s) {
    terminalOpen = { open: true, serverId: s.id, serverName: s.name };
  }

  function nodeStatusOf(s) {
    if (!s.node_installed) return 'offline';
    return s.node_status || 'offline';
  }
</script>

<div class="space-y-5">
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold text-slate-100">{$_('servers.title')}</h1>
      <p class="text-sm text-slate-400 mt-1">مدیریت سرورها و نودهای nosrat</p>
    </div>
    <Button onclick={() => (createOpen = true)}>
      {#snippet icon()}<Plus class="w-4 h-4" />{/snippet}
      {$_('servers.new_server')}
    </Button>
  </div>

  {#if loading}
    <LoadingSpinner centered />
  {:else if servers.length === 0}
    <Card>
      <p class="text-center py-6 text-slate-500">
        هیچ سروری تعریف نشده. برای شروع یک سرور جدید اضافه کنید.
      </p>
    </Card>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {#each servers as s (s.id)}
        {@const t = testResults[s.id]}
        <div class="card">
          <div class="flex items-start justify-between gap-3 mb-3">
            <div class="flex items-center gap-2 min-w-0">
              <ServerIcon class="w-5 h-5 text-primary-400 flex-shrink-0" />
              <div class="min-w-0">
                <h3 class="font-semibold text-slate-100 truncate">{s.name}</h3>
                <p class="text-xs text-slate-500 font-mono">{s.host}:{s.ssh_port}</p>
              </div>
            </div>
            <StatusBadge status={s.status} />
          </div>

          <dl class="text-sm space-y-1">
            <div class="flex justify-between">
              <dt class="text-slate-500">{$_('servers.fields.username')}</dt>
              <dd class="text-slate-200">{s.ssh_user}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-slate-500">{$_('servers.fields.node_name')}</dt>
              <dd class="text-slate-200">{s.node_name || '—'}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-slate-500">{$_('servers.fields.location')}</dt>
              <dd class="text-slate-200">{s.node_location || '—'}</dd>
            </div>
            <div class="flex justify-between items-center pt-1">
              <dt class="text-slate-500">{$_('servers.node_installed')}</dt>
              <dd>
                {#if s.node_installed}
                  <StatusBadge status={nodeStatusOf(s)} />
                {:else}
                  <span class="badge border bg-slate-500/15 text-slate-300 border-slate-500/30">
                    {$_('servers.node.not_installed')}
                  </span>
                {/if}
              </dd>
            </div>
            {#if t}
              <div class="flex justify-between pt-1 text-xs">
                <dt class="text-slate-500">SSH</dt>
                <dd class={t.ssh_ok ? 'text-emerald-400' : 'text-red-400'}>
                  {t.pending ? '...' : (t.ssh_ok ? 'OK' : (t.detail || 'failed'))}
                </dd>
              </div>
            {/if}
          </dl>

          <div class="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border-slate-800">
            <button class="btn-ghost text-xs" onclick={() => testOne(s)}>
              <TestTube class="w-3 h-3" /> تست SSH
            </button>
            <button class="btn-ghost text-xs" onclick={() => openTerminal(s)}>
              <TerminalSquare class="w-3 h-3" /> {$_('servers.open_terminal')}
            </button>
            <button class="btn-ghost text-xs" onclick={() => startInstall(s)}>
              <Download class="w-3 h-3" /> {$_('servers.install_node')}
            </button>
            <button class="btn-ghost text-xs" onclick={() => openEdit(s)}>
              <Edit class="w-3 h-3" /> {$_('servers.edit')}
            </button>
          </div>
          <div class="flex justify-end mt-2">
            <button
              class="btn-ghost text-xs text-red-400"
              onclick={() => (confirmDelete = { open: true, id: s.id, name: s.name })}
            >
              <Trash2 class="w-3 h-3" /> حذف
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<!-- ── Create server modal ─────────────────────────────────────────────── -->
<Modal bind:open={createOpen} title={$_('servers.new_server')} size="lg">
  <div class="space-y-3">
    <Input label={$_('servers.fields.name')} bind:value={draft.name} required />
    <div class="grid grid-cols-3 gap-3">
      <div class="col-span-2">
        <Input label={$_('servers.fields.host')} bind:value={draft.host} required placeholder="192.168.1.1" />
      </div>
      <Input label={$_('servers.fields.port')} type="number" bind:value={draft.ssh_port} />
    </div>
    <Input label={$_('servers.fields.username')} bind:value={draft.ssh_user} required />
    <Select
      label={$_('servers.fields.auth_method')}
      bind:value={draft.auth_method}
      options={[
        { value: 'key', label: $_('servers.auth_methods.key') },
        { value: 'password', label: $_('servers.auth_methods.password') }
      ]}
    />
    {#if draft.auth_method === 'key'}
      <Input label="ssh_key_path" bind:value={draft.ssh_key_path} placeholder="/root/.ssh/id_rsa" />
      <label class="block">
        <span class="label">{$_('servers.fields.private_key')}</span>
        <textarea
          bind:value={draft.ssh_private_key}
          rows="5"
          class="input font-mono text-xs"
          placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
        ></textarea>
      </label>
    {:else}
      <Input label={$_('servers.fields.password')} type="password" bind:value={draft.ssh_password} />
    {/if}
    <div class="grid grid-cols-2 gap-3">
      <Input label={$_('servers.fields.node_name')} bind:value={draft.node_name} />
      <Select
        label={$_('servers.fields.location')}
        bind:value={draft.node_location}
        options={[
          { value: 'iran', label: $_('nodes.locations.iran') },
          { value: 'external', label: $_('nodes.locations.external') }
        ]}
      />
    </div>
  </div>
  {#snippet footer()}
    <Button variant="ghost" onclick={() => (createOpen = false)}>انصراف</Button>
    <Button onclick={create}>ذخیره</Button>
  {/snippet}
</Modal>

<!-- ── Edit server modal ────────────────────────────────────────────────── -->
<Modal bind:open={editOpen} title="ویرایش سرور" size="lg">
  <div class="space-y-3">
    <Input label={$_('servers.fields.name')} bind:value={editDraft.name} disabled />
    <div class="grid grid-cols-3 gap-3">
      <div class="col-span-2">
        <Input label={$_('servers.fields.host')} bind:value={editDraft.host} />
      </div>
      <Input label={$_('servers.fields.port')} type="number" bind:value={editDraft.ssh_port} />
    </div>
    <Input label={$_('servers.fields.username')} bind:value={editDraft.ssh_user} />
    <Select
      label={$_('servers.fields.auth_method')}
      bind:value={editDraft.auth_method}
      options={[
        { value: 'key', label: $_('servers.auth_methods.key') },
        { value: 'password', label: $_('servers.auth_methods.password') }
      ]}
    />
    {#if editDraft.auth_method === 'key'}
      <Input label="ssh_key_path" bind:value={editDraft.ssh_key_path} />
      <label class="block">
        <span class="label">{$_('servers.fields.private_key')} (برای تغییر مقدار دهید)</span>
        <textarea bind:value={editDraft.ssh_private_key} rows="5" class="input font-mono text-xs"></textarea>
      </label>
    {:else}
      <Input label={$_('servers.fields.password')} type="password" bind:value={editDraft.ssh_password} />
    {/if}
    <div class="grid grid-cols-2 gap-3">
      <Input label={$_('servers.fields.node_name')} bind:value={editDraft.node_name} />
      <Select
        label={$_('servers.fields.location')}
        bind:value={editDraft.node_location}
        options={[
          { value: 'iran', label: $_('nodes.locations.iran') },
          { value: 'external', label: $_('nodes.locations.external') }
        ]}
      />
    </div>
  </div>
  {#snippet footer()}
    <Button variant="ghost" onclick={() => (editOpen = false)}>انصراف</Button>
    <Button onclick={saveEdit}>ذخیره</Button>
  {/snippet}
</Modal>

<ConfirmDialog
  bind:open={confirmDelete.open}
  title="حذف سرور"
  message={`سرور «${confirmDelete.name}» حذف شود؟`}
  confirmText="حذف"
  onConfirm={removeConfirmed}
/>

<!-- ── Install progress modal ─────────────────────────────────────────── -->
<Modal
  open={installOpen.open}
  onclose={() => (installOpen = { open: false })}
  title={$_('nodes.install.title')}
  size="lg"
>
  <InstallProgress
    serverId={installOpen.serverId}
    serverName={installOpen.serverName}
    onClose={() => (installOpen = { open: false })}
  />
  {#snippet footer()}
    <Button variant="ghost" onclick={() => (installOpen = { open: false })}>بستن</Button>
  {/snippet}
</Modal>

<!-- ── SSH terminal modal ─────────────────────────────────────────────── -->
<Modal
  open={terminalOpen.open}
  onclose={() => (terminalOpen = { open: false })}
  title={`${$_('nodes.terminal.title')} — ${terminalOpen.serverName}`}
  size="xl"
>
  <div style="height: 480px;">
    <Terminal
      url={
        ServersAPI.terminalUrl(terminalOpen.serverId) +
        `&token=${encodeURIComponent(getToken() || '')}`
      }
      cols={80}
      rows={24}
    />
  </div>
  {#snippet footer()}
    <Button variant="ghost" onclick={() => (terminalOpen = { open: false })}>بستن</Button>
  {/snippet}
</Modal>