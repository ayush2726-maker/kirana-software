(function () {
  'use strict';

  if (window.__kiranaOwnerPrintFixLoaded) return;
  window.__kiranaOwnerPrintFixLoaded = true;

  var VERSION = '127';
  var originalOpen = typeof window.open === 'function' ? window.open.bind(window) : null;
  var scheduled = 0;

  function one(selector, root) {
    return (root || document).querySelector(selector);
  }

  function visibleTransactionCards() {
    return Array.prototype.slice.call(document.querySelectorAll('.transaction-card')).filter(function (card) {
      return card.offsetParent !== null && Number(card.getAttribute('data-transaction-id') || 0) > 0;
    });
  }

  function selectedCount() {
    return Array.prototype.slice.call(document.querySelectorAll('[data-txn-bulk-select]')).filter(function (input) {
      return input.checked;
    }).length;
  }

  function injectStyle() {
    if (one('#owner-print-fix-style')) return;
    var style = document.createElement('style');
    style.id = 'owner-print-fix-style';
    style.textContent =
      '.txn-bulk-bar.txn-bulk-always{display:flex!important;bottom:150px!important;left:12px!important;right:12px!important;transform:none!important;width:auto!important}' +
      '.txn-bulk-bar.txn-bulk-always .primary{min-width:128px}' +
      '.txn-bulk-bar.txn-bulk-always strong{white-space:nowrap}' +
      '@media(min-width:760px){.txn-bulk-bar.txn-bulk-always{left:50%!important;right:auto!important;bottom:20px!important;transform:translateX(-50%)!important;width:min(720px,calc(100vw - 40px))!important}}';
    document.head.appendChild(style);
  }

  function revealBulkPrint() {
    injectStyle();
    var bar = one('#txn-bulk-bar');
    var cards = visibleTransactionCards();
    if (!bar || !cards.length) return;

    bar.classList.remove('hidden');
    bar.classList.add('txn-bulk-always');

    var count = selectedCount();
    var countNode = one('#txn-selected-count', bar);
    if (countNode) countNode.textContent = String(count);

    var printButton = one('[data-txn-bulk-print]', bar);
    if (printButton) {
      printButton.textContent = '🖨 Bulk Print (' + count + ')';
      printButton.setAttribute('aria-label', count ? 'Print ' + count + ' selected transactions' : 'Select transactions, then bulk print');
    }
  }

  function scheduleReveal() {
    window.clearTimeout(scheduled);
    scheduled = window.setTimeout(revealBulkPrint, 40);
  }

  // Keep print inside the authenticated owner WebView/tab. Opening a separate
  // browser context can lose the owner cookie and show {"detail":"Login required"}.
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

  document.addEventListener('change', function (event) {
    if (event.target && event.target.matches('[data-txn-bulk-select]')) scheduleReveal();
  }, true);
  document.addEventListener('click', function () {
    scheduleReveal();
  }, true);

  function boot() {
    injectStyle();
    revealBulkPrint();
    if (typeof MutationObserver !== 'undefined') {
      new MutationObserver(scheduleReveal).observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class', 'checked']
      });
    }
    [250, 700, 1500, 3000].forEach(function (delay) {
      window.setTimeout(revealBulkPrint, delay);
    });
    console.log('Owner print session + persistent bulk toolbar v' + VERSION);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
