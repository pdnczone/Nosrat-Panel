<script>
  let {
    columns = [],
    rows = [],
    loading = false,
    emptyText = 'داده‌ای موجود نیست',
    rowKey = 'id',
    onRowClick = null,
    striped = true
  } = $props();
</script>

<div class="overflow-x-auto rounded-lg border border-slate-800">
  <table class="w-full text-sm">
    <thead class="bg-slate-900/80 text-slate-400 text-xs uppercase">
      <tr>
        {#each columns as col}
          <th class="px-4 py-3 text-start font-medium whitespace-nowrap">{col.label}</th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#if loading}
        <tr><td colspan={columns.length} class="text-center py-10 text-slate-500">در حال بارگذاری...</td></tr>
      {:else if rows.length === 0}
        <tr><td colspan={columns.length} class="text-center py-10 text-slate-500">{emptyText}</td></tr>
      {:else}
        {#each rows as row, i (row[rowKey] ?? i)}
          <tr
            class="border-t border-slate-800 hover:bg-slate-800/40 transition-colors {striped && i % 2 ? 'bg-slate-900/30' : ''} {onRowClick ? 'cursor-pointer' : ''}"
            onclick={() => onRowClick?.(row)}
          >
            {#each columns as col}
              <td class="px-4 py-3 text-slate-200">
                {#if col.render}
                  {@render col.render(row)}
                {:else}
                  {row[col.key] ?? '—'}
                {/if}
              </td>
            {/each}
          </tr>
        {/each}
      {/if}
    </tbody>
  </table>
</div>
