<script>
  import { AuthAPI } from '../lib/api.js';
  import { setAuth } from '../lib/auth.js';
  import { _, locale } from '../lib/i18n.js';
  import { toast } from '../lib/toast.js';
  import { Shield, User, Lock, LogIn } from 'lucide-svelte';

  let username = $state('');
  let password = $state('');
  let loading = $state(false);
  let error = $state('');

  async function submit(e) {
    e.preventDefault();
    if (!username || !password) { error = $_('auth.login_failed'); return; }
    loading = true;
    error = '';
    try {
      const res = await AuthAPI.login(username, password);
      setAuth(res.token, res.user);
      toast.success($_('common.loading'));
      location.hash = '/';
    } catch (err) {
      error = err.response?.data?.message || $_('auth.login_failed');
    } finally {
      loading = false;
    }
  }
</script>

<div class="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
  <div class="w-full max-w-md">
    <div class="text-center mb-8">
      <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary-500/15 text-primary-400 mb-4 shadow-glow">
        <Shield class="w-8 h-8" />
      </div>
      <h1 class="text-3xl font-bold text-slate-100">{$_('app.name')}</h1>
      <p class="text-slate-400 mt-2">{$_('app.tagline')}</p>
    </div>

    <div class="card">
      <h2 class="text-xl font-semibold text-slate-100 mb-6 text-center">{$_('auth.title')}</h2>

      <form onsubmit={submit} class="space-y-4">
        <label class="block">
          <span class="label">{$_('auth.username')}</span>
          <div class="relative">
            <User class="w-4 h-4 absolute start-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              bind:value={username}
              class="input ps-10"
              autocomplete="username"
              required
            />
          </div>
        </label>

        <label class="block">
          <span class="label">{$_('auth.password')}</span>
          <div class="relative">
            <Lock class="w-4 h-4 absolute start-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="password"
              bind:value={password}
              class="input ps-10"
              autocomplete="current-password"
              required
            />
          </div>
        </label>

        {#if error}
          <div class="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">{error}</div>
        {/if}

        <button type="submit" disabled={loading} class="btn-primary w-full">
          {#if loading}
            <span class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></span>
          {:else}
            <LogIn class="w-4 h-4" />
          {/if}
          {$_('auth.login')}
        </button>
      </form>
    </div>

    <p class="text-center text-xs text-slate-500 mt-6">
      {$locale === 'fa' ? 'ورود به معنای پذیرش' : 'By signing in you agree to'}
      <a href="#" class="text-primary-400 hover:underline">{$_('app.tagline')}</a>
    </p>
  </div>
</div>
