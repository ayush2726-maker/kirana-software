(function () {
  'use strict';

  var stack = ['home'];
  var currentPage = 'home';
  var expectedBackPage = '';
  var observer = null;

  function one(selector, root) { return (root || document).querySelector(selector); }
  function isVisible(node) {
    return Boolean(node && !node.classList.contains('hidden') && node.getAttribute('aria-hidden') !== 'true');
  }

  function activePage() {
    var page = one('.page.active');
    return page ? String(page.getAttribute('data-page-name') || page.id.replace(/^page-/, '') || 'home') : 'home';
  }

  function syncPage() {
    var page = activePage();
    if (page === currentPage) return;

    if (expectedBackPage && page === expectedBackPage) {
      expectedBackPage = '';
    } else if (page === 'home') {
      stack = ['home'];
    } else if (stack[stack.length - 1] !== page) {
      stack.push(page);
      if (stack.length > 30) stack = ['home'].concat(stack.slice(-20));
    }
    currentPage = page;
  }

  function clickPage(page) {
    var button = one('[data-page="' + page + '"]');
    if (!button) return false;
    button.click();
    setTimeout(syncPage, 0);
    return true;
  }

  function closeOpenLayer() {
    if (window.KiranaBulkItems && window.KiranaBulkItems.handleBack && window.KiranaBulkItems.handleBack()) return true;

    var txnForm = one('#txn-form-screen');
    if (isVisible(txnForm)) {
      var txnBack = one('[data-txn-action="back-center"]', txnForm) || one('[data-txn-action="close-form"]', txnForm);
      if (txnBack) txnBack.click();
      return true;
    }

    var txnCenter = one('#txn-center');
    if (isVisible(txnCenter)) {
      var txnClose = one('[data-txn-action="close-center"]', txnCenter);
      if (txnClose) txnClose.click();
      return true;
    }

    var modalBackdrop = one('#modal-backdrop');
    if (isVisible(modalBackdrop)) {
      var modalClose = one('[data-action="close-modal"]', modalBackdrop);
      if (modalClose) modalClose.click();
      return true;
    }

    return false;
  }

  function handleBack() {
    syncPage();
    if (closeOpenLayer()) return 'handled';

    if (currentPage !== 'home') {
      if (stack[stack.length - 1] === currentPage) stack.pop();
      var target = stack.length ? stack[stack.length - 1] : 'home';
      if (target === currentPage || !target) target = 'home';
      expectedBackPage = target;
      if (!clickPage(target)) {
        expectedBackPage = 'home';
        clickPage('home');
      }
      return 'handled';
    }

    stack = ['home'];
    return 'home';
  }

  function boot() {
    currentPage = activePage();
    stack = currentPage === 'home' ? ['home'] : ['home', currentPage];
    var app = one('#app');
    if (app) {
      observer = new MutationObserver(syncPage);
      observer.observe(app, { attributes: true, subtree: true, attributeFilter: ['class'] });
    }
    window.addEventListener('popstate', function (event) {
      if (handleBack() === 'handled') event.preventDefault();
    });
  }

  window.KiranaBack = {
    handle: handleBack,
    current: function () { syncPage(); return currentPage; },
    stack: function () { return stack.slice(); }
  };

  boot();
})();
