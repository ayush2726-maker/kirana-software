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
    if (kind === 'desk') {
      return '<button type="button" data-smart-desk><span>🤖</span><div><b>AI Billing Desk</b><small>Customer button dabaye aur voice se bill banaye</small></div><i>›</i></button>';
    }
    return '<button type="button" data-smart-barcode><span>▥</span><div><b>Barcode Generator</b><small>Item barcode generate aur labels print</small></div><i>›</i></button>';
  }

  function addMenuButtons(list) {
    if (!list) return;
    function ensureOne(kind, selector) {
      var matches = list.querySelectorAll(selector);
      for (var index = 1; index < matches.length; index += 1) matches[index].remove();
      if (!matches.length) list.insertAdjacentHTML('beforeend', buttonMarkup(kind));
    }
    // Older hard-fix launchers use data-kirana-*-direct attributes. Treat
    // those as the same logical menu action so multiple launchers cannot add
    // duplicate rows while the owner page is re-rendering.
    ensureOne('photo', '[data-smart-photo],[data-kirana-photo-direct]');
    ensureOne('quick', '[data-smart-quick],[data-kirana-quick-direct]');
    ensureOne('desk', '[data-smart-desk],[data-kirana-ai-desk]');
    ensureOne('barcode', '[data-smart-barcode],[data-kirana-barcode-direct]');
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

  function launchDesk(target, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
      if (typeof event.stopImmediatePropagation === 'function') event.stopImmediatePropagation();
    }
    if (!target || target.dataset.launching === '1') return;
    target.dataset.launching = '1';
    var oldHtml = target.innerHTML;
    target.disabled = true;
    target.innerHTML = '<span>🤖</span><div><b>Opening AI Desk…</b><small>Secure kiosk session bana rahe hain</small></div><i>›</i>';
    fetch('/api/ai-counter/kiosk-token', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    }).then(function (response) {
      return response.json().then(function (data) {
        if (!response.ok) throw new Error(data.detail || 'AI Desk open nahi hua');
        return data;
      });
    }).then(function (data) {
      if (!data || !data.url) throw new Error('AI Desk URL missing');
      window.location.assign(data.url);
    }).catch(function (error) {
      target.dataset.launching = '0';
      target.disabled = false;
      target.innerHTML = oldHtml;
      window.alert(error.message || 'AI Desk open nahi hua. Dobara try karein.');
    });
  }

  function smartTarget(event) {
    return event.target && event.target.closest ? event.target.closest('[data-smart-photo],[data-kirana-photo-direct],[data-smart-quick],[data-kirana-quick-direct],[data-smart-desk],[data-kirana-ai-desk],[data-smart-barcode],[data-kirana-barcode-direct],#owner-smart-photo-button') : null;
  }

  document.addEventListener('click', function (event) {
    var target = smartTarget(event);
    if (!target) return;
    if (target.matches('[data-smart-desk],[data-kirana-ai-desk]')) return launchDesk(target, event);
    if (target.matches('[data-smart-quick],[data-kirana-quick-direct],#owner-smart-photo-button')) return go('/owner/quick-bill?v=205', event);
    if (target.matches('[data-smart-photo],[data-kirana-photo-direct]')) return go('/owner/smart-tools?build=205#photo', event);
    if (target.matches('[data-smart-barcode],[data-kirana-barcode-direct]')) return go('/owner/smart-tools?build=205#barcode', event);
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
