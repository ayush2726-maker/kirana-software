(function () {
  'use strict';

  if (window.__kiranaTransactionActionsLoaded) return;
  window.__kiranaTransactionActionsLoaded = true;

  var selected = new Set();
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
    all('.transaction-card[data-transaction-id][data-transaction-kind]').forEach(function (card) {
      var key = keyFor(card);
      var checked = selected.has(key);
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

  function decorate() {
    if (decorating) return;
    decorating = true;
    try {
      all('.transaction-card[data-transaction-id][data-transaction-kind]').forEach(decorateCard);
      updateSelectionUi();
    } finally {
      decorating = false;
    }
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
    try {
      opened = window.open(url, '_blank');
    } catch (ignore) {}
    if (!opened) window.location.href = url;
  }

  function visibleCards() {
    return all('.page.active .transaction-card[data-transaction-id][data-transaction-kind]').filter(function (card) {
      return card.offsetParent !== null;
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

  function boot() {
    injectStyle();
    ensureBulkBar();
    decorate();
    var observer = new MutationObserver(function () {
      window.clearTimeout(boot.mutationTimer);
      boot.mutationTimer = window.setTimeout(decorate, 50);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
