<script>
  import { auth, isAdmin, clearAuth } from '../auth.js';
  import { wsStatus } from '../ws.js';
  import { _ } from '../i18n.js';
  import {
    LayoutDashboard,
    Network,
    Lock,
    Activity,
    Gauge,
    Server,
    Users,
    Settings,
    LogOut,
    Shield,
    Cpu,
    UserCheck
  } from 'lucide-svelte';

  let { currentPath = '/', onNavigate = () => {}, collapsed = false } = $props();

  const items = $derived([
    { path: '/', icon: LayoutDashboard, label: $_('nav.dashboard') },
    { path: '/tunnels', icon: Network, label: $_('nav.tunnels') },
    { path: '/crypto', icon: Lock, label: $_('nav.crypto') },
    { path: '/health', icon: Activity, label: $_('nav.health') },
    { path: '/speed', icon: Gauge, label: $_('nav.speed') },
    { path: '/servers', icon: Server, label: $_('nav.servers') },
    { path: '/nodes', icon: Cpu, label: $_('nav.nodes') },
    { path: '/users', icon: Users, label: $_('nav.users'), adminOnly: true },
    { path: '/clients', icon: UserCheck, label: $_('nav.clients'), adminOnly: true },
    { path: '/settings', icon: Settings, label: $_('nav.settings') }
  ]);

  function isActive(path) {
    if (path === '/') return currentPath === '/';
    return currentPath.startsWith(path);
  }

  function logout() {
    clearAuth();
    location.href = '/login';
  }

  const wsState = $derived($wsStatus);
  const wsClass = $derived({
    connected: 'bg-emerald-400',
    connecting: 'bg-amber-400 animate-pulse',
    reconnecting: 'bg-amber-400 animate-pulse',
    disconnected: 'bg-red-400'
  }[wsState] || 'bg-slate-500');

  const wsLabel = $derived({
    connected: $_('common.status_labels.connected') || 'Connected',
    connecting: $_('common.status_labels.connecting') || 'Connecting...',
    reconnecting: $_('common.status_labels.reconnecting') || 'Reconnecting...',
    disconnected: $_('common.status_labels.disconnected') || 'Disconnected'
  }[wsState] || $_('common.status_labels.unknown'));
</script>

<aside
  class="bg-slate-950/80 backdrop-blur-sm border-slate-800 h-screen sticky top-0 flex flex-col transition-all duration-200
         {collapsed ? 'w-16' : 'w-64'}
         border-l rtl:border-l rtl:border-r-0"
>
  <div class="px-4 py-4 border-b border-slate-800 flex items-center gap-3">
    <div class="w-9 h-9 rounded-lg bg-primary-500/15 flex items-center justify-center text-primary-400 flex-shrink-0">
      <Shield class="w-5 h-5" />
    </div>
    {#if !collapsed}
      <div class="min-w-0">
        <h1 class="font-extrabold text-slate-100 truncate tracking-widest text-lg">NOSRAT</h1>
        <p class="text-xs text-slate-500 truncate">WebUI</p>
      </div>
    {/if}
  </div>

  <nav class="flex-1 overflow-y-auto py-3 px-2 space-y-1">
    {#each items as item}
      {#if !item.adminOnly || $isAdmin}
        {@const active = isActive(item.path)}
        <a
          href={`#${item.path}`}
          onclick={(e) => { e.preventDefault(); onNavigate(item.path); }}
          class="nav-link {active ? 'nav-link-active' : ''}"
          title={item.label}
        >
          <item.icon class="w-5 h-5 flex-shrink-0" />
          {#if !collapsed}<span class="truncate">{item.label}</span>{/if}
        </a>
      {/if}
    {/each}
  </nav>

  <div class="p-3 border-t border-slate-800">
    {#if !collapsed}
      <div class="flex items-center gap-2 mb-3 text-xs">
        <span class="w-2 h-2 rounded-full {wsClass}"></span>
        <span class="text-slate-400">{wsLabel}</span>
      </div>
    {/if}

    {#if !collapsed}
      <div class="flex items-center gap-3 mb-2 p-2 rounded-lg bg-slate-900/50">
        <div class="w-8 h-8 rounded-full bg-primary-500/20 flex items-center justify-center text-primary-300 font-semibold text-sm">
          {$auth.user?.username?.[0]?.toUpperCase() ?? '?'}
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-sm text-slate-200 truncate">{$auth.user?.username}</p>
          <p class="text-xs text-slate-500 truncate">{$auth.user?.role}</p>
        </div>
      </div>
    {/if}

    <button
      onclick={logout}
      class="nav-link w-full text-red-400 hover:bg-red-500/10 hover:text-red-300"
      title={$_('nav.logout')}
    >
      <LogOut class="w-5 h-5 flex-shrink-0" />
      {#if !collapsed}<span>{$_('nav.logout')}</span>{/if}
    </button>
  </div>
</aside>