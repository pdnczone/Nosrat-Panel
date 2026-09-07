<script>
  import { useNavigate } from 'svelte-routing';
  import { _ } from '../i18n.js';
  import StatusBadge from './StatusBadge.svelte';

  let { tunnel } = $props();

  function open() {
    location.hash = `/tunnels/${tunnel.id}`;
  }
</script>

<button
  onclick={open}
  class="text-start w-full bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-primary-500/50 rounded-xl p-4 transition-all group"
>
  <div class="flex items-start justify-between mb-2 gap-2">
    <div class="min-w-0 flex-1">
      <h4 class="font-semibold text-slate-100 truncate">{tunnel.name}</h4>
      <p class="text-xs text-slate-500 mt-0.5">{tunnel.type ?? '—'} · {tunnel.server ?? '—'}</p>
    </div>
    <StatusBadge status={tunnel.status} />
  </div>

  <div class="grid grid-cols-3 gap-2 mt-3 text-center">
    <div>
      <div class="text-xs text-slate-500">ورودی</div>
      <div class="text-sm font-mono text-emerald-300">{tunnel.rx ?? '0 B'}</div>
    </div>
    <div>
      <div class="text-xs text-slate-500">خروجی</div>
      <div class="text-sm font-mono text-cyan-300">{tunnel.tx ?? '0 B'}</div>
    </div>
    <div>
      <div class="text-xs text-slate-500">پینگ</div>
      <div class="text-sm font-mono text-amber-300">{tunnel.ping ?? '—'}</div>
    </div>
  </div>

  {#if tunnel.uptime}
    <div class="mt-3 text-xs text-slate-500 text-start">آپتایم: {tunnel.uptime}</div>
  {/if}
</button>
