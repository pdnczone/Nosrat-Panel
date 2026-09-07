<script>
  import { _ } from '../lib/i18n.js';
  import Button from '../lib/components/Button.svelte';
  import { Home } from 'lucide-svelte';

  let { onNavigate = () => {} } = $props();
</script>

<div class="flex items-center justify-center min-h-[60vh]">
  <div class="text-center">
    <div class="text-7xl font-bold text-primary-500 mb-2">404</div>
    <h1 class="text-2xl font-semibold text-slate-100 mb-2">{$_('errors.not_found')}</h1>
    <p class="text-slate-400 mb-6">{$_('errors.not_found_desc')}</p>
    <Button onclick={() => onNavigate('/')}>
      {#snippet icon()}<Home class="w-4 h-4" />{/snippet}
      {$_('errors.back_home')}
    </Button>
  </div>
</div>
