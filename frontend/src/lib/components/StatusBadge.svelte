<script>
  let { status = 'unknown' } = $props();

  const map = {
    running: { label: 'در حال اجرا', class: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400' },
    active: { label: 'فعال', class: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400' },
    stopped: { label: 'متوقف', class: 'bg-slate-500/15 text-slate-300 border-slate-500/30', dot: 'bg-slate-400' },
    starting: { label: 'در حال راه‌اندازی', class: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400 animate-pulse' },
    stopping: { label: 'در حال توقف', class: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400 animate-pulse' },
    error: { label: 'خطا', class: 'bg-red-500/15 text-red-300 border-red-500/30', dot: 'bg-red-400' },
    failed: { label: 'ناموفق', class: 'bg-red-500/15 text-red-300 border-red-500/30', dot: 'bg-red-400' },
    healthy: { label: 'سالم', class: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400' },
    unhealthy: { label: 'ناسالم', class: 'bg-red-500/15 text-red-300 border-red-500/30', dot: 'bg-red-400' },
    warning: { label: 'هشدار', class: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400' },
    unknown: { label: 'نامشخص', class: 'bg-slate-500/15 text-slate-300 border-slate-500/30', dot: 'bg-slate-400' },
    online: { label: 'آنلاین', class: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400' },
    offline: { label: 'آفلاین', class: 'bg-red-500/15 text-red-300 border-red-500/30', dot: 'bg-red-400' }
  };

  const info = $derived(map[status] || map.unknown);
</script>

<span class="badge border {info.class}">
  <span class="w-1.5 h-1.5 rounded-full {info.dot}"></span>
  {info.label}
</span>
