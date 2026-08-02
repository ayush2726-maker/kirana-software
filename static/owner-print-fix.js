(function () {
  'use strict';

  if (window.__kiranaOwnerPrintFixLoaded) return;
  window.__kiranaOwnerPrintFixLoaded = true;

  var VERSION = '128';
  var originalOpen = typeof window.open === 'function' ? window.open.bind(window) : null;

  function one(selector, root) {
    return (root || document).querySelector(selector);
  }

  function injectStyle() {
    if (one('#owner-print-fix-style')) return;
    var style = document.createElement('style');
    style.id = 'owner-print-fix-style';
    style.textContent =
      '#txn-bulk-bar,.txn-bulk-bar,.txn-select-label{display:none!important}' +
      '.transaction-card.txn-card-selected{outline:none!important}' +
      '.txn-card-actions{justify-content:flex-end!important}' +
      '.txn-card-actions .txn-print-btn{margin-left:auto}';
    document.head.appendChild(style);
  }

  // Keep old per-bill print routes inside the authenticated owner WebView/tab.
  // The main bulk workflow now lives behind the printer icon/print center.
  if (originalOpen) {
    window.open = function (url, target, features) {
      var text = String(url || '');
      if (text.indexOf('/owner/bulk-print?') === 0 || text.indexOf(location.origin + '/owner/bulk-print?') === 0) {
        window.location.assign(text);
        return { closed: false, focus: function () {} };
      }
      return originalOpen(url, target, features);
    };
  }

  function boot() {
    injectStyle();
    console.log('Owner print session + clean transaction actions v' + VERSION);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
