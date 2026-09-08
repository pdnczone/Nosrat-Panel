<script>
  import { _ } from '../i18n.js';

  let { label = '', type = 'text', value = $bindable(''), placeholder = '', error = '', hint = '', required = false, disabled = false, icon = null, class: cls = '' } = $props();
</script>

<label class="block">
  {#if label}
    <span class="label">{label}{#if required}<span class="text-red-400 ms-1">*</span>{/if}</span>
  {/if}
  <div class="relative">
    {#if icon}
      <span class="absolute inset-y-0 start-0 flex items-center ps-3 text-slate-500">{@render icon()}</span>
    {/if}
    <input
      {type}
      bind:value
      {placeholder}
      {required}
      {disabled}
      class="input {icon ? 'ps-10' : ''} {error ? 'border-red-500' : ''} {cls}"
    />
  </div>
  {#if error}
    <span class="text-xs text-red-400 mt-1 block">{error}</span>
  {:else if hint}
    <span class="text-xs text-slate-500 mt-1 block">{hint}</span>
  {/if}
</label>