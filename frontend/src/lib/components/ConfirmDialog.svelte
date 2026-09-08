<script>
  import Modal from './Modal.svelte';
  import Button from './Button.svelte';
  import { _ } from '../i18n.js';

  let {
    open = $bindable(false),
    title = '',
    message = '',
    confirmText = '',
    cancelText = '',
    variant = 'danger',
    onConfirm = () => {},
    onCancel = () => {}
  } = $props();

  const defaultConfirm = $_('common.confirm');
  const defaultCancel = $_('common.cancel');
  const defaultTitle = $_('common.confirm') || 'Confirm';

  async function handleConfirm() {
    await onConfirm();
    open = false;
  }

  function handleCancel() {
    onCancel();
    open = false;
  }
</script>

<Modal bind:open title={title || defaultTitle} size="sm">
  <p class="text-slate-300">{message}</p>
  {#snippet footer()}
    <Button variant="ghost" onclick={handleCancel}>{cancelText || defaultCancel}</Button>
    <Button variant={variant} onclick={handleConfirm}>{confirmText || defaultConfirm}</Button>
  {/snippet}
</Modal>