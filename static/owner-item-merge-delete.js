(function () {
  'use strict';

  if (window.__kiranaItemMergeDeleteLoaded) return;
  window.__kiranaItemMergeDeleteLoaded = true;

  function one(selector, root) {
    return (root || document).querySelector(selector);
  }

  function clean(value) {
    return String(value == null ? '' : value).normalize('NFKC').replace(/\s+/g, ' ').trim().toLowerCase();
  }

  function label(item) {
    return String(item.size || item.unit || 'Default').trim();
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
    }, 3800);
  }

  async function api(path, options) {
    var config = options || {};
    var headers = Object.assign({ Accept: 'application/json' }, config.headers || {});
    var body = config.body;
    if (body && typeof body !== 'string') {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }
    var response = await fetch(path, Object.assign({}, config, {
      body: body,
      headers: headers,
      credentials: 'include',
      cache: 'no-store'
    }));
    var data = await response.json().catch(function () { return null; });
    if (response.status === 401) {
      window.location.replace('/owner-login');
      throw new Error('Owner session expired');
    }
    if (!response.ok) throw new Error(data && data.detail ? data.detail : 'Request failed');
    return data;
  }

  function injectStyle() {
    if (one('#item-merge-delete-style')) return;
    var style = document.createElement('style');
    style.id = 'item-merge-delete-style';
    style.textContent =
      '.item-merge-delete-wrap{padding:0 20px 24px;background:#fff}' +
      '.item-merge-delete-button{width:100%;border:1px solid #e6a7b5;border-radius:13px;background:#fff4f6;color:#c93658;padding:13px 15px;font-size:15px;font-weight:900}' +
      '.item-merge-delete-button:disabled{opacity:.55}' +
      '.item-merge-delete-note{display:block;margin-top:7px;color:#7b8790;font-size:11px;text-align:center}';
    document.head.appendChild(style);
  }

  function activeItemId() {
    var overlay = one('#item-history-overlay');
    var edit = overlay && one('[data-item-history-edit]', overlay);
    return Number(edit && edit.getAttribute('data-id') || 0);
  }

  function decorate() {
    var overlay = one('#item-history-overlay');
    if (!overlay || overlay.classList.contains('hidden')) return;
    var summary = one('.item-history-summary', overlay);
    if (!summary || one('.item-merge-delete-wrap', summary)) return;
    var itemId = activeItemId();
    if (!itemId) return;
    var wrap = document.createElement('div');
    wrap.className = 'item-merge-delete-wrap';
    wrap.innerHTML = '<button type="button" class="item-merge-delete-button" data-merge-delete-item="' + itemId + '">Delete This Size / Batch</button><small class="item-merge-delete-note">Unused size ka stock same product ke dusre size me merge karke delete hoga.</small>';
    summary.insertAdjacentElement('afterend', wrap);
  }

  function pickTarget(source, siblings) {
    if (!siblings.length) return null;
    if (siblings.length === 1) return siblings[0];
    var choices = siblings.map(function (item, index) {
      return (index + 1) + '. ' + label(item) + ' (Stock ' + item.stock + ')';
    }).join('\n');
    var answer = window.prompt('Stock kis size me merge karna hai?\n' + choices, '1');
    if (answer == null) return undefined;
    var index = Number(answer) - 1;
    return siblings[index] || undefined;
  }

  async function removeItem(button) {
    var itemId = Number(button.getAttribute('data-merge-delete-item') || 0);
    if (!itemId) return;
    button.disabled = true;
    button.textContent = 'Checking...';
    try {
      var items = await api('/api/items?limit=5000');
      var source = (items || []).find(function (item) { return Number(item.id) === itemId; });
      if (!source) throw new Error('Item not found');
      var siblings = (items || []).filter(function (item) {
        return Number(item.id) !== itemId && clean(item.name) === clean(source.name);
      });
      var sourceStock = Number(source.stock || 0);
      var target = null;
      if (Math.abs(sourceStock) > 0.00005) {
        target = pickTarget(source, siblings);
        if (target === undefined) return;
        if (!target) throw new Error('Is size me stock hai aur same product ka doosra size nahi mila. Pehle stock 0 karein.');
        var transferMessage = label(source) + ' ka stock ' + sourceStock + ' ' + (source.unit || '') + ' ko ' + label(target) + ' me merge karke delete karna hai?';
        if (!window.confirm(transferMessage)) return;
      } else if (!window.confirm(label(source) + ' size ko permanently delete karna hai?')) {
        return;
      }

      var result = await api('/api/items/' + itemId + '/merge-delete', {
        method: 'POST',
        body: { target_item_id: target ? Number(target.id) : null }
      });
      if (result.merged_into_id) {
        toast('Size deleted. Stock merge ke baad naya stock ' + result.target_stock + ' hai.');
      } else {
        toast('Item size deleted successfully');
      }
      window.setTimeout(function () { window.location.reload(); }, 550);
    } catch (error) {
      toast(error.message || 'Item delete nahi hua', true);
    } finally {
      button.disabled = false;
      button.textContent = 'Delete This Size / Batch';
    }
  }

  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-merge-delete-item]');
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    removeItem(button);
  }, true);

  function schedule() {
    window.clearTimeout(schedule.timer);
    schedule.timer = window.setTimeout(decorate, 70);
  }

  function boot() {
    injectStyle();
    schedule();
    if (typeof MutationObserver !== 'undefined') {
      new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'data-id'] });
    }
    document.addEventListener('click', schedule, true);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
