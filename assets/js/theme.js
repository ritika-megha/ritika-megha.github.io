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
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      button.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`);
      button.title = `${theme === 'dark' ? 'Dark' : 'Light'} theme. Click to switch.`;
    });
  }

  apply();
  document.addEventListener('DOMContentLoaded', apply);
  document.addEventListener('click', event => {
    if (!event.target.closest('[data-theme-toggle]')) return;
    preference = root.dataset.theme === 'dark' ? 'light' : 'dark';
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
