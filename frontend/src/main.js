import './app.css';
import { mount } from 'svelte';
import App from './App.svelte';
import { initI18n } from './lib/i18n.js';
import { initTheme } from './lib/theme.js';

initI18n();
initTheme();

const app = mount(App, {
  target: document.getElementById('app')
});

export default app;
