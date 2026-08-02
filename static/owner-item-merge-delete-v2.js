(function () {
  'use strict';

  if (window.__kiranaItemMergeDeleteV134) return;
  window.__kiranaItemMergeDeleteV134 = true;

  var busy = false;
  var sheetState = null;

  function one(selector, root) { return (root || document).querySelector(selector); }
  function all(selector, root) { return Array.prototype.slice.call((root || document).querySelectorAll(selector)); }
  function clean(value) {
    return String(value == null ? '' : value).normalize('NFKC')
      .replace(/[\u200B-\u200D\u2060\uFEFF]/g, '')
      .replace(/\s+/g, ' ').trim().toLowerCase();
  }
  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (character) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character];
    });
  }
  function qty(value) {
    var number = Number(value || 0);
    return Number.isFinite(number) ? number.toLocaleString('en-IN', { maximumFractionDigits: 4 }) : '0';
  }
  function label(item) { return String(item && (item.size || item.unit) || 'Default').trim(); }

  function errorText(value) {
    if (value == null) return '';
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
    if (Array.isArray(value)) return value.map(errorText).filter(Boolean).join(' · ');
    if (typeof value === 'object') {
      if (value.msg) {
        var location = Array.isArray(value.loc) ? value.loc.filter(function (part) { return part !== 'body'; }).join(' › ') : '';
        return (location ? location + ': ' : '') + errorText(value.msg);
      }
      if (value.detail != null) return errorText(value.detail);
      if (value.message != null) return errorText(value.message);
      return Object.keys(value).map(function (key) {
        var text = errorText(value[key]);
        return text ? key + ': ' + text : '';
      }).filter(Boolean).join(' · ');
    }
    return String(value);
  }

  function toast(message, isError) {
    var node = one('#toast') || one('#txn-toast') || one('#bulk-toast');
    if (!node) return;
    node.textContent = errorText(message) || 'Done';
    var base = node.id === 'txn-toast' ? 'txn-toast' : node.id === 'bulk-toast' ? 'bulk-toast' : 'toast';
    node.className = base + ' show' + (isError ? ' error' : '');
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(function () { node.className = base; }, 4800);
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
    if (!response.ok) throw new Error(errorText(data && data.detail != null ? data.detail : data) || 'Request failed (' + response.status + ')');
    return data;
  }

  function injectStyle() {
    if (one('#item-merge-delete-v134-style')) return;
    var style = document.createElement('style');
    style.id = 'item-merge-delete-v134-style';
    style.textContent =
      '.item-merge-delete-wrap{padding:0 20px 24px;background:#fff}' +
      '.item-merge-delete-button{width:100%;border:1px solid #e6a7b5;border-radius:13px;background:#fff4f6;color:#c93658;padding:13px 15px;font-size:15px;font-weight:900;touch-action:manipulation}' +
      '.item-merge-delete-button:disabled{opacity:.55}' +
      '.item-merge-delete-note{display:block;margin-top:7px;color:#7b8790;font-size:11px;text-align:center;line-height:1.45}' +
      '.item-merge-sheet{position:fixed;inset:0;z-index:7200;background:rgba(25,39,50,.58);display:flex;align-items:flex-end;justify-content:center;padding-top:30px}' +
      '.item-merge-panel{width:min(680px,100%);max-height:86vh;overflow:auto;background:#fff;border-radius:24px 24px 0 0;padding:18px 16px calc(18px + env(safe-area-inset-bottom));box-shadow:0 -15px 38px rgba(0,0,0,.24)}' +
      '.item-merge-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:13px}.item-merge-head h2{margin:3px 0 0;font-size:22px}.item-merge-head small{color:#75828c;font-weight:800}.item-merge-close{width:42px;height:42px;border:0;border-radius:50%;background:#edf3f6;font-size:27px;color:#263742}' +
      '.item-merge-source{border-radius:14px;background:#f4f8fa;padding:13px;margin-bottom:12px}.item-merge-source b,.item-merge-source span{display:block}.item-merge-source span{margin-top:5px;color:#65737e}' +
      '.item-merge-warning{border-radius:12px;background:#fff5df;color:#765700;padding:11px 12px;font-size:13px;font-weight:800;line-height:1.45;margin-bottom:12px}' +
      '.item-merge-choice{width:100%;display:grid;grid-template-columns:minmax(0,1fr) auto 22px;gap:10px;align-items:center;border:1px solid #d8e4ea;border-radius:14px;background:#fff;padding:14px 12px;margin:9px 0;text-align:left;color:#22333f}.item-merge-choice b,.item-merge-choice small{display:block}.item-merge-choice small{margin-top:4px;color:#74828c}.item-merge-choice strong{color:#087fbd;white-space:nowrap}.item-merge-choice i{font-style:normal;font-size:25px;color:#81909b}' +
      '.item-merge-cancel,.item-merge-confirm-empty{width:100%;border:0;border-radius:14px;padding:14px;font-size:16px;font-weight:900;margin-top:10px}.item-merge-cancel{background:#edf3f6;color:#344550}.item-merge-confirm-empty{background:#d83c5d;color:#fff}.item-merge-sheet button:disabled{opacity:.55}';
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
    var itemId = activeItemId();
    if (!summary || !itemId) return;

    all('.item-merge-delete-wrap', overlay).forEach(function (wrap) { wrap.remove(); });
    var wrap = document.createElement('div');
    wrap.className = 'item-merge-delete-wrap';
    wrap.setAttribute('data-for-item-id', String(itemId));
    wrap.innerHTML =
      '<button type="button" class="item-merge-delete-button" data-delete-item-size="' + itemId + '">Delete This Size / Batch</button>' +
      '<small class="item-merge-delete-note">Sirf ye size delete hoga. Doosre sizes aur purane bills safe rahenge.</small>';
    summary.insertAdjacentElement('afterend', wrap);
  }

  function closeSheet() {
    var sheet = one('#item-merge-delete-sheet');
    if (sheet) sheet.remove();
    sheetState = null;
    busy = false;
  }

  function openSheet(source, siblings) {
    closeSheet();
    var sourceStock = Number(source.stock || 0);
    sheetState = { source: source, siblings: siblings || [] };
    var sheet = document.createElement('div');
    sheet.id = 'item-merge-delete-sheet';
    sheet.className = 'item-merge-sheet';

    var choices = '';
    if (Math.abs(sourceStock) > 0.00005) {
      choices = siblings.map(function (item) {
        var newStock = Number(item.stock || 0) + sourceStock;
        return '<button type="button" class="item-merge-choice" data-merge-target-id="' + Number(item.id) + '">' +
          '<span><b>' + esc(label(item)) + '</b><small>Current stock ' + esc(qty(item.stock)) + ' ' + esc(item.unit || '') + '</small></span>' +
          '<strong>New ' + esc(qty(newStock)) + '</strong><i>›</i></button>';
      }).join('');
    } else {
      choices = '<button type="button" class="item-merge-confirm-empty" data-confirm-empty-delete>Delete Permanently</button>';
    }

    var warning = Math.abs(sourceStock) > 0.00005
      ? qty(sourceStock) + ' stock selected size me merge hoga, fir ' + label(source) + ' delete hoga.'
      : 'Is size ka stock 0 hai. Sirf ye size permanently delete hoga.';

    sheet.innerHTML =
      '<section class="item-merge-panel">' +
        '<div class="item-merge-head"><div><small>DELETE SIZE / BATCH</small><h2>' + esc(source.name || 'Item') + '</h2></div><button type="button" class="item-merge-close" data-close-delete-sheet>×</button></div>' +
        '<div class="item-merge-source"><b>Delete: ' + esc(label(source)) + '</b><span>Stock ' + esc(qty(sourceStock)) + ' ' + esc(source.unit || '') + '</span></div>' +
        '<div class="item-merge-warning">' + esc(warning) + '</div>' +
        (Math.abs(sourceStock) > 0.00005 ? '<b>Stock kis size me merge karna hai?</b>' : '') +
        choices +
        '<button type="button" class="item-merge-cancel" data-close-delete-sheet>Cancel</button>' +
      '</section>';
    document.body.appendChild(sheet);
  }

  async function prepareDelete(itemId, button) {
    if (busy) return;
    busy = true;
    var oldText = button.textContent;
    button.disabled = true;
    button.textContent = 'Checking...';
    try {
      var items = await api('/api/items?limit=5000');
      var source = (items || []).find(function (item) { return Number(item.id) === Number(itemId); });
      if (!source) throw new Error('Item not found');
      var siblings = (items || []).filter(function (item) {
        return Number(item.id) !== Number(itemId) && clean(item.name) === clean(source.name);
      });
      if (Math.abs(Number(source.stock || 0)) > 0.00005 && !siblings.length) {
        throw new Error('Is size me stock hai, lekin same product ka doosra size nahi mila.');
      }
      openSheet(source, siblings);
    } catch (error) {
      busy = false;
      toast(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = oldText;
    }
  }

  function setSheetBusy(on) {
    all('#item-merge-delete-sheet button').forEach(function (button) { button.disabled = on; });
  }

  async function performDelete(targetItemId) {
    if (!sheetState || busy) return;
    busy = true;
    setSheetBusy(true);
    try {
      var source = sheetState.source;
      var result = await api('/api/items/' + Number(source.id) + '/merge-delete', {
        method: 'POST',
        body: { target_item_id: targetItemId ? Number(targetItemId) : null }
      });
      toast(result.merged_into_id ? 'Size delete ho gaya. Naya stock ' + qty(result.target_stock) + ' hai.' : 'Size delete ho gaya.');
      closeSheet();
      window.setTimeout(function () { window.location.replace('/?page=items&stable=134'); }, 450);
    } catch (error) {
      busy = false;
      setSheetBusy(false);
      toast(error.message, true);
    }
  }

  document.addEventListener('click', function (event) {
    var deleteButton = event.target.closest('[data-delete-item-size]');
    if (deleteButton) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      prepareDelete(Number(deleteButton.getAttribute('data-delete-item-size')), deleteButton);
      return;
    }

    var target = event.target.closest('[data-merge-target-id]');
    if (target) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      performDelete(Number(target.getAttribute('data-merge-target-id')));
      return;
    }

    if (event.target.closest('[data-confirm-empty-delete]')) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      performDelete(null);
      return;
    }

    if (event.target.closest('[data-close-delete-sheet]')) {
      event.preventDefault();
      event.stopPropagation();
      closeSheet();
      return;
    }

    var sheet = event.target.closest('#item-merge-delete-sheet');
    if (sheet && event.target === sheet) closeSheet();
  }, true);

  function schedule() {
    window.clearTimeout(schedule.timer);
    schedule.timer = window.setTimeout(decorate, 90);
  }

  function boot() {
    injectStyle();
    schedule();
    if (typeof MutationObserver !== 'undefined') {
      new MutationObserver(schedule).observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class', 'data-id']
      });
    }
    document.addEventListener('click', schedule, true);
    [350, 900, 1800].forEach(function (delay) { window.setTimeout(schedule, delay); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
