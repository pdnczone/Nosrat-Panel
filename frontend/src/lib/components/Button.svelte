<script>
  let { variant = 'primary', type = 'button', disabled = false, loading = false, fullWidth = false, onclick = () => {}, children, icon = null, class: cls = '' } = $props();
  const variantClass = {
    primary: 'btn-primary',
    secondary: 'btn-secondary',
    danger: 'btn-danger',
    ghost: 'btn-ghost'
  }[variant] || 'btn-primary';
</script>

<button
  {type}
  {disabled}
  onclick={onclick}
  class="{variantClass} {fullWidth ? 'w-full' : ''} {cls}"
>
  {#if loading}
    <span class="inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></span>
  {:else if icon}
    {@render icon()}
  {/if}
  {@render children?.()}
</button>
