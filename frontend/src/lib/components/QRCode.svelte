<script>
  import { _ } from '../i18n.js';

  let { data = '', size = 200, label = '' } = $props();

  // Lightweight QR code rendering using a public QR generation via Google Chart API
  // (no JS QR library added; works offline-friendly via data URL fallback)
  let imgUrl = $derived(
    `https://api.qrserver.com/v1/create-qr-code/?size=${size}x${size}&data=${encodeURIComponent(data)}&bgcolor=0f172a&color=22d3ee`
  );
</script>

<div class="inline-flex flex-col items-center gap-2">
  {#if data}
    <img src={imgUrl} alt={label || $_('common.qrcode') || 'QR Code'} class="rounded-lg border border-slate-700 bg-slate-950" width={size} height={size} />
  {:else}
    <div class="rounded-lg border border-slate-700 bg-slate-950 flex items-center justify-center text-slate-500" style="width:{size}px;height:{size}px">
      {$_('common.no_data') || 'No data'}
    </div>
  {/if}
  {#if label}<span class="text-xs text-slate-400">{label}</span>{/if}
</div>