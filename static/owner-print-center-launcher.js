(function () {
  'use strict';

  if (window.__kiranaPrintCenterLauncherLoaded) return;
  window.__kiranaPrintCenterLauncherLoaded = true;

  function addLauncher() {
    var topbar = document.querySelector('.topbar');
    if (!topbar || document.getElementById('owner-print-center-button')) return;

    var button = document.createElement('button');
    button.id = 'owner-print-center-button';
    button.type = 'button';
    button.className = 'round-button';
    button.setAttribute('aria-label', 'Open Print Center');
    button.setAttribute('title', 'Print Center');
    button.textContent = '🖨';

    var settings = topbar.querySelector('[data-page="settings"]');
    if (settings) topbar.insertBefore(button, settings);
    else topbar.appendChild(button);

    button.addEventListener('click', function (event) {
      event.preventDefault();
      event.stopPropagation();
      window.location.assign('/owner/print-center');
    });
  }

  function boot() {
    addLauncher();
    [300, 800, 1800].forEach(function (delay) {
      window.setTimeout(addLauncher, delay);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
