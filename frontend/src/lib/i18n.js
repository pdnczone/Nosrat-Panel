import { addMessages, init, getLocaleFromNavigator, locale, _ } from 'svelte-i18n';
import fa from '../../public/locales/fa.json';
import en from '../../public/locales/en.json';

const STORAGE_KEY = 'nosrat_locale';

export function initI18n() {
  addMessages('fa', fa);
  addMessages('en', en);

  init({
    fallbackLocale: 'fa',
    initialLocale: detectLocale()
  });
}

function detectLocale() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && ['fa', 'en'].includes(saved)) return saved;
  } catch (_) {}
  const nav = getLocaleFromNavigator();
  return nav?.startsWith('en') ? 'en' : 'fa';
}

export function setLocale(loc) {
  locale.set(loc);
  try { localStorage.setItem(STORAGE_KEY, loc); } catch (_) {}
  document.documentElement.lang = loc;
  document.documentElement.dir = loc === 'fa' ? 'rtl' : 'ltr';
}

export function toggleLocale() {
  const current = getLocale();
  setLocale(current === 'fa' ? 'en' : 'fa');
}

export function getLocale() {
  let current = 'fa';
  const unsub = locale.subscribe((v) => { if (v) current = v; });
  unsub();
  return current;
}

export { locale, _ };
