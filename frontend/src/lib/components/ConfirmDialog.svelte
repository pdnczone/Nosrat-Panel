<script>
  import Modal from './Modal.svelte';
  import Button from './Button.svelte';

  let {
    open = $bindable(false),
    title = 'تأیید عملیات',
    message = 'آیا مطمئن هستید؟',
    confirmText = 'تأیید',
    cancelText = 'انصراف',
    variant = 'danger',
    onConfirm = () => {},
    onCancel = () => {}
  } = $props();

  async function handleConfirm() {
    await onConfirm();
    open = false;
  }

  function handleCancel() {
    onCancel();
    open = false;
  }
</script>

<Modal bind:open {title} size="sm">
  <p class="text-slate-300">{message}</p>
  {#snippet footer()}
    <Button variant="ghost" onclick={handleCancel}>{cancelText}</Button>
    <Button variant={variant} onclick={handleConfirm}>{confirmText}</Button>
  {/snippet}
</Modal>
