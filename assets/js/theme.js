(() => {
  'use strict';
  const root = document.documentElement;
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  const valid = value => ['auto', 'light', 'dark'].includes(value) ? value : 'auto';
  let preference = 'auto';
  try { preference = valid(localStorage.getItem('portfolio-theme')); } catch (_) { /* Use device preference. */ }

  function apply() {
    const theme = preference === 'auto' ? (system.matches ? 'dark' : 'light') : preference;
    root.dataset.theme = theme;
    root.dataset.themePreference = preference;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = theme === 'dark' ? '#1b1d19' : '#f4f3ee';
    document.querySelectorAll('[data-theme-picker]').forEach(picker => { picker.value = preference; });
  }

  apply();
  document.addEventListener('DOMContentLoaded', apply);
  document.addEventListener('change', event => {
    if (!event.target.matches('[data-theme-picker]')) return;
    preference = valid(event.target.value);
    try { localStorage.setItem('portfolio-theme', preference); } catch (_) { /* Choice still applies for this page. */ }
    apply();
  });
  system.addEventListener('change', () => { if (preference === 'auto') apply(); });
  window.addEventListener('storage', event => {
    if (event.key === 'portfolio-theme' || event.key === null) {
      preference = valid(event.newValue);
      apply();
    }
  });
})();
