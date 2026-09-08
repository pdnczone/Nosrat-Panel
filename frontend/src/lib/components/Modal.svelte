<script>
  import { fly, fade } from 'svelte/transition';
  import { _ } from '../i18n.js';

  let { open = $bindable(false), title = '', size = 'md', closeOnBackdrop = true, children, footer = null } = $props();

  const sizeClass = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl'
  }[size] || 'max-w-md';

  function close() {
    if (closeOnBackdrop) open = false;
  }

  function onKey(e) {
    if (e.key === 'Escape') open = false;
  }
</script>

<svelte:window onkeydown={onKey} />

{#if open}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm"
    transition:fade={{ duration: 150 }}
    onclick={close}
    role="presentation"
  >
    <div
      class="w-full {sizeClass} bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl"
      transition:fly={{ y: 20, duration: 200 }}
      onclick={(e) => e.stopPropagation()}
      role="dialog"
      aria-modal="true"
    >
      {#if title}
        <div class="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <h3 class="text-lg font-semibold text-slate-100">{title}</h3>
          <button onclick={() => (open = false)} class="btn-ghost p-1 rounded-md" aria-label={$_('common.close')}>
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M6 18L18 6"/></svg>
          </button>
        </div>
      {/if}
      <div class="p-5">{@render children?.()}</div>
      {#if footer}
        <div class="px-5 py-3 border-t border-slate-800 flex items-center justify-end gap-2">{@render footer()}</div>
      {/if}
    </div>
  </div>
{/if}