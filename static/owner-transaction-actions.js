(function () {
  'use strict';

  if (window.__kiranaTransactionActionsLoaded) return;
  window.__kiranaTransactionActionsLoaded = true;

  var selected = new Set();
  var decorating = false;
  var activityCache = [];
  var activityCacheAt = 0;
  var activityPromise = null;

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

  function normalize(value) {
    return String(value == null ? '' : value).replace(/\s+/g, ' ').trim().toLowerCase();
  }

  function num(value) {
    var parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function amountFromText(value) {
    var parsed = Number(String(value || '').replace(/[^0-9.\-]/g, ''));
    return Number.isFinite(parsed) ? parsed : 0;
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

  function keyFor(card) {
    var kind = String(card.getAttribute('data-transaction-kind') || '').trim();
    var id = Number(card.getAttribute('data-transaction-id') || 0);
    return kind && id > 0 ? kind + ':' + id : '';
  }

  async function loadActivity(force) {
    if (!force && activityCache.length && Date.now() - activityCacheAt < 15000) return activityCache;
    if (activityPromise) return activityPromise;
    activityPromise = fetch('/api/activity?limit=300', {
      headers: { Accept: 'application/json' },
      credentials: 'include',
      cache: 'no-store'
    }).then(async function (response) {
      var data = await response.json().catch(function () { return null; });
      if (response.status === 401) {
        window.location.replace('/owner-login');
        throw new Error('Owner session expired');
      }
      if (!response.ok) throw new Error(data && data.detail ? data.detail : 'Transactions could not load');
      activityCache = Array.isArray(data) ? data : [];
      activityCacheAt = Date.now();
      return activityCache;
    }).finally(function () {
      activityPromise = null;
    });
    return activityPromise;
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
      var rowAmount = num(row.amount != null ? row.amount : row.total);
      var titleMatches = !title || rowTitle === title;
      var detailMatches = !small || (rowRef && small.indexOf(rowRef) >= 0) || (rowDate && small.indexOf(rowDate) >= 0);
      var amountMatches = !visibleAmount || Math.abs(rowAmount - visibleAmount) < 0.01;
      return titleMatches && detailMatches && amountMatches;
    });

    if (!candidates.length && title) {
      candidates = rows.filter(function (row) {
        return normalize(row.title || row.party_name || row.ref || '') === title;
      });
    }
    return candidates[0] || null;
  }

  async function hydrateMissingCards() {
    var missing = all('.transaction-card').filter(function (card) { return !keyFor(card); });
    if (!missing.length) return;
    try {
      var rows = await loadActivity(false);
      missing.forEach(function (card) {
        var row = matchCard(card, rows);
        if (!row || !row.id || !row.kind) return;
        card.setAttribute('data-transaction-id', String(Number(row.id)));
        card.setAttribute('data-transaction-kind', String(row.kind));
      });
    } catch (error) {
      console.error('Transaction action matching failed', error);
    }
  }

  function injectStyle() {
    if (one('#txn-action-style')) return;
    var style = document.createElement('style');
    style.id = 'txn-action-style';
    style.textContent =
      '.transaction-card{position:relative}.txn-card-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:12px;padding-top:11px;border-top:1px solid #e6edf2}' +
      '.txn-select-label{display:flex;align-items:center;gap:7px;margin-right:auto;font-size:13px;font-weight:800;color:#52616d;cursor:pointer}.txn-select-label input{width:20px;height:20px;margin:0;accent-color:#0b82c2}' +
      '.txn-share-btn,.txn-print-btn{border:1px solid #c8dbe6;border-radius:10px;background:#fff;padding:8px 11px;font-weight:850;color:#075d96;display:inline-flex;align-items:center;gap:6px}' +
      '.txn-share-btn{background:#e8fff1;border-color:#95ddb0;color:#087c3e}.txn-card-selected{outline:3px solid rgba(11,130,194,.22)}' +
      '.txn-bulk-bar{position:fixed;left:12px;right:12px;bottom:82px;z-index:980;background:#fff;border:1px solid #cbdde8;border-radius:16px;box-shadow:0 12px 34px rgba(18,64,92,.24);padding:11px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}' +
      '.txn-bulk-bar.hidden{display:none!important}.txn-bulk-bar strong{margin-right:auto}.txn-bulk-bar button{border:1px solid #c8dbe6;border-radius:10px;background:#fff;padding:9px 12px;font-weight:850;color:#075d96}.txn-bulk-bar .primary{background:#0b82c2;color:#fff;border-color:#0b82c2}' +
      '@media(min-width:760px){.txn-bulk-bar{left:50%;right:auto;transform:translateX(-50%);width:min(720px,calc(100vw - 40px));bottom:20px}}';
    document.head.appendChild(style);
  }

  function ensureBulkBar() {
    var bar = one('#txn-bulk-bar');
    if (bar) return bar;
    bar = document.createElement('div');
    bar.id = 'txn-bulk-bar';
    bar.className = 'txn-bulk-bar hidden';
    bar.setAttribute('data-transaction-action-control', '1');
    bar.innerHTML =
      '<strong><span id="txn-selected-count">0</span> selected</strong>' +
      '<button type="button" data-txn-select-visible>Select Visible</button>' +
      '<button type="button" data-txn-clear-selection>Clear</button>' +
      '<button type="button" class="primary" data-txn-bulk-print>🖨 Bulk Print</button>';
    document.body.appendChild(bar);
    return bar;
  }

  function updateSelectionUi() {
    all('.transaction-card').forEach(function (card) {
      var key = keyFor(card);
      var checked = key ? selected.has(key) : false;
      card.classList.toggle('txn-card-selected', checked);
      var input = one('[data-txn-bulk-select]', card);
      if (input && input.checked !== checked) input.checked = checked;
    });
    var bar = ensureBulkBar();
    var count = selected.size;
    one('#txn-selected-count', bar).textContent = String(count);
    bar.classList.toggle('hidden', count === 0);
  }

  function decorateCard(card) {
    if (!card || one('.txn-card-actions', card)) return;
    var key = keyFor(card);
    if (!key) return;
    var actions = document.createElement('div');
    actions.className = 'txn-card-actions';
    actions.setAttribute('data-transaction-action-control', '1');
    actions.innerHTML =
      '<label class="txn-select-label"><input type="checkbox" data-txn-bulk-select value="' + esc(key) + '"> Select</label>' +
      '<button type="button" class="txn-print-btn" data-txn-print>🖨 Print</button>' +
      '<button type="button" class="txn-share-btn" data-txn-share>WhatsApp</button>';
    card.appendChild(actions);
  }

  async function decorate() {
    if (decorating) return;
    decorating = true;
    try {
      await hydrateMissingCards();
      all('.transaction-card').forEach(decorateCard);
      updateSelectionUi();
    } finally {
      decorating = false;
    }
  }

  function scheduleDecorate() {
    window.clearTimeout(scheduleDecorate.timer);
    scheduleDecorate.timer = window.setTimeout(decorate, 80);
  }

  async function requestShare(kind, id) {
    var response = await fetch('/api/transaction-share/' + encodeURIComponent(kind) + '/' + Number(id), {
      method: 'POST',
      headers: { Accept: 'application/json' },
      credentials: 'include',
      cache: 'no-store'
    });
    var data = await response.json().catch(function () { return null; });
    if (response.status === 401) {
      window.location.replace('/owner-login');
      throw new Error('Owner session expired');
    }
    if (!response.ok) throw new Error(data && data.detail ? data.detail : 'Share link could not be created');
    return data;
  }

  function parseCard(card) {
    return {
      kind: String(card.getAttribute('data-transaction-kind') || ''),
      id: Number(card.getAttribute('data-transaction-id') || 0)
    };
  }

  async function shareCard(card, button) {
    var row = parseCard(card);
    if (!row.kind || !row.id) return toast('Transaction could not be identified', true);
    var oldText = button.textContent;
    button.disabled = true;
    button.textContent = 'Opening...';
    try {
      var data = await requestShare(row.kind, row.id);
      window.location.href = data.whatsapp_url;
    } catch (error) {
      toast(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = oldText;
    }
  }

  function printKeys(keys) {
    if (!keys.length) return toast('Select at least one transaction', true);
    var url = '/owner/bulk-print?items=' + encodeURIComponent(keys.join(','));
    var opened = null;
    try { opened = window.open(url, '_blank'); } catch (ignore) {}
    if (!opened) window.location.href = url;
  }

  function visibleCards() {
    return all('.page.active .transaction-card').filter(function (card) {
      return card.offsetParent !== null && Boolean(keyFor(card));
    });
  }

  window.addEventListener('click', function (event) {
    var control = event.target.closest('[data-transaction-action-control]');
    if (!control) return;

    var share = event.target.closest('[data-txn-share]');
    var print = event.target.closest('[data-txn-print]');
    var selectVisible = event.target.closest('[data-txn-select-visible]');
    var clear = event.target.closest('[data-txn-clear-selection]');
    var bulkPrint = event.target.closest('[data-txn-bulk-print]');

    if (!share && !print && !selectVisible && !clear && !bulkPrint) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    if (share) {
      var shareCardNode = share.closest('.transaction-card');
      if (shareCardNode) shareCard(shareCardNode, share);
      return;
    }
    if (print) {
      var printCardNode = print.closest('.transaction-card');
      var printKey = printCardNode ? keyFor(printCardNode) : '';
      if (printKey) printKeys([printKey]);
      return;
    }
    if (selectVisible) {
      visibleCards().forEach(function (card) {
        var key = keyFor(card);
        if (key) selected.add(key);
      });
      updateSelectionUi();
      return;
    }
    if (clear) {
      selected.clear();
      updateSelectionUi();
      return;
    }
    if (bulkPrint) printKeys(Array.from(selected));
  }, true);

  window.addEventListener('change', function (event) {
    var input = event.target.closest('[data-txn-bulk-select]');
    if (!input) return;
    event.preventDefault();
    event.stopPropagation();
    var key = String(input.value || '');
    if (input.checked) selected.add(key);
    else selected.delete(key);
    updateSelectionUi();
  }, true);

  function observeList(id) {
    var node = one(id);
    if (!node || typeof MutationObserver === 'undefined') return;
    new MutationObserver(scheduleDecorate).observe(node, { childList: true });
  }

  function boot() {
    injectStyle();
    ensureBulkBar();
    observeList('#activity-list');
    observeList('#transactions-list');
    decorate();
    [500, 1500, 3500].forEach(function (delay) { window.setTimeout(scheduleDecorate, delay); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
