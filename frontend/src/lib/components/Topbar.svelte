<script>
  import { Menu, Bell, Search, Sun, Moon, Languages } from 'lucide-svelte';
  import { theme, toggleTheme } from '../theme.js';
  import { locale, toggleLocale, _ } from '../i18n.js';
  import { notifications, unreadCount } from '../../stores/notifications.js';
  import { toasts, ICONS, COLORS, dismiss as dismissToast } from '../toast.js';

  let { onToggleSidebar = () => {}, title = '' } = $props();

  let notifOpen = $state(false);
  let userNotifOpen = $state(false);

  function currentTitle(path) {
    const map = {
      '/': $_('nav.dashboard'),
      '/tunnels': $_('nav.tunnels'),
      '/crypto': $_('nav.crypto'),
      '/health': $_('nav.health'),
      '/speed': $_('nav.speed'),
      '/servers': $_('nav.servers'),
      '/users': $_('nav.users'),
      '/settings': $_('nav.settings'),
      '/create-tunnel': $_('tunnels.create')
    };
    for (const k of Object.keys(map)) {
      if (k !== '/' && path.startsWith(k)) return map[k];
    }
    return map['/'];
  }
</script>

<header class="bg-slate-950/80 backdrop-blur border-b border-slate-800 sticky top-0 z-30">
  <div class="flex items-center gap-3 px-4 h-14">
    <button onclick={onToggleSidebar} class="btn-ghost p-2 lg:hidden" aria-label={$_('nav.menu') || 'Menu'}>
      <Menu class="w-5 h-5" />
    </button>

    <h2 class="text-lg font-semibold text-slate-100 hidden sm:block">{title || currentTitle(location.hash.replace('#', '') || '/')}</h2>

    <div class="flex-1"></div>

    <div class="hidden md:block relative">
      <Search class="w-4 h-4 absolute start-3 top-1/2 -translate-y-1/2 text-slate-500" />
      <input type="search" placeholder={$_('common.search')} class="input ps-10 w-64 bg-slate-900" />
    </div>

    <button onclick={toggleLocale} class="btn-ghost p-2" title={$_('settings.general.language') || 'Change language'}>
      <Languages class="w-5 h-5" />
      <span class="text-xs uppercase ms-1 hidden sm:inline">{$locale}</span>
    </button>

    <button onclick={toggleTheme} class="btn-ghost p-2" title={$_('settings.general.theme') || 'Theme'}>
      {#if $theme === 'dark'}<Sun class="w-5 h-5" />{:else}<Moon class="w-5 h-5" />{/if}
    </button>

    <div class="relative">
      <button onclick={() => (notifOpen = !notifOpen)} class="btn-ghost p-2 relative" aria-label={$_('nav.notifications')}>
        <Bell class="w-5 h-5" />
        {#if unreadCount($notifications) > 0}
          <span class="absolute top-1 end-1 w-2 h-2 bg-red-500 rounded-full"></span>
        {/if}
      </button>

      {#if notifOpen}
        <div class="absolute end-0 mt-2 w-80 max-h-96 overflow-auto bg-slate-900 border border-slate-800 rounded-lg shadow-2xl">
          <div class="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
            <span class="font-medium text-slate-200">{$_('nav.notifications')}</span>
            <button class="text-xs text-primary-400 hover:text-primary-300" onclick={() => (notifOpen = false)}>
              {$_('common.close')}
            </button>
          </div>
          {#if $notifications.length === 0}
            <div class="p-6 text-center text-slate-500 text-sm">{$_('common.empty')}</div>
          {:else}
            {#each $notifications.slice(0, 20) as n}
              <div class="px-4 py-2 border-b border-slate-800/50 text-sm hover:bg-slate-800/30">
                <div class="flex items-start gap-2">
                  <span class="badge {COLORS[n.level]}">{ICONS[n.level]}</span>
                  <span class="text-slate-300 flex-1">{n.message}</span>
                </div>
              </div>
            {/each}
          {/if}
        </div>
      {/if}
    </div>
  </div>
</header>

<div class="fixed top-4 end-4 z-50 flex flex-col gap-2 pointer-events-none">
  {#each $toasts as t (t.id)}
    <div class="pointer-events-auto border rounded-lg px-4 py-3 shadow-lg min-w-[200px] backdrop-blur {COLORS[t.type]}" role="alert">
      <div class="flex items-center gap-2">
        <span class="font-bold">{ICONS[t.type]}</span>
        <span class="text-sm flex-1">{t.message}</span>
        <button onclick={() => dismissToast(t.id)} class="text-current opacity-60 hover:opacity-100">✕</button>
      </div>
    </div>
  {/each}
</div>