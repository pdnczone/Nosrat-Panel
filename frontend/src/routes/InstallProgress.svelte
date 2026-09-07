<!--
  InstallProgress.svelte — polls /api/servers/{id}/install-status and renders
  the live log with a progress bar.
-->
<script>
  import { onMount, onDestroy } from 'svelte';
  import { ServersAPI } from '../lib/api.js';
  import { _ } from '../lib/i18n.js';
  import Button from './Button.svelte';

  let { serverId, serverName = '', onClose = () => {} } = $props();

  let status = $state('pending');
  let progress = $state(0);
  let logText = $state('');
  let error = $state(null);
  let lines = $state(0);
  let timer = null;
  let scrollEl;

  async function poll() {
    try {
      const res = await ServersAPI.installStatus(serverId, lines);
      lines += (res.tail || '').split('\n').filter(Boolean).length;
      logText += (res.tail || '');
      status = res.status;
      progress = res.progress || 0;
      error = res.error || null;
      // autoscroll
      if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
    } catch (err) {
      // likely 404 = no job yet; ignore silently
    }
  }

  onMount(() => {
    poll();
    timer = setInterval(poll, 1500);
  });

  onDestroy(() => {
    if (timer) clearInterval(timer);
  });
</script>

<div class="space-y-3">
  <p class="text-sm text-slate-300">
    {$_('nodes.install.intro')}
  </p>
  <div class="flex items-center gap-3">
    <span class="text-xs text-slate-500">{serverName}</span>
    <span class="badge border bg-slate-800 text-slate-200 border-slate-700">{status}</span>
    <span class="ml-auto text-xs text-slate-500">{progress}%</span>
  </div>
  <div class="h-1.5 bg-slate-800 rounded overflow-hidden">
    <div
      class="h-full transition-all"
      class:bg-emerald-500={status === 'success'}
      class:bg-red-500={status === 'failed'}
      class:bg-primary-500={status === 'running' || status === 'pending'}
      style={`width: ${Math.max(2, progress)}%`}
    ></div>
  </div>
  <div
    bind:this={scrollEl}
    class="bg-slate-950 border border-slate-800 rounded-lg p-3 h-72 overflow-y-auto font-mono text-xs leading-relaxed text-slate-200 whitespace-pre-wrap"
  >{logText || '⏳ waiting for first output…'}</div>
  {#if error}
    <div class="text-xs text-red-400">{error}</div>
  {/if}
</div>

{#snippet footer()}
  <Button variant="ghost" onclick={onClose}>{$_('nodes.actions.close')}</Button>
{/snippet}