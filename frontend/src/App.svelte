<script>
  import { onMount } from 'svelte';
  import { auth, isAuthenticated } from './lib/auth.js';
  import { locale } from './lib/i18n.js';
  import { openChannel, closeAll } from './lib/ws.js';
  import { notify } from './stores/notifications.js';
  import Sidebar from './lib/components/Sidebar.svelte';
  import Topbar from './lib/components/Topbar.svelte';
  import LoadingSpinner from './lib/components/LoadingSpinner.svelte';

  import Login from './routes/Login.svelte';
  import Dashboard from './routes/Dashboard.svelte';
  import Tunnels from './routes/Tunnels.svelte';
  import TunnelDetail from './routes/TunnelDetail.svelte';
  import CreateTunnel from './routes/CreateTunnel.svelte';
  import Crypto from './routes/Crypto.svelte';
  import Health from './routes/Health.svelte';
  import Speed from './routes/Speed.svelte';
  import Servers from './routes/Servers.svelte';
  import Users from './routes/Users.svelte';
  import Settings from './routes/Settings.svelte';
  import NotFound from './routes/NotFound.svelte';

  let currentPath = $state(parseHash());
  let sidebarCollapsed = $state(false);
  let sidebarOpenMobile = $state(false);

  function parseHash() {
    const h = location.hash.replace(/^#/, '') || '/';
    return h;
  }

  function onHashChange() {
    currentPath = parseHash();
    sidebarOpenMobile = false;
  }

  function navigate(path) {
    location.hash = path;
  }

  onMount(() => {
    window.addEventListener('hashchange', onHashChange);

    // Apply initial RTL/LTR from locale
    document.documentElement.dir = $locale === 'fa' ? 'rtl' : 'ltr';
    document.documentElement.lang = $locale;

    // Initialize realtime channel when authenticated
    const unsub = auth.subscribe((a) => {
      if (a.token && a.ready) {
        const ch = openChannel('/ws/events');
        ch.subscribe((msg) => {
          if (msg?.type === 'notification') {
            notify(msg.message, msg.level || 'info');
          }
        });
      }
    });

    return () => {
      window.removeEventListener('hashchange', onHashChange);
      unsub();
      closeAll();
    };
  });

  function matchRoute(p) {
    if (p === '/tunnels/create' || p === '/tunnels/new') return { route: 'create-tunnel' };
    if (p.match(/^\/tunnels\/[^/]+$/)) return { route: 'tunnel-detail', id: p.split('/')[2] };
    if (p === '/' || p === '') return { route: 'dashboard' };
    return { route: p.replace(/^\//, '') };
  }

  const route = $derived(matchRoute(currentPath));
</script>

{#if !$auth.ready}
  <div class="h-screen flex items-center justify-center bg-slate-950">
    <LoadingSpinner size="lg" text="در حال بارگذاری..." centered />
  </div>
{:else if !$isAuthenticated && currentPath !== '/login'}
  <Login />
{:else if currentPath === '/login'}
  <Login />
{:else}
  <div class="flex h-screen bg-slate-950">
    {#if sidebarOpenMobile}
      <div class="fixed inset-0 bg-black/50 z-40 lg:hidden" onclick={() => (sidebarOpenMobile = false)}></div>
    {/if}

    <div class="hidden lg:block">
      <Sidebar {currentPath} onNavigate={navigate} collapsed={sidebarCollapsed} />
    </div>

    <div class="fixed inset-y-0 start-0 z-50 lg:hidden {sidebarOpenMobile ? 'translate-x-0' : '-translate-x-full rtl:translate-x-full'} transition-transform">
      <Sidebar {currentPath} onNavigate={navigate} collapsed={false} />
    </div>

    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
      <Topbar onToggleSidebar={() => { sidebarCollapsed = !sidebarCollapsed; sidebarOpenMobile = !sidebarOpenMobile; }} />
      <main class="flex-1 overflow-y-auto p-4 md:p-6">
        {#if route.route === 'dashboard'}
          <Dashboard onNavigate={navigate} />
        {:else if route.route === 'tunnels'}
          <Tunnels onNavigate={navigate} />
        {:else if route.route === 'tunnel-detail'}
          <TunnelDetail id={route.id} onNavigate={navigate} />
        {:else if route.route === 'create-tunnel'}
          <CreateTunnel onNavigate={navigate} />
        {:else if route.route === 'crypto'}
          <Crypto />
        {:else if route.route === 'health'}
          <Health />
        {:else if route.route === 'speed'}
          <Speed />
        {:else if route.route === 'servers'}
          <Servers />
        {:else if route.route === 'users'}
          <Users />
        {:else if route.route === 'settings'}
          <Settings />
        {:else}
          <NotFound onNavigate={navigate} />
        {/if}
      </main>
    </div>
  </div>
{/if}
