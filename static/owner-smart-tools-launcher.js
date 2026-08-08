(function () {
  'use strict';

  if (window.__kiranaSmartToolsLauncherLoaded) return;
  window.__kiranaSmartToolsLauncherLoaded = true;

  function buttonMarkup(kind) {
    if (kind === 'photo') {
      return '<button type="button" data-smart-photo><span>📷</span><div><b>Photo to Bill</b><small>Bill photo se editable Sale/Purchase draft</small></div><i>›</i></button>';
    }
    if (kind === 'quick') {
      return '<button type="button" data-smart-quick><span>✍️</span><div><b>Quick Write Bill</b><small>Hindi/English note likho, item + size + saved rate auto</small></div><i>›</i></button>';
    }
    return '<button type="button" data-smart-barcode><span>▥</span><div><b>Barcode Generator</b><small>Item barcode generate aur labels print</small></div><i>›</i></button>';
  }

  function addMenuButtons(list) {
    if (!list) return;
    if (!list.querySelector('[data-smart-photo]')) list.insertAdjacentHTML('beforeend', buttonMarkup('photo'));
    if (!list.querySelector('[data-smart-quick]')) list.insertAdjacentHTML('beforeend', buttonMarkup('quick'));
    if (!list.querySelector('[data-smart-barcode]')) list.insertAdjacentHTML('beforeend', buttonMarkup('barcode'));
  }

  function addTopButton() {
    var topbar = document.querySelector('.topbar');
    if (!topbar || document.getElementById('owner-smart-photo-button')) return;
    var button = document.createElement('button');
    button.id = 'owner-smart-photo-button';
    button.type = 'button';
    button.className = 'round-button';
    button.setAttribute('aria-label', 'Quick Write Bill');
    button.setAttribute('title', 'Quick Write Bill');
    button.textContent = '✍️';
    var settings = topbar.querySelector('[data-page="settings"]');
    if (settings) topbar.insertBefore(button, settings);
    else topbar.appendChild(button);
  }

  function install() {
    addTopButton();
    addMenuButtons(document.querySelector('#page-menu .menu-list'));
    addMenuButtons(document.querySelector('#page-settings .menu-list'));
  }

  function go(url, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
      if (typeof event.stopImmediatePropagation === 'function') event.stopImmediatePropagation();
    }
    window.location.assign(url);
  }

  function smartTarget(event) {
    return event.target && event.target.closest ? event.target.closest('[data-smart-photo],[data-smart-quick],[data-smart-barcode],#owner-smart-photo-button') : null;
  }

  document.addEventListener('click', function (event) {
    var target = smartTarget(event);
    if (!target) return;
    if (target.matches('[data-smart-quick],#owner-smart-photo-button')) return go('/owner/quick-bill?v=149', event);
    if (target.matches('[data-smart-photo]')) return go('/owner/smart-tools?build=149#photo', event);
    if (target.matches('[data-smart-barcode]')) return go('/owner/smart-tools?build=149#barcode', event);
  }, true);

  function boot() {
    install();
    [50, 150, 300, 600, 1000, 1800, 3000].forEach(function (delay) { window.setTimeout(install, delay); });
    if (window.MutationObserver && document.documentElement) {
      var queued = false;
      var observer = new MutationObserver(function () {
        if (queued) return;
        queued = true;
        window.requestAnimationFrame(function () {
          queued = false;
          install();
        });
      });
      observer.observe(document.documentElement, { childList: true, subtree: true });
      window.__kiranaSmartToolsObserver = observer;
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
