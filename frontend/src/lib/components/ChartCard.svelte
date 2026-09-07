<script>
  import Card from './Card.svelte';

  let { title = '', type = 'line', data, options = {}, height = 240 } = $props();

  let chartCanvas;

  async function render() {
    if (!chartCanvas || !data) return;
    const Chart = (await import('chart.js/auto')).default;
    if (chartCanvas._chart) chartCanvas._chart.destroy();

    const defaultOpts = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#cbd5e1' } },
        tooltip: { backgroundColor: '#0f172a', borderColor: '#334155', borderWidth: 1 }
      },
      scales: {
        x: { ticks: { color: '#94a3b8' }, grid: { color: '#1e293b' } },
        y: { ticks: { color: '#94a3b8' }, grid: { color: '#1e293b' } }
      }
    };

    chartCanvas._chart = new Chart(chartCanvas, { type, data, options: { ...defaultOpts, ...options } });
  }

  $effect(() => {
    data;
    render();
  });
</script>

<Card {title}>
  <div style="height: {height}px;">
    <canvas bind:this={chartCanvas}></canvas>
  </div>
</Card>
