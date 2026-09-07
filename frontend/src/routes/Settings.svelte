<script>
  import { onMount } from 'svelte';
  import { _ } from '../lib/i18n.js';
  import { SettingsAPI } from '../lib/api.js';
  import { theme, setTheme } from '../lib/theme.js';
  import { locale, setLocale } from '../lib/i18n.js';
  import Card from '../lib/components/Card.svelte';
  import Button from '../lib/components/Button.svelte';
  import Input from '../lib/components/Input.svelte';
  import Select from '../lib/components/Select.svelte';
  import LoadingSpinner from '../lib/components/LoadingSpinner.svelte';
  import { toast } from '../lib/toast.js';
  import { Save, Download, Upload, Database } from 'lucide-svelte';

  let activeTab = $state('general');
  let settings = $state({
    general: { site_name: 'nosrat', language: 'fa', theme: 'dark', timezone: 'Asia/Tehran', auto_refresh: true },
    security: { two_factor: false, session_timeout: 60, password_policy: 'strong', audit_log: true },
    network: { api_listen: '0.0.0.0:8000', public_url: '', dns_servers: '1.1.1.1,8.8.8.8', mtu: 1400 },
    backup: { last_backup: null }
  });
  let loading = $state(true);
  let saving = $state(false);
  let fileInput;

  const TABS = ['general', 'security', 'network', 'backup'];

  onMount(async () => {
    try {
      const data = await SettingsAPI.get();
      const flat = {};
      (Array.isArray(data) ? data : []).forEach((d) => {
        flat[d.key] = d.value;
      });
      const merged = { ...settings };
      for (const section of ['general', 'security', 'network', 'backup']) {
        const next = { ...settings[section] };
        for (const key of Object.keys(settings[section])) {
          const k = `${section}.${key}`;
          if (k in flat) next[key] = flat[k];
        }
        merged[section] = next;
      }
      settings = merged;
    } finally {
      loading = false;
    }
  });

  async function save(section) {
    saving = true;
    try {
      await SettingsAPI.update(section, settings[section]);
      toast.success($_('settings.saved'));
    } finally {
      saving = false;
    }
  }

  async function backup() {
    const blob = await SettingsAPI.backup();
    settings.backup.last_backup = new Date().toISOString();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `nosrat-backup-${new Date().toISOString().slice(0, 10)}.tar.gz`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function restore(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    await SettingsAPI.restore(fd);
    toast.success($_('settings.saved'));
  }
</script>

<div class="space-y-5">
  <h1 class="text-2xl font-bold text-slate-100">{$_('settings.title')}</h1>

  {#if loading}
    <LoadingSpinner centered />
  {:else}
    <div class="border-b border-slate-800 flex gap-1">
      {#each TABS as t}
        <button
          class="px-4 py-2 text-sm font-medium border-b-2 transition-colors {activeTab === t ? 'border-primary-500 text-primary-400' : 'border-transparent text-slate-400 hover:text-slate-200'}"
          onclick={() => (activeTab = t)}
        >{$_(`settings.tabs.${t}`)}</button>
      {/each}
    </div>

    {#if activeTab === 'general'}
      <Card>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input label={$_('settings.general.site_name')} bind:value={settings.general.site_name} />
          <Select label={$_('settings.general.language')} bind:value={settings.general.language} options={[
            { value: 'fa', label: 'فارسی' }, { value: 'en', label: 'English' }
          ]} />
          <Select label={$_('settings.general.theme')} bind:value={settings.general.theme} options={[
            { value: 'dark', label: 'Dark' }, { value: 'light', label: 'Light' }
          ]} />
          <Input label={$_('settings.general.timezone')} bind:value={settings.general.timezone} />
          <label class="flex items-center gap-2 md:col-span-2">
            <input type="checkbox" bind:checked={settings.general.auto_refresh} class="rounded" />
            <span class="text-sm text-slate-300">{$_('settings.general.auto_refresh')}</span>
          </label>
        </div>
        <div class="mt-4 pt-4 border-t border-slate-800 flex justify-end">
          <Button loading={saving} onclick={() => save('general')}>
            {#snippet icon()}<Save class="w-4 h-4" />{/snippet}
            {$_('common.save')}
          </Button>
        </div>
      </Card>
    {:else if activeTab === 'security'}
      <Card>
        <div class="space-y-4">
          <label class="flex items-center justify-between p-3 bg-slate-950 rounded-lg">
            <span class="text-sm text-slate-300">{$_('settings.security.two_factor')}</span>
            <input type="checkbox" bind:checked={settings.security.two_factor} class="rounded" />
          </label>
          <Input label={$_('settings.security.session_timeout')} type="number" bind:value={settings.security.session_timeout} />
          <Select label={$_('settings.security.password_policy')} bind:value={settings.security.password_policy} options={[
            { value: 'basic', label: 'Basic' },
            { value: 'strong', label: 'Strong' },
            { value: 'paranoid', label: 'Paranoid' }
          ]} />
          <label class="flex items-center justify-between p-3 bg-slate-950 rounded-lg">
            <span class="text-sm text-slate-300">{$_('settings.security.audit_log')}</span>
            <input type="checkbox" bind:checked={settings.security.audit_log} class="rounded" />
          </label>
        </div>
        <div class="mt-4 pt-4 border-t border-slate-800 flex justify-end">
          <Button loading={saving} onclick={() => save('security')}>
            {#snippet icon()}<Save class="w-4 h-4" />{/snippet}
            {$_('common.save')}
          </Button>
        </div>
      </Card>
    {:else if activeTab === 'network'}
      <Card>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input label={$_('settings.network.api_listen')} bind:value={settings.network.api_listen} />
          <Input label={$_('settings.network.public_url')} bind:value={settings.network.public_url} placeholder="https://example.com" />
          <Input label={$_('settings.network.dns_servers')} bind:value={settings.network.dns_servers} />
          <Input label={$_('settings.network.mtu')} type="number" bind:value={settings.network.mtu} />
        </div>
        <div class="mt-4 pt-4 border-t border-slate-800 flex justify-end">
          <Button loading={saving} onclick={() => save('network')}>
            {#snippet icon()}<Save class="w-4 h-4" />{/snippet}
            {$_('common.save')}
          </Button>
        </div>
      </Card>
    {:else if activeTab === 'backup'}
      <Card>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="p-4 bg-slate-950 rounded-lg border border-slate-800">
            <div class="flex items-center gap-2 mb-2"><Database class="w-4 h-4 text-primary-400" /><span class="font-semibold text-slate-200">{$_('settings.backup.last_backup')}</span></div>
            <p class="text-sm text-slate-400">{settings.backup.last_backup ?? '—'}</p>
            <Button variant="secondary" fullWidth onclick={backup} class="mt-3">
              {#snippet icon()}<Download class="w-4 h-4" />{/snippet}
              {$_('settings.backup.create')}
            </Button>
          </div>
          <div class="p-4 bg-slate-950 rounded-lg border border-slate-800">
            <div class="flex items-center gap-2 mb-2"><Upload class="w-4 h-4 text-primary-400" /><span class="font-semibold text-slate-200">{$_('settings.backup.restore')}</span></div>
            <p class="text-sm text-slate-400 mb-3">{$_('settings.backup.upload')}</p>
            <input type="file" bind:this={fileInput} onchange={restore} accept=".gz,.tar,.zip" class="hidden" />
            <Button variant="secondary" fullWidth onclick={() => fileInput?.click()}>
              {$_('settings.backup.upload')}
            </Button>
          </div>
        </div>
      </Card>
    {/if}
  {/if}
</div>
