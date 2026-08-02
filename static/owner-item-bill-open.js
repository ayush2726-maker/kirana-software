(function () {
  'use strict';

  if (window.__kiranaItemBillOpenLoaded) return;
  window.__kiranaItemBillOpenLoaded = true;

  var cache = new Map();
  var activeBill = null;
  var decorating = false;

  function one(selector, root) {
    return (root || document).querySelector(selector);
  }

  function all(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (character) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character];
    });
  }

  function num(value) {
    var parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function money(value) {
    return '₹ ' + num(value).toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function dateLabel(value) {
    var text = String(value || '').slice(0, 10);
    var parts = text.split('-');
    return parts.length === 3 ? parts[2] + '/' + parts[1] + '/' + parts[0] : text;
  }

  function kindLabel(kind) {
    return ({
      sale: 'Sale Invoice',
      purchase: 'Purchase Bill',
      sale_return: 'Sale Return',
      purchase_return: 'Purchase Return'
    })[String(kind || '')] || String(kind || 'Transaction').replace(/_/g, ' ');
  }

  function toast(message, isError) {
    var node = one('#toast') || one('#txn-toast');
    if (!node) {
      console[isError ? 'error' : 'log'](message);
      return;
    }
    node.textContent = String(message || 'Done');
    node.className = (node.id === 'txn-toast' ? 'txn-toast' : 'toast') + ' show' + (isError ? ' error' : '');
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(function () {
      node.className = node.id === 'txn-toast' ? 'txn-toast' : 'toast';
    }, 3500);
  }

  async function api(path) {
    var response = await fetch(path, {
      headers: { Accept: 'application/json' },
      credentials: 'include',
      cache: 'no-store'
    });
    var data = await response.json().catch(function () { return null; });
    if (response.status === 401) {
      window.location.replace('/owner-login');
      throw new Error('Owner session expired');
    }
    if (!response.ok) throw new Error(data && data.detail ? data.detail : 'Request failed');
    return data;
  }

  function injectStyle() {
    if (one('#item-bill-open-style')) return;
    var style = document.createElement('style');
    style.id = 'item-bill-open-style';
    style.textContent =
      '.item-history-row.item-history-openable{cursor:pointer;touch-action:manipulation;position:relative;padding-right:34px}' +
      '.item-history-row.item-history-openable:active{background:#eef7fc}' +
      '.item-history-row.item-history-openable:after{content:"›";position:absolute;right:12px;top:50%;transform:translateY(-50%);font-size:29px;color:#82919c}' +
      '.item-bill-overlay{position:fixed;inset:0;z-index:4800;background:#f3f7fa;overflow:auto;color:#1f2d39}' +
      '.item-bill-overlay.hidden{display:none!important}' +
      '.item-bill-head{position:sticky;top:0;z-index:2;background:#fff;border-bottom:1px solid #dce5ea;padding:calc(10px + env(safe-area-inset-top)) 14px 10px;display:grid;grid-template-columns:48px minmax(0,1fr) 48px;align-items:center;gap:8px}' +
      '.item-bill-head h1{margin:0;font-size:23px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' +
      '.item-bill-head button{width:46px;height:46px;border:0;border-radius:50%;background:transparent;font-size:30px;color:#087fbd}.item-bill-head button:active{background:#edf5f9}' +
      '.item-bill-body{padding:16px 14px calc(28px + env(safe-area-inset-bottom));display:grid;gap:13px}' +
      '.item-bill-card{background:#fff;border:1px solid #dce5ea;border-radius:17px;padding:16px;box-shadow:0 7px 20px rgba(30,75,100,.09)}' +
      '.item-bill-title{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}.item-bill-title h2{margin:0;font-size:21px}.item-bill-title small{display:block;margin-top:5px;color:#74818c}.item-bill-title strong{font-size:20px;white-space:nowrap}' +
      '.item-bill-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:14px}.item-bill-grid div{background:#f3f7fa;border-radius:11px;padding:10px}.item-bill-grid small{display:block;color:#75818b}.item-bill-grid b{display:block;margin-top:3px}' +
      '.item-bill-line{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;padding:12px 0;border-bottom:1px solid #edf1f4}.item-bill-line:last-child{border-bottom:0}.item-bill-line small{display:block;color:#74818c;margin-top:4px}.item-bill-line strong{white-space:nowrap}' +
      '.item-bill-loading,.item-bill-error{text-align:center;padding:52px 18px;color:#74818c;font-weight:800}.item-bill-error{color:#cc3f5d}.item-bill-retry{display:block;margin:16px auto 0;border:0;border-radius:12px;background:#0b82c2;color:#fff;padding:11px 20px;font-weight:850}' +
      '@media(min-width:760px){.item-bill-overlay{left:50%;right:auto;width:min(720px,100%);transform:translateX(-50%);box-shadow:0 0 45px rgba(20,50,70,.22)}}';
    document.head.appendChild(style);
  }

  function ensureOverlay() {
    var overlay = one('#item-bill-overlay');
    if (overlay) return overlay;
    overlay = document.createElement('section');
    overlay.id = 'item-bill-overlay';
    overlay.className = 'item-bill-overlay hidden';
    overlay.setAttribute('aria-hidden', 'true');
    overlay.innerHTML =
      '<header class="item-bill-head">' +
        '<button type="button" data-close-item-bill aria-label="Back">←</button>' +
        '<h1 id="item-bill-heading">Bill Details</h1>' +
        '<button type="button" data-print-item-bill aria-label="Print bill">🖨</button>' +
      '</header>' +
      '<main id="item-bill-body" class="item-bill-body"></main>';
    document.body.appendChild(overlay);
    return overlay;
  }

  function showOverlay() {
    var overlay = ensureOverlay();
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    overlay.scrollTop = 0;
    document.body.style.overflow = 'hidden';
  }

  function closeOverlay() {
    var overlay = one('#item-bill-overlay');
    if (!overlay) return;
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
    activeBill = null;
    document.body.style.overflow = 'hidden';
  }

  function itemLine(item) {
    return '<div class="item-bill-line"><div><b>' + esc(item.item_name || 'Item') + '</b><small>' +
      esc(item.size || '') + (item.size ? ' · ' : '') + 'Qty ' + esc(item.qty) + ' × ' + money(item.rate) +
      (num(item.gst_rate) ? ' · GST ' + esc(item.gst_rate) + '%' : '') +
      '</small></div><strong>' + money(item.line_total) + '</strong></div>';
  }

  function renderBill(detail) {
    var overlay = ensureOverlay();
    var title = kindLabel(detail.kind);
    var items = Array.isArray(detail.items) ? detail.items : [];
    one('#item-bill-heading', overlay).textContent = title;
    one('#item-bill-body', overlay).innerHTML =
      '<section class="item-bill-card"><div class="item-bill-title"><div><h2>' + esc(detail.party_name || detail.title || 'Cash Customer') + '</h2><small>' +
        esc(detail.number || detail.reference || '') + (detail.date ? ' · ' + dateLabel(detail.date) : '') +
        '</small></div><strong>' + money(detail.total) + '</strong></div>' +
        '<div class="item-bill-grid">' +
          '<div><small>Subtotal</small><b>' + money(detail.subtotal) + '</b></div>' +
          '<div><small>Tax</small><b>' + money(detail.tax) + '</b></div>' +
          '<div><small>Discount</small><b>' + money(detail.discount) + '</b></div>' +
          '<div><small>Paid</small><b>' + money(detail.paid) + '</b></div>' +
          '<div><small>Due</small><b>' + money(detail.due) + '</b></div>' +
          '<div><small>Payment Mode</small><b>' + esc(detail.payment_mode || '—') + '</b></div>' +
        '</div></section>' +
      (items.length ? '<section class="item-bill-card"><h3>Items</h3>' + items.map(itemLine).join('') + '</section>' : '') +
      (detail.notes ? '<section class="item-bill-card"><h3>Notes</h3><div>' + esc(detail.notes) + '</div></section>' : '');
  }

  async function openBill(kind, transactionId) {
    kind = String(kind || '');
    transactionId = Number(transactionId || 0);
    if (!kind || !transactionId) return;
    activeBill = { kind: kind, id: transactionId };
    var overlay = ensureOverlay();
    one('#item-bill-heading', overlay).textContent = kindLabel(kind);
    one('#item-bill-body', overlay).innerHTML = '<div class="item-bill-loading">Loading bill details...</div>';
    showOverlay();
    try {
      var detail = await api('/api/transaction-detail/' + encodeURIComponent(kind) + '/' + transactionId);
      if (activeBill && activeBill.kind === kind && activeBill.id === transactionId) renderBill(detail);
    } catch (error) {
      if (!activeBill) return;
      one('#item-bill-body', overlay).innerHTML = '<div class="item-bill-error">Bill could not be opened.<button type="button" class="item-bill-retry" data-retry-item-bill>Retry</button></div>';
      toast(error.message || 'Bill could not be opened', true);
    }
  }

  async function historyFor(itemId) {
    itemId = Number(itemId || 0);
    if (!itemId) return null;
    if (cache.has(itemId)) return cache.get(itemId);
    var promise = api('/api/item-history/' + itemId).catch(function (error) {
      cache.delete(itemId);
      throw error;
    });
    cache.set(itemId, promise);
    return promise;
  }

  async function decorateRows() {
    if (decorating) return;
    var overlay = one('#item-history-overlay');
    if (!overlay || overlay.classList.contains('hidden')) return;
    var rows = all('.item-history-row', overlay);
    if (!rows.length) return;
    var edit = one('[data-item-history-edit]', overlay);
    var itemId = Number(edit && edit.getAttribute('data-id') || 0);
    if (!itemId) return;
    decorating = true;
    try {
      var data = await historyFor(itemId);
      var transactions = data && Array.isArray(data.transactions) ? data.transactions : [];
      rows.forEach(function (row, index) {
        var transaction = transactions[index];
        row.setAttribute('data-item-history-index', String(index));
        if (transaction && transaction.transaction_id && ['sale', 'purchase', 'sale_return', 'purchase_return'].indexOf(String(transaction.kind)) >= 0) {
          row.classList.add('item-history-openable');
          row.setAttribute('aria-label', 'Open ' + kindLabel(transaction.kind));
        } else {
          row.classList.remove('item-history-openable');
        }
      });
    } catch (error) {
      console.error('Item bill row decoration failed', error);
    } finally {
      decorating = false;
    }
  }

  async function openRow(row) {
    var overlay = one('#item-history-overlay');
    var edit = overlay && one('[data-item-history-edit]', overlay);
    var itemId = Number(edit && edit.getAttribute('data-id') || 0);
    var index = Number(row.getAttribute('data-item-history-index'));
    if (!Number.isInteger(index) || index < 0) index = all('.item-history-row', overlay).indexOf(row);
    try {
      var data = await historyFor(itemId);
      var transaction = data && data.transactions ? data.transactions[index] : null;
      if (!transaction || !transaction.transaction_id) {
        toast('This is a stock adjustment. No bill is attached.', true);
        return;
      }
      openBill(transaction.kind, transaction.transaction_id);
    } catch (error) {
      toast(error.message || 'Bill could not be opened', true);
    }
  }

  document.addEventListener('click', function (event) {
    var close = event.target.closest('[data-close-item-bill]');
    if (close) {
      event.preventDefault();
      event.stopPropagation();
      closeOverlay();
      return;
    }

    var retry = event.target.closest('[data-retry-item-bill]');
    if (retry && activeBill) {
      event.preventDefault();
      openBill(activeBill.kind, activeBill.id);
      return;
    }

    var print = event.target.closest('[data-print-item-bill]');
    if (print) {
      event.preventDefault();
      if (!activeBill) return;
      location.assign('/owner/bulk-print?items=' + encodeURIComponent(activeBill.kind + ':' + activeBill.id));
      return;
    }

    var row = event.target.closest('#item-history-overlay .item-history-row');
    if (!row) return;
    event.preventDefault();
    event.stopPropagation();
    openRow(row);
  }, true);

  function scheduleDecorate() {
    window.clearTimeout(scheduleDecorate.timer);
    scheduleDecorate.timer = window.setTimeout(decorateRows, 80);
  }

  function boot() {
    injectStyle();
    ensureOverlay();
    if (typeof MutationObserver !== 'undefined') {
      new MutationObserver(scheduleDecorate).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'data-id'] });
    }
    document.addEventListener('click', scheduleDecorate, true);
    [400, 1000, 2200].forEach(function (delay) { window.setTimeout(scheduleDecorate, delay); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
