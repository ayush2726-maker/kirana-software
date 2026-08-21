(function () {
  'use strict';

  if (window.__kiranaItemMergeDeleteV178) return;
  window.__kiranaItemMergeDeleteV178 = true;

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
    if (one('#item-merge-delete-v178-style')) return;
    var style = document.createElement('style');
    style.id = 'item-merge-delete-v178-style';
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
      '.item-merge-select-tools{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:4px 0 8px}.item-merge-select-tools span{color:#65737e;font-size:13px;font-weight:800}.item-merge-select-tools div{display:flex;gap:7px}.item-merge-select-tools button{border:0;border-radius:9px;background:#e7f3fb;color:#087fbd;padding:8px 10px;font-size:12px;font-weight:900}' +
      '.item-merge-select-row{width:100%;display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:10px;align-items:center;border:1px solid #d8e4ea;border-radius:13px;background:#fff;padding:12px;margin:8px 0;text-align:left;color:#22333f}.item-merge-select-row.selected{border-color:#087fbd;background:#eef8fd;box-shadow:0 0 0 2px rgba(8,127,189,.08)}.item-merge-check{width:24px;height:24px;border:2px solid #aab8c1;border-radius:7px;display:grid;place-items:center;color:transparent;font-size:16px;font-weight:900}.item-merge-select-row.selected .item-merge-check{background:#087fbd;border-color:#087fbd;color:#fff}.item-merge-select-row b,.item-merge-select-row small{display:block}.item-merge-select-row small{margin-top:4px;color:#74828c}.item-merge-select-row strong{color:#344550;white-space:nowrap}' +
      '.item-merge-action-title{display:block;margin:16px 2px 4px;color:#65737e;font-size:12px;font-weight:900;text-transform:uppercase;letter-spacing:.04em}.item-merge-unit-note{border-radius:11px;background:#f2f5f7;color:#65737e;padding:10px 11px;font-size:12px;font-weight:800;line-height:1.4;margin-top:10px}.item-merge-success{border-radius:12px;background:#e4f7ec;color:#17713a;padding:11px 12px;font-size:13px;font-weight:900;line-height:1.4;margin-bottom:10px}' +
      '.item-merge-choice{width:100%;display:grid;grid-template-columns:minmax(0,1fr) auto 22px;gap:10px;align-items:center;border:1px solid #d8e4ea;border-radius:14px;background:#fff;padding:14px 12px;margin:9px 0;text-align:left;color:#22333f}.item-merge-choice b,.item-merge-choice small{display:block}.item-merge-choice small{margin-top:4px;color:#74828c}.item-merge-choice strong{color:#087fbd;white-space:nowrap}.item-merge-choice i{font-style:normal;font-size:25px;color:#81909b}' +
      '.item-merge-cancel,.item-merge-confirm-empty,.item-archive-only,.item-zero-remove{width:100%;border:0;border-radius:14px;padding:14px;font-size:16px;font-weight:900;margin-top:10px}.item-merge-cancel{background:#edf3f6;color:#344550}.item-merge-confirm-empty,.item-zero-remove{background:#d83c5d;color:#fff}.item-archive-only{background:#e7f5fb;color:#087fbd}' +
      '.archived-items-button{white-space:nowrap}.archived-item-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;border:1px solid #dde7ec;border-radius:14px;padding:12px;margin:9px 0}.archived-item-row b,.archived-item-row small{display:block}.archived-item-row small{color:#71808a;margin-top:4px}.archived-item-row button{border:0;border-radius:11px;background:#087fbd;color:#fff;padding:10px 13px;font-weight:900}.archived-empty{text-align:center;color:#71808a;padding:28px 10px}.item-merge-sheet button:disabled{opacity:.55}';
    document.head.appendChild(style);
  }

  function activeItemId() {
    var overlay = one('#item-history-overlay');
    var edit = overlay && one('[data-item-history-edit]', overlay);
    return Number(edit && edit.getAttribute('data-id') || 0);
  }

  function decorate() {
    decorateArchivedButton();
    var overlay = one('#item-history-overlay');
    if (!overlay || overlay.classList.contains('hidden')) return;
    var summary = one('.item-history-summary', overlay);
    var itemId = activeItemId();
    if (!summary || !itemId) return;

    var wraps = all('.item-merge-delete-wrap', overlay);
    var keep = null;
    wraps.forEach(function (wrap) {
      if (!keep && Number(wrap.getAttribute('data-for-item-id') || 0) === itemId) {
        keep = wrap;
      } else {
        wrap.remove();
      }
    });
    if (keep) return;

    var wrap = document.createElement('div');
    wrap.className = 'item-merge-delete-wrap';
    wrap.setAttribute('data-for-item-id', String(itemId));
    wrap.innerHTML =
      '<button type="button" class="item-merge-delete-button" data-delete-item-size="' + itemId + '">Archive / Remove Sizes</button>' +
      '<small class="item-merge-delete-note">Select one or multiple sizes together. Historical bills always stay safe.</small>';
    summary.insertAdjacentElement('afterend', wrap);
  }

  function decorateArchivedButton() {
    if (one('#archived-items-button')) return;
    var heading = one('#page-items .page-heading');
    if (!heading) return;
    var button = document.createElement('button');
    button.id = 'archived-items-button';
    button.type = 'button';
    button.className = 'secondary-small archived-items-button';
    button.setAttribute('data-open-archived-items', '');
    button.textContent = 'Archived';
    var actions = one('.bulk-heading-actions', heading);
    if (actions) actions.insertBefore(button, actions.firstChild);
    else heading.appendChild(button);
  }

  function closeItemHistoryIfNeeded(state) {
    if (!state || !state.openerRemoved) return;
    if (window.KiranaItemHistory && typeof window.KiranaItemHistory.close === 'function') {
      window.KiranaItemHistory.close();
      return;
    }
    var overlay = one('#item-history-overlay');
    if (overlay) overlay.classList.add('hidden');
  }

  function closeSheet() {
    var sheet = one('#item-merge-delete-sheet');
    if (sheet) sheet.remove();
    var oldState = sheetState;
    sheetState = null;
    busy = false;
    closeItemHistoryIfNeeded(oldState);
  }

  function selectedSheetItems() {
    if (!sheetState) return [];
    return sheetState.items.filter(function (item) {
      return sheetState.selectedIds.indexOf(Number(item.id)) !== -1;
    });
  }

  function selectedUnit(items) {
    var units = items.map(function (item) { return clean(item.unit); });
    if (!units.length) return '';
    return units.every(function (unit) { return unit === units[0]; }) ? units[0] : null;
  }

  function renderDeleteSheet() {
    var sheet = one('#item-merge-delete-sheet');
    if (!sheet || !sheetState) return;
    var items = sheetState.items;
    var selected = selectedSheetItems();
    var selectedIds = selected.map(function (item) { return Number(item.id); });
    var selectedStock = selected.reduce(function (sum, item) { return sum + Number(item.stock || 0); }, 0);
    var hasStock = selected.some(function (item) { return Math.abs(Number(item.stock || 0)) > 0.00005; });
    var unit = selectedUnit(selected);
    var transferTargets = unit === null ? [] : items.filter(function (item) {
      return selectedIds.indexOf(Number(item.id)) === -1 && clean(item.unit) === unit;
    });
    var success = sheetState.successMessage
      ? '<div class="item-merge-success">' + esc(sheetState.successMessage) + '</div>'
      : '';

    var selection = items.length ?
      '<div class="item-merge-select-tools"><span>' + selected.length + ' of ' + items.length + ' selected</span><div>' +
        '<button type="button" data-select-all-delete-sizes>Select All</button>' +
        '<button type="button" data-clear-delete-sizes>Clear</button>' +
      '</div></div>' +
      items.map(function (item) {
        var isSelected = selectedIds.indexOf(Number(item.id)) !== -1;
        return '<button type="button" class="item-merge-select-row' + (isSelected ? ' selected' : '') + '" data-toggle-delete-item-id="' + Number(item.id) + '" aria-pressed="' + (isSelected ? 'true' : 'false') + '">' +
          '<span class="item-merge-check">✓</span>' +
          '<span><b>' + esc(label(item)) + '</b><small>Sale ' + esc(qty(item.sale_price)) + ' · Stock ' + esc(qty(item.stock)) + ' ' + esc(item.unit || '') + '</small></span>' +
          '<strong>' + esc(item.unit || '') + '</strong>' +
        '</button>';
      }).join('') : '<div class="archived-empty">No active sizes left for this product.</div>';

    var choices = '';
    if (selected.length) {
      choices = '<span class="item-merge-action-title">Apply to ' + selected.length + (selected.length === 1 ? ' selected size' : ' selected sizes') + '</span>' +
        '<button type="button" class="item-archive-only" data-archive-selected>Archive / Hide Selected — Keep Stock</button>';
      if (hasStock) {
        choices += '<button type="button" class="item-zero-remove" data-zero-selected>Set Selected Stock 0 &amp; Remove</button>';
        if (transferTargets.length) {
          choices += '<b class="item-merge-action-title">Or transfer selected stock to</b>' + transferTargets.map(function (item) {
            var newStock = Number(item.stock || 0) + selectedStock;
            return '<button type="button" class="item-merge-choice" data-merge-target-id="' + Number(item.id) + '">' +
              '<span><b>' + esc(label(item)) + '</b><small>Current stock ' + esc(qty(item.stock)) + ' ' + esc(item.unit || '') + '</small></span>' +
              '<strong>New ' + esc(qty(newStock)) + '</strong><i>›</i></button>';
          }).join('');
        } else if (unit === null) {
          choices += '<div class="item-merge-unit-note">For stock transfer, select sizes having the same unit only (kg with kg, pcs with pcs).</div>';
        }
      } else {
        choices += '<button type="button" class="item-merge-confirm-empty" data-remove-selected>Remove Selected Sizes</button>';
      }
    }

    var warning = 'Historical bills will never be deleted. Billed sizes are archived and hidden from New Sale, Purchase and the Customer App.';
    sheet.innerHTML =
      '<section class="item-merge-panel">' +
        '<div class="item-merge-head"><div><small>SELECT MULTIPLE SIZES</small><h2>' + esc(sheetState.productName || 'Item') + '</h2></div><button type="button" class="item-merge-close" data-close-delete-sheet>×</button></div>' +
        success +
        '<div class="item-merge-warning">' + esc(warning) + '</div>' +
        selection + choices +
        '<button type="button" class="item-merge-cancel" data-close-delete-sheet>' + (items.length ? 'Done' : 'Close') + '</button>' +
      '</section>';
  }

  function openSheet(source, siblings) {
    closeSheet();
    var items = [source].concat(siblings || []).filter(function (item, index, rows) {
      return rows.findIndex(function (candidate) { return Number(candidate.id) === Number(item.id); }) === index;
    });
    sheetState = {
      productName: source.name || 'Item',
      openerItemId: Number(source.id),
      openerRemoved: false,
      items: items,
      selectedIds: [Number(source.id)],
      successMessage: ''
    };
    var sheet = document.createElement('div');
    sheet.id = 'item-merge-delete-sheet';
    sheet.className = 'item-merge-sheet';
    document.body.appendChild(sheet);
    renderDeleteSheet();
  }

  async function prepareDelete(itemId, button) {
    if (busy) return;
    busy = true;
    var oldText = button.textContent;
    button.disabled = true;
    button.textContent = 'Checking...';
    try {
      var items = await api('/api/items?limit=2000');
      var source = (items || []).find(function (item) { return Number(item.id) === Number(itemId); });
      if (!source) throw new Error('Item not found');
      var siblings = (items || []).filter(function (item) {
        return Number(item.id) !== Number(itemId) && clean(item.name) === clean(source.name);
      });
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

  async function refreshItemsInPlace() {
    if (typeof window.refreshMasterData === 'function') await window.refreshMasterData();
    if (typeof window.renderItems === 'function') window.renderItems();
  }

  async function performSelected(targetItemId, stockAction, forceArchive) {
    if (!sheetState || busy) return;
    var selected = selectedSheetItems();
    if (!selected.length) {
      toast('Select at least one size.', true);
      return;
    }
    busy = true;
    setSheetBusy(true);
    var completedIds = [];
    var archivedCount = 0;
    var deletedCount = 0;
    var transferred = 0;
    try {
      for (var index = 0; index < selected.length; index += 1) {
        var source = selected[index];
        var result = await api('/api/items/' + Number(source.id) + '/merge-delete', {
          method: 'POST',
          body: {
            target_item_id: targetItemId ? Number(targetItemId) : null,
            stock_action: stockAction || (targetItemId ? 'transfer' : 'keep'),
            force_archive: Boolean(forceArchive)
          }
        });
        completedIds.push(Number(source.id));
        if (result.archived) archivedCount += 1;
        else deletedCount += 1;
        transferred += Math.abs(Number(result.transferred_stock || 0));
        if (result.merged_into_id && result.target_stock != null) {
          var targetItem = sheetState.items.find(function (item) {
            return Number(item.id) === Number(result.merged_into_id);
          });
          if (targetItem) targetItem.stock = Number(result.target_stock);
        }
      }
      sheetState.openerRemoved = sheetState.openerRemoved || completedIds.indexOf(sheetState.openerItemId) !== -1;
      sheetState.items = sheetState.items.filter(function (item) { return completedIds.indexOf(Number(item.id)) === -1; });
      sheetState.selectedIds = [];
      var parts = [];
      if (archivedCount) parts.push(archivedCount + (archivedCount === 1 ? ' size archived' : ' sizes archived'));
      if (deletedCount) parts.push(deletedCount + (deletedCount === 1 ? ' unused size deleted' : ' unused sizes deleted'));
      if (targetItemId && transferred) parts.push('stock transferred');
      sheetState.successMessage = parts.join(' · ') + '. You can select more sizes here.';
      await refreshItemsInPlace();
      busy = false;
      renderDeleteSheet();
      toast(parts.join(' · ') + '.');
    } catch (error) {
      if (completedIds.length && sheetState) {
        sheetState.openerRemoved = sheetState.openerRemoved || completedIds.indexOf(sheetState.openerItemId) !== -1;
        sheetState.items = sheetState.items.filter(function (item) { return completedIds.indexOf(Number(item.id)) === -1; });
        sheetState.selectedIds = sheetState.selectedIds.filter(function (id) { return completedIds.indexOf(Number(id)) === -1; });
        await refreshItemsInPlace().catch(function () {});
      }
      busy = false;
      renderDeleteSheet();
      toast(error.message, true);
    }
  }

  function closeArchivedItems() {
    var sheet = one('#archived-items-sheet');
    if (sheet) sheet.remove();
  }

  async function openArchivedItems() {
    closeArchivedItems();
    var sheet = document.createElement('div');
    sheet.id = 'archived-items-sheet';
    sheet.className = 'item-merge-sheet';
    sheet.innerHTML =
      '<section class="item-merge-panel">' +
        '<div class="item-merge-head"><div><small>HIDDEN FROM BILLING</small><h2>Archived Items</h2></div><button type="button" class="item-merge-close" data-close-archived-items>×</button></div>' +
        '<div id="archived-items-list" class="archived-empty">Loading…</div>' +
      '</section>';
    document.body.appendChild(sheet);
    try {
      var items = await api('/api/items/archived?limit=2000');
      var list = one('#archived-items-list');
      if (!list) return;
      if (!items || !items.length) {
        list.className = 'archived-empty';
        list.textContent = 'No archived items';
        return;
      }
      list.className = '';
      list.innerHTML = items.map(function (item) {
        return '<article class="archived-item-row">' +
          '<div><b>' + esc(item.name || 'Item') + ' · ' + esc(label(item)) + '</b>' +
          '<small>Stock ' + esc(qty(item.stock)) + ' ' + esc(item.unit || '') +
          (item.archived_reason ? ' · ' + esc(item.archived_reason) : '') + '</small></div>' +
          '<button type="button" data-restore-item-id="' + Number(item.id) + '">Restore</button>' +
        '</article>';
      }).join('');
    } catch (error) {
      var failed = one('#archived-items-list');
      if (failed) failed.textContent = error.message || 'Archived items could not be loaded';
      toast(error.message, true);
    }
  }

  async function restoreArchivedItem(itemId, button) {
    if (!itemId || button.disabled) return;
    var oldText = button.textContent;
    button.disabled = true;
    button.textContent = 'Restoring…';
    try {
      await api('/api/items/' + itemId + '/restore', { method: 'POST' });
      var row = button.closest('.archived-item-row');
      if (row) row.remove();
      var list = one('#archived-items-list');
      if (list && !one('.archived-item-row', list)) {
        list.className = 'archived-empty';
        list.textContent = 'No archived items';
      }
      toast('Item restored. It is available in billing again.');
    } catch (error) {
      button.disabled = false;
      button.textContent = oldText;
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
      performSelected(Number(target.getAttribute('data-merge-target-id')), 'transfer', false);
      return;
    }

    var sizeToggle = event.target.closest('[data-toggle-delete-item-id]');
    if (sizeToggle) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      var toggledId = Number(sizeToggle.getAttribute('data-toggle-delete-item-id'));
      var selectedIndex = sheetState ? sheetState.selectedIds.indexOf(toggledId) : -1;
      if (sheetState) {
        if (selectedIndex === -1) sheetState.selectedIds.push(toggledId);
        else sheetState.selectedIds.splice(selectedIndex, 1);
        sheetState.successMessage = '';
        renderDeleteSheet();
      }
      return;
    }

    if (event.target.closest('[data-select-all-delete-sizes]')) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      if (sheetState) {
        sheetState.selectedIds = sheetState.items.map(function (item) { return Number(item.id); });
        sheetState.successMessage = '';
        renderDeleteSheet();
      }
      return;
    }

    if (event.target.closest('[data-clear-delete-sizes]')) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      if (sheetState) {
        sheetState.selectedIds = [];
        sheetState.successMessage = '';
        renderDeleteSheet();
      }
      return;
    }

    if (event.target.closest('[data-archive-selected]')) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      performSelected(null, 'keep', true);
      return;
    }

    if (event.target.closest('[data-zero-selected]')) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      performSelected(null, 'zero', false);
      return;
    }

    if (event.target.closest('[data-remove-selected]')) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      performSelected(null, 'keep', false);
      return;
    }

    var archivedButton = event.target.closest('[data-open-archived-items]');
    if (archivedButton) {
      event.preventDefault();
      event.stopPropagation();
      openArchivedItems();
      return;
    }

    var restoreButton = event.target.closest('[data-restore-item-id]');
    if (restoreButton) {
      event.preventDefault();
      event.stopPropagation();
      restoreArchivedItem(Number(restoreButton.getAttribute('data-restore-item-id')), restoreButton);
      return;
    }

    if (event.target.closest('[data-close-archived-items]')) {
      event.preventDefault();
      event.stopPropagation();
      closeArchivedItems();
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
    var archivedSheet = event.target.closest('#archived-items-sheet');
    if (archivedSheet && event.target === archivedSheet) closeArchivedItems();
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
