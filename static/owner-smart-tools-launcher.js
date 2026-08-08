(function () {
  'use strict';

  if (window.__kiranaSmartToolsLauncherLoaded) return;
  window.__kiranaSmartToolsLauncherLoaded = true;

  function buttonMarkup(kind) {
    if (kind === 'photo') {
      return '<button type="button" data-smart-photo><span>📷</span><div><b>Photo to Bill</b><small>Bill photo se editable Sale/Purchase draft</small></div><i>›</i></button>';
    }
    return '<button type="button" data-smart-barcode><span>▥</span><div><b>Barcode Generator</b><small>Item barcode generate aur labels print</small></div><i>›</i></button>';
  }

  function addMenuButtons(list) {
    if (!list) return;
    if (!list.querySelector('[data-smart-photo]')) list.insertAdjacentHTML('beforeend', buttonMarkup('photo'));
    if (!list.querySelector('[data-smart-barcode]')) list.insertAdjacentHTML('beforeend', buttonMarkup('barcode'));
  }

  function addTopButton() {
    var topbar = document.querySelector('.topbar');
    if (!topbar || document.getElementById('owner-smart-photo-button')) return;
    var button = document.createElement('button');
    button.id = 'owner-smart-photo-button';
    button.type = 'button';
    button.className = 'round-button';
    button.setAttribute('aria-label', 'Photo to Bill');
    button.setAttribute('title', 'Photo to Bill');
    button.textContent = '📷';
    var settings = topbar.querySelector('[data-page="settings"]');
    if (settings) topbar.insertBefore(button, settings);
    else topbar.appendChild(button);
    button.addEventListener('click', function (event) {
      event.preventDefault();
      event.stopPropagation();
      window.location.assign('/owner/smart-tools#photo');
    });
  }

  function bind() {
    document.querySelectorAll('[data-smart-photo]').forEach(function (button) {
      if (button.dataset.boundSmartTool) return;
      button.dataset.boundSmartTool = '1';
      button.addEventListener('click', function () { window.location.assign('/owner/smart-tools#photo'); });
    });
    document.querySelectorAll('[data-smart-barcode]').forEach(function (button) {
      if (button.dataset.boundSmartTool) return;
      button.dataset.boundSmartTool = '1';
      button.addEventListener('click', function () { window.location.assign('/owner/smart-tools#barcode'); });
    });
  }

  function install() {
    addTopButton();
    addMenuButtons(document.querySelector('#page-menu .menu-list'));
    addMenuButtons(document.querySelector('#page-settings .menu-list'));
    bind();
  }

  function boot() {
    install();
    [250, 700, 1500, 3000].forEach(function (delay) { window.setTimeout(install, delay); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
