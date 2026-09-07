<script>
  let { label = '', value = $bindable(''), options = [], placeholder = 'انتخاب کنید...', required = false, disabled = false, class: cls = '' } = $props();
</script>

<label class="block">
  {#if label}<span class="label">{label}{#if required}<span class="text-red-400 ms-1">*</span>{/if}</span>{/if}
  <select bind:value {required} {disabled} class="input {cls}">
    {#if placeholder}<option value="" disabled>{placeholder}</option>{/if}
    {#each options as opt}
      <option value={opt.value}>{opt.label}</option>
    {/each}
  </select>
</label>
