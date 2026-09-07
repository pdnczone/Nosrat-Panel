<script>
  let { size = 'md', text = '', centered = false } = $props();
  const sizeClass = { sm: 'w-4 h-4 border-2', md: 'w-6 h-6 border-2', lg: 'w-10 h-10 border-4' }[size] || 'w-6 h-6 border-2';
</script>

<div class="flex items-center gap-3 {centered ? 'justify-center min-h-[200px]' : ''}">
  <span class="inline-block rounded-full animate-spin border-current border-t-transparent {sizeClass} text-primary-500"></span>
  {#if text}<span class="text-slate-400 text-sm">{text}</span>{/if}
</div>
