<script>
  let { title = '', subtitle = '', class: cls = '', children, footer = null, headerActions = null } = $props();
</script>

<div class="card {cls}">
  {#if title || headerActions}
    <div class="flex items-start justify-between mb-4 gap-3">
      <div>
        {#if title}<h3 class="text-lg font-semibold text-slate-100">{title}</h3>{/if}
        {#if subtitle}<p class="text-sm text-slate-400 mt-0.5">{subtitle}</p>{/if}
      </div>
      {#if headerActions}<div class="flex items-center gap-2">{@render headerActions()}</div>{/if}
    </div>
  {/if}
  <div>{@render children?.()}</div>
  {#if footer}
    <div class="mt-4 pt-4 border-t border-slate-800">{@render footer()}</div>
  {/if}
</div>
