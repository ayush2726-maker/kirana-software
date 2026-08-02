(function () {
  'use strict';

  if (window.__kiranaItemHistoryLoaded) return;
  window.__kiranaItemHistoryLoaded = true;

  var activeItemId = 0;
  var openingItemId = 0;
  var previousOverflow = '';

  function one(selector, root) {
    return (root || document).querySelector(selector);
  }

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (character) {
      return ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      })[character];
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

  function quantity(value) {
    var parsed = num(value);
    return parsed.toLocaleString('en-IN', {
      minimumFractionDigits: Number.isInteger(parsed) ? 1 : 0,
      maximumFractionDigits: 3
    });
  }

  function dateLabel(value) {
    var text = String(value || '').slice(0, 10);
    if (!text) return '—';
    var parts = text.split('-');
    if (parts.length !== 3) return text;
    return parts[2] + '/' + parts[1] + '/' + parts[0];
  }

  function kindLabel(kind) {
    return ({
      sale: 'Sale',
      purchase: 'Purchase',
      sale_return: 'Sale Return',
      purchase_return: 'Purchase Return',
      opening_stock: 'Opening Stock',
      add_stock: 'Add Stock',
      reduce_stock: 'Reduce Stock'
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
    if (!response.ok) {
      throw new Error(data && data.detail ? data.detail : 'Item details could not load');
    }
    return data;
  }

  function injectStyle() {
    if (one('#owner-item-history-style')) return;
    var style = document.createElement('style');
    style.id = 'owner-item-history-style';
    style.textContent =
      '.item-history-overlay{position:fixed;inset:0;z-index:4300;background:#fff;overflow:auto;overscroll-behavior:contain;color:#1e2935}' +
      '.item-history-overlay.hidden{display:none!important}' +
      '.item-history-head{position:sticky;top:0;z-index:3;min-height:68px;padding:calc(10px + env(safe-area-inset-top)) 17px 10px;background:#fff;border-bottom:1px solid #e2e8ee;display:grid;grid-template-columns:48px 1fr 48px;align-items:center;gap:8px}' +
      '.item-history-head h1{margin:0;text-align:left;font-size:24px}.item-history-icon{border:0;background:transparent;width:46px;height:46px;border-radius:50%;font-size:31px;color:#25313b}.item-history-icon:active{background:#edf4f8}.item-history-edit{font-size:26px;color:#087fbd}' +
      '.item-history-body{background:#f3f7fa;min-height:calc(100vh - 68px);padding-bottom:calc(28px + env(safe-area-inset-bottom))}' +
      '.item-history-summary{background:#fff;padding:24px 20px 21px;border-bottom:1px solid #dfe7ec}.item-history-name{margin:0;font-size:23px;font-weight:500;color:#66717f}.item-history-size{display:inline-block;margin-top:8px;padding:5px 10px;border-radius:999px;background:#eef6fb;color:#087fbd;font-size:12px;font-weight:850}' +
      '.item-history-prices{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:26px}.item-history-metric small{display:block;color:#67717c;font-size:14px}.item-history-metric strong{display:block;margin-top:6px;font-size:21px;white-space:nowrap}.item-history-metric.stock strong{color:#12a56f}.item-history-stock-value{margin-top:24px}.item-history-stock-value small{display:block;color:#67717c}.item-history-stock-value strong{display:block;margin-top:6px;font-size:21px}' +
      '.item-history-section{background:#fff;margin-top:10px}.item-history-section-title{padding:18px 20px 14px;font-size:21px;font-weight:850}.item-history-columns{display:grid;grid-template-columns:minmax(0,1fr) 92px 112px;gap:8px;padding:13px 20px;color:#6f7882;border-bottom:1px solid #dfe5e9;font-size:13px}.item-history-columns span:nth-child(2),.item-history-columns span:nth-child(3){text-align:right}' +
      '.item-history-row{display:grid;grid-template-columns:minmax(0,1fr) 92px 112px;gap:8px;align-items:center;padding:17px 20px;border-bottom:1px solid #e4e9ed;background:#fff}.item-history-row:last-child{border-bottom:0}.item-history-main{min-width:0}.item-history-main b{display:block;font-size:18px}.item-history-main small{display:block;margin-top:4px;color:#727d88;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.item-history-qty,.item-history-amount{text-align:right;font-size:17px}.item-history-qty.positive{color:#119d6c}.item-history-qty.negative{color:#313a42}.item-history-empty,.item-history-loading{padding:46px 20px;text-align:center;color:#737f89;font-weight:750}.item-history-error{color:#d23c5a}.item-history-retry{display:block;margin:16px auto 0;border:0;border-radius:12px;background:#0b82c2;color:#fff;padding:11px 20px;font-size:16px;font-weight:850}' +
      '@media(max-width:430px){.item-history-prices{gap:8px}.item-history-metric small{font-size:12px}.item-history-metric strong{font-size:18px}.item-history-columns,.item-history-row{grid-template-columns:minmax(0,1fr) 76px 94px;padding-left:14px;padding-right:14px;gap:5px}.item-history-main b{font-size:16px}.item-history-qty,.item-history-amount{font-size:15px}}' +
      '@media(min-width:760px){.item-history-overlay{left:50%;right:auto;width:min(720px,100%);transform:translateX(-50%);box-shadow:0 0 45px rgba(20,50,70,.22)}}';
    document.head.appendChild(style);
  }

  function ensureOverlay() {
    var overlay = one('#item-history-overlay');
    if (overlay) return overlay;
    overlay = document.createElement('section');
    overlay.id = 'item-history-overlay';
    overlay.className = 'item-history-overlay hidden';
    overlay.setAttribute('aria-hidden', 'true');
    overlay.innerHTML =
      '<header class="item-history-head">' +
        '<button type="button" class="item-history-icon" data-close-item-history aria-label="Back">←</button>' +
        '<h1>Item Details</h1>' +
        '<button type="button" class="item-history-icon item-history-edit" data-item-history-edit data-action="edit-item" data-id="0" aria-label="Edit item">✎</button>' +
      '</header>' +
      '<main id="item-history-body" class="item-history-body"></main>';
    document.body.appendChild(overlay);
    return overlay;
  }

  function showOverlay() {
    var overlay = ensureOverlay();
    if (overlay.classList.contains('hidden')) previousOverflow = document.body.style.overflow || '';
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    overlay.scrollTop = 0;
    document.body.style.overflow = 'hidden';
  }

  function closeOverlay() {
    var overlay = one('#item-history-overlay');
    if (!overlay) return;
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = previousOverflow;
  }

  function showLoading(itemId) {
    activeItemId = Number(itemId || 0);
    var overlay = ensureOverlay();
    one('[data-item-history-edit]', overlay).setAttribute('data-id', String(activeItemId));
    one('#item-history-body', overlay).innerHTML = '<div class="item-history-loading">Loading item and bill history...</div>';
    showOverlay();
  }

  function transactionMarkup(row, unit) {
    var kind = String(row.kind || 'transaction');
    var meta = [dateLabel(row.transaction_date), row.party_name, row.number].filter(Boolean).join(' · ');
    var stockClass = num(row.stock_delta) >= 0 ? 'positive' : 'negative';
    return '<article class="item-history-row">' +
      '<div class="item-history-main"><b>' + esc(kindLabel(kind)) + '</b><small>' + esc(meta || 'Main Godown') + '</small></div>' +
      '<div class="item-history-qty ' + stockClass + '">' + esc(quantity(row.qty)) + (unit ? ' ' + esc(unit) : '') + '</div>' +
      '<div class="item-history-amount">' + money(row.amount) + '</div>' +
    '</article>';
  }

  function render(data) {
    var overlay = ensureOverlay();
    var item = data && data.item ? data.item : {};
    var rows = data && Array.isArray(data.transactions) ? data.transactions : [];
    var sizeText = [item.size, item.unit].filter(Boolean).join(' · ');
    one('[data-item-history-edit]', overlay).setAttribute('data-id', String(Number(item.id || activeItemId)));
    one('#item-history-body', overlay).innerHTML =
      '<section class="item-history-summary">' +
        '<h2 class="item-history-name">' + esc(item.name || 'Item') + '</h2>' +
        (sizeText ? '<span class="item-history-size">' + esc(sizeText) + '</span>' : '') +
        '<div class="item-history-prices">' +
          '<div class="item-history-metric"><small>Sale Price</small><strong>' + money(item.sale_price) + '</strong></div>' +
          '<div class="item-history-metric"><small>Purchase Price</small><strong>' + money(item.purchase_price) + '</strong></div>' +
          '<div class="item-history-metric stock"><small>In Stock</small><strong>' + esc(quantity(item.stock)) + '</strong></div>' +
        '</div>' +
        '<div class="item-history-stock-value"><small>Stock Value</small><strong>' + money(item.stock_value) + '</strong></div>' +
      '</section>' +
      '<section class="item-history-section">' +
        '<div class="item-history-section-title">Stock Transactions</div>' +
        '<div class="item-history-columns"><span>Transactions</span><span>Quantity</span><span>Total Amount</span></div>' +
        (rows.length ? rows.map(function (row) { return transactionMarkup(row, item.unit || ''); }).join('') : '<div class="item-history-empty">This item has not appeared in any sale, purchase or stock entry yet.</div>') +
      '</section>';
  }

  function renderError(error) {
    var body = one('#item-history-body');
    if (!body) return;
    body.innerHTML =
      '<div class="item-history-loading item-history-error">Item details load nahi hui.' +
      '<button type="button" class="item-history-retry" data-retry-item-history>Retry</button></div>';
    console.error('Item history failed', error);
  }

  async function openItem(itemId) {
    itemId = Number(itemId || 0);
    if (!itemId || openingItemId === itemId) return;
    openingItemId = itemId;
    showLoading(itemId);
    try {
      var data = await api('/api/item-history/' + itemId);
      if (activeItemId === itemId) render(data);
    } catch (error) {
      if (activeItemId === itemId) renderError(error);
      toast('Item details load nahi hui. Retry dabayein.', true);
    } finally {
      if (openingItemId === itemId) openingItemId = 0;
    }
  }

  document.addEventListener('click', function (event) {
    var retry = event.target.closest('[data-retry-item-history]');
    if (retry) {
      event.preventDefault();
      openItem(activeItemId);
      return;
    }

    var editInside = event.target.closest('#item-history-overlay [data-item-history-edit]');
    if (editInside) {
      closeOverlay();
      return;
    }

    var close = event.target.closest('[data-close-item-history]');
    if (close) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      closeOverlay();
      return;
    }

    var trigger = event.target.closest('#items-list [data-action="edit-item"]');
    if (!trigger) {
      var card = event.target.closest('#items-list .item-card');
      if (card) trigger = one('[data-action="edit-item"]', card);
    }
    if (!trigger) return;
    var itemId = Number(trigger.getAttribute('data-id') || 0);
    if (!itemId) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    openItem(itemId);
  }, true);

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      var overlay = one('#item-history-overlay');
      if (overlay && !overlay.classList.contains('hidden')) closeOverlay();
    }
  });

  window.KiranaItemHistory = {
    open: openItem,
    close: closeOverlay
  };

  injectStyle();
  ensureOverlay();
})();
