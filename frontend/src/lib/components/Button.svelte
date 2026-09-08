<script>
  let { variant = 'primary', type = 'button', disabled = false, loading = false, fullWidth = false, onclick = () => {}, children, icon = null, class: cls = '', size = 'md' } = $props();
  const variantClass = {
    primary: 'btn-primary',
    secondary: 'btn-secondary',
    danger: 'btn-danger',
    ghost: 'btn-ghost'
  }[variant] || 'btn-primary';
  const sizeClass = {
    sm: 'px-2.5 py-1.5 text-sm',
    md: 'px-4 py-2',
    lg: 'px-5 py-2.5 text-base'
  }[size] || 'px-4 py-2';
</script>

<button
  {type}
  {disabled}
  onclick={onclick}
  class="{variantClass} {sizeClass} {fullWidth ? 'w-full' : ''} {cls}"
>
  {#if loading}
    <span class="inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></span>
  {:else if icon}
    {@render icon()}
  {/if}
  {@render children?.()}
</button>