(function () {
  'use strict';

  if (window.__kiranaTransactionDetailLoaded) return;
  window.__kiranaTransactionDetailLoaded = true;

  var activityCache = [];
  var cacheAt = 0;
  var opening = false;

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
    return '₹' + num(value).toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function normalize(value) {
    return String(value == null ? '' : value).replace(/\s+/g, ' ').trim().toLowerCase();
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
    var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timer = window.setTimeout(function () {
      if (controller) controller.abort();
    }, 10000);
    try {
      var response = await fetch(path, {
        headers: { Accept: 'application/json' },
        credentials: 'include',
        cache: 'no-store',
        signal: controller ? controller.signal : undefined
      });
      var data = await response.json().catch(function () { return null; });
      if (response.status === 401) {
        window.location.replace('/owner-login');
        throw new Error('Owner session expired');
      }
      if (!response.ok) {
        throw new Error(data && data.detail ? data.detail : 'Request failed (' + response.status + ')');
      }
      return data;
    } finally {
      window.clearTimeout(timer);
    }
  }

  function injectStyle() {
    if (one('#transaction-detail-style')) return;
    var style = document.createElement('style');
    style.id = 'transaction-detail-style';
    style.textContent =
      '.transaction-card,#dashboard-activity .compact-row{cursor:pointer;touch-action:manipulation}' +
      '.transaction-card:active,#dashboard-activity .compact-row:active{transform:scale(.992)}' +
      '.transaction-detail-overlay{position:fixed;inset:0;z-index:4500;background:rgba(20,34,44,.52);display:flex;align-items:flex-end;justify-content:center}' +
      '.transaction-detail-sheet{width:min(680px,100%);max-height:94vh;overflow:auto;background:#f4fafe;border-radius:25px 25px 0 0;box-shadow:0 -18px 55px rgba(0,0,0,.22)}' +
      '.transaction-detail-head{position:sticky;top:0;z-index:2;background:#fff;border-bottom:1px solid #d9e4eb;padding:15px 18px;display:flex;align-items:center;justify-content:space-between;gap:12px}' +
      '.transaction-detail-head small{display:block;color:#075d96;font-size:11px;font-weight:900;letter-spacing:1.2px}' +
      '.transaction-detail-head h2{margin:3px 0 0;font-size:23px}' +
      '.transaction-detail-close{border:0;background:#eef4f8;color:#42515e;border-radius:50%;width:42px;height:42px;font-size:29px}' +
      '.transaction-detail-body{padding:16px;display:grid;gap:13px}' +
      '.transaction-detail-card{background:#fff;border:1px solid #d9e4eb;border-radius:18px;padding:16px;box-shadow:0 8px 22px rgba(24,72,100,.1)}' +
      '.transaction-detail-title{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}' +
      '.transaction-detail-title h3{margin:0;font-size:20px}.transaction-detail-title small{display:block;color:#71808c;margin-top:5px}' +
      '.transaction-detail-title strong{font-size:20px;white-space:nowrap}' +
      '.transaction-detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}' +
      '.transaction-detail-grid div{background:#f4f8fb;border-radius:12px;padding:11px}.transaction-detail-grid small{display:block;color:#71808c}.transaction-detail-grid b{display:block;margin-top:3px}' +
      '.transaction-detail-item{display:grid;grid-template-columns:1fr auto;gap:10px;padding:11px 0;border-bottom:1px solid #edf1f4}.transaction-detail-item:last-child{border-bottom:0}' +
      '.transaction-detail-item small{display:block;color:#71808c;margin-top:3px}.transaction-detail-notes{white-space:pre-wrap;color:#53616c}' +
      '.transaction-detail-loading{text-align:center;padding:42px 15px;color:#71808c;font-weight:750}' +
      '@media(min-width:760px){.transaction-detail-overlay{align-items:center;padding:20px}.transaction-detail-sheet{border-radius:25px}}';
    document.head.appendChild(style);
  }

  function ensureOverlay() {
    var overlay = one('#transaction-detail-overlay');
    if (overlay) return overlay;
    overlay = document.createElement('section');
    overlay.id = 'transaction-detail-overlay';
    overlay.className = 'transaction-detail-overlay hidden';
    overlay.setAttribute('aria-hidden', 'true');
    overlay.innerHTML =
      '<div class="transaction-detail-sheet" role="dialog" aria-modal="true" aria-labelledby="transaction-detail-heading">' +
        '<header class="transaction-detail-head"><div><small>TRANSACTION DETAILS</small><h2 id="transaction-detail-heading">Transaction</h2></div><button type="button" class="transaction-detail-close" data-close-transaction-detail>×</button></header>' +
        '<main id="transaction-detail-body" class="transaction-detail-body"></main>' +
      '</div>';
    document.body.appendChild(overlay);
    return overlay;
  }

  function closeDetail() {
    var overlay = one('#transaction-detail-overlay');
    if (!overlay) return;
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  function showLoading() {
    var overlay = ensureOverlay();
    one('#transaction-detail-heading', overlay).textContent = 'Loading...';
    one('#transaction-detail-body', overlay).innerHTML = '<div class="transaction-detail-loading">Loading transaction details...</div>';
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function itemMarkup(item) {
    return '<div class="transaction-detail-item"><div><b>' + esc(item.item_name || 'Item') + '</b><small>' + esc(item.size || '') + ' · Qty ' + esc(item.qty) + ' × ' + money(item.rate) + (num(item.gst_rate) ? ' · GST ' + esc(item.gst_rate) + '%' : '') + '</small></div><strong>' + money(item.line_total) + '</strong></div>';
  }

  function renderDetail(detail) {
    var overlay = ensureOverlay();
    var kindLabel = String(detail.kind || 'transaction').replace(/_/g, ' ').toUpperCase();
    one('#transaction-detail-heading', overlay).textContent = kindLabel;
    var items = Array.isArray(detail.items) ? detail.items : [];
    var reference = detail.number || detail.reference || '';
    var extraAccount = detail.account_name ? '<div><small>Account</small><b>' + esc(detail.account_name) + '</b></div>' : '';
    var toAccount = detail.to_account_name ? '<div><small>To Account</small><b>' + esc(detail.to_account_name) + '</b></div>' : '';
    var billTotals = detail.source === 'bill' || detail.source === 'return'
      ? '<div><small>Subtotal</small><b>' + money(detail.subtotal) + '</b></div><div><small>Tax</small><b>' + money(detail.tax) + '</b></div><div><small>Discount</small><b>' + money(detail.discount) + '</b></div>'
      : '';

    one('#transaction-detail-body', overlay).innerHTML =
      '<section class="transaction-detail-card"><div class="transaction-detail-title"><div><h3>' + esc(detail.title || detail.party_name || kindLabel) + '</h3><small>' + esc(reference) + (detail.date ? ' · ' + esc(detail.date) : '') + '</small></div><strong>' + money(detail.total) + '</strong></div>' +
        '<div class="transaction-detail-grid">' + billTotals +
          '<div><small>Paid</small><b>' + money(detail.paid) + '</b></div><div><small>Due</small><b>' + money(detail.due) + '</b></div>' +
          '<div><small>Payment Mode</small><b>' + esc(detail.payment_mode || '—') + '</b></div><div><small>Status</small><b>' + esc(String(detail.status || 'completed').replace(/_/g, ' ')) + '</b></div>' +
          extraAccount + toAccount +
        '</div></section>' +
      (items.length ? '<section class="transaction-detail-card"><h3>Items</h3>' + items.map(itemMarkup).join('') + '</section>' : '') +
      (detail.notes ? '<section class="transaction-detail-card"><h3>Notes</h3><div class="transaction-detail-notes">' + esc(detail.notes) + '</div></section>' : '');
  }

  async function loadActivity(force) {
    if (!force && activityCache.length && Date.now() - cacheAt < 15000) return activityCache;
    var rows = await api('/api/activity?limit=500');
    activityCache = Array.isArray(rows) ? rows : [];
    cacheAt = Date.now();
    return activityCache;
  }

  function amountFromText(text) {
    return num(String(text || '').replace(/[^0-9.\-]/g, ''));
  }

  function matchCard(card, rows) {
    var titleNode = one('h3,b', card);
    var smallNode = one('small', card);
    var amountNode = one('.row-top>strong', card) || one(':scope>strong', card);
    var title = normalize(titleNode ? titleNode.textContent : '');
    var small = normalize(smallNode ? smallNode.textContent : '');
    var visibleAmount = amountFromText(amountNode ? amountNode.textContent : '');

    var candidates = rows.filter(function (row) {
      var rowTitle = normalize(row.title || row.party_name || row.ref || row.invoice_no || 'transaction');
      var rowRef = normalize(row.ref || row.invoice_no || '');
      var rowDate = normalize(row.entry_date || row.invoice_date || row.created_at || '');
      var titleMatches = !title || rowTitle === title;
      var detailMatches = !small || (rowRef && small.indexOf(rowRef) >= 0) || (rowDate && small.indexOf(rowDate) >= 0);
      var amountMatches = !visibleAmount || Math.abs(num(row.amount != null ? row.amount : row.total) - visibleAmount) < 0.01;
      return titleMatches && detailMatches && amountMatches;
    });

    if (!candidates.length && title) {
      candidates = rows.filter(function (row) {
        return normalize(row.title || row.party_name || row.ref || '') === title;
      });
    }
    return candidates[0] || null;
  }

  async function openForCard(card) {
    if (opening) return;
    opening = true;
    try {
      var rows = await loadActivity(false);
      var row = matchCard(card, rows);
      if (!row) {
        rows = await loadActivity(true);
        row = matchCard(card, rows);
      }
      if (!row || !row.id || !row.kind) throw new Error('Transaction record could not be matched');
      showLoading();
      var detail = await api('/api/transaction-detail/' + encodeURIComponent(row.kind) + '/' + Number(row.id));
      renderDetail(detail);
    } catch (error) {
      closeDetail();
      toast(error.message || 'Transaction could not be opened', true);
    } finally {
      opening = false;
    }
  }

  document.addEventListener('click', function (event) {
    var close = event.target.closest('[data-close-transaction-detail]');
    if (close) {
      event.preventDefault();
      closeDetail();
      return;
    }

    var overlay = event.target.closest('#transaction-detail-overlay');
    if (overlay && event.target === overlay) {
      closeDetail();
      return;
    }

    var card = event.target.closest('.transaction-card');
    if (!card) {
      var compact = event.target.closest('#dashboard-activity .compact-row');
      if (compact) card = compact;
    }
    if (!card) return;
    event.preventDefault();
    openForCard(card);
  }, true);

  window.KiranaTransactionDetail = {
    close: closeDetail,
    isOpen: function () {
      var overlay = one('#transaction-detail-overlay');
      return Boolean(overlay && !overlay.classList.contains('hidden'));
    }
  };

  injectStyle();
  ensureOverlay();
})();
