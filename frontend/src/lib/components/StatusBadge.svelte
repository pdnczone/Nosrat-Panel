<script>
  import { _ } from '../i18n.js';

  let { status = 'unknown' } = $props();

  const map = {
    running: { labelKey: 'common.status_labels.running', class: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400' },
    active: { labelKey: 'common.status_labels.active', class: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400' },
    stopped: { labelKey: 'common.status_labels.stopped', class: 'bg-slate-500/15 text-slate-300 border-slate-500/30', dot: 'bg-slate-400' },
    starting: { labelKey: 'common.status_labels.starting', class: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400 animate-pulse' },
    stopping: { labelKey: 'common.status_labels.stopping', class: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400 animate-pulse' },
    error: { labelKey: 'common.status_labels.error', class: 'bg-red-500/15 text-red-300 border-red-500/30', dot: 'bg-red-400' },
    failed: { labelKey: 'common.status_labels.failed', class: 'bg-red-500/15 text-red-300 border-red-500/30', dot: 'bg-red-400' },
    healthy: { labelKey: 'common.status_labels.healthy', class: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400' },
    unhealthy: { labelKey: 'common.status_labels.unhealthy', class: 'bg-red-500/15 text-red-300 border-red-500/30', dot: 'bg-red-400' },
    warning: { labelKey: 'common.status_labels.warning', class: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400' },
    unknown: { labelKey: 'common.status_labels.unknown', class: 'bg-slate-500/15 text-slate-300 border-slate-500/30', dot: 'bg-slate-400' },
    online: { labelKey: 'common.status_labels.online', class: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400' },
    offline: { labelKey: 'common.status_labels.offline', class: 'bg-red-500/15 text-red-300 border-red-500/30', dot: 'bg-red-400' },
    pending: { labelKey: 'common.status_labels.pending', class: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400 animate-pulse' },
    created: { labelKey: 'common.status_labels.created', class: 'bg-slate-500/15 text-slate-300 border-slate-500/30', dot: 'bg-slate-400' },
    connecting: { labelKey: 'common.status_labels.connecting', class: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400 animate-pulse' },
    reconnecting: { labelKey: 'common.status_labels.reconnecting', class: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400 animate-pulse' },
    disconnected: { labelKey: 'common.status_labels.disconnected', class: 'bg-red-500/15 text-red-300 border-red-500/30', dot: 'bg-red-400' },
    over_quota: { labelKey: 'common.status_labels.over_quota', class: 'bg-red-500/15 text-red-300 border-red-500/30', dot: 'bg-red-400' },
    expired: { labelKey: 'common.status_labels.expired', class: 'bg-red-500/15 text-red-300 border-red-500/30', dot: 'bg-red-400' },
    active_status: { labelKey: 'common.status_labels.active_status', class: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400' },
    inactive: { labelKey: 'common.status_labels.inactive', class: 'bg-slate-500/15 text-slate-300 border-slate-500/30', dot: 'bg-slate-400' }
  };

  const info = $derived(map[status] || map.unknown);
  const label = $derived($_(info.labelKey));
</script>

<span class="badge border {info.class}">
  <span class="w-1.5 h-1.5 rounded-full {info.dot}"></span>
  {label}
</span>