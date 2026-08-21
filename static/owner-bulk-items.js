(function () {
  'use strict';

  if (window.__kiranaBulkItemsV178) return;
  window.__kiranaBulkItemsV178 = true;

  var selected = new Set();
  var bulkMode = false;
  var observer = null;

  function one(selector, root) { return (root || document).querySelector(selector); }
  function all(selector, root) { return Array.prototype.slice.call((root || document).querySelectorAll(selector)); }
  function num(value) { var parsed = Number(value || 0); return Number.isFinite(parsed) ? parsed : 0; }
  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char];
    });
  }

  function errorText(value) {
    if (value == null) return '';
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
    if (Array.isArray(value)) {
      return value.map(errorText).filter(Boolean).join(' · ');
    }
    if (typeof value === 'object') {
      if (value.msg) {
        var location = Array.isArray(value.loc) ? value.loc.filter(function (part) { return part !== 'body'; }).join(' › ') : '';
        return (location ? location + ': ' : '') + errorText(value.msg);
      }
      if (value.detail != null) return errorText(value.detail);
      if (value.message != null) return errorText(value.message);
      var parts = Object.keys(value).map(function (key) {
        var text = errorText(value[key]);
        return text ? key + ': ' + text : '';
      }).filter(Boolean);
      return parts.join(' · ');
    }
    return String(value);
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
      throw new Error('Your session expired. Please log in again.');
    }
    if (!response.ok) {
      throw new Error(errorText(data && data.detail != null ? data.detail : data) || 'Request failed (' + response.status + ')');
    }
    return data;
  }

  function notify(message, error) {
    var node = one('#bulk-toast');
    if (!node) return;
    node.textContent = errorText(message) || 'Done';
    node.className = 'bulk-toast show' + (error ? ' error' : '');
    clearTimeout(notify.timer);
    notify.timer = setTimeout(function () { node.className = 'bulk-toast'; }, 4600);
  }

  function inject() {
    if (one('#bulk-items-toggle')) return;
    var heading = one('#page-items .page-heading');
    if (!heading) return;
    var addButton = one('[data-action="new-item"]', heading);
    var controls = document.createElement('div');
    controls.className = 'bulk-heading-actions';
    controls.innerHTML = '<button id="bulk-items-toggle" type="button" class="secondary-small">Bulk Edit</button>';
    if (addButton) {
      addButton.parentNode.insertBefore(controls, addButton);
      controls.appendChild(addButton);
    } else {
      heading.appendChild(controls);
    }

    var filterRow = one('#page-items .filter-row');
    if (filterRow) {
      filterRow.insertAdjacentHTML('afterend',
        '<section id="bulk-items-toolbar" class="bulk-toolbar hidden">' +
          '<div><strong id="bulk-selected-count">0 items selected</strong><small>Select each size or batch separately to edit, archive or remove it</small></div>' +
          '<div class="bulk-toolbar-actions">' +
            '<button type="button" data-bulk-action="select-visible">Select Visible</button>' +
            '<button type="button" data-bulk-action="edit" class="bulk-primary" disabled>Edit Selected</button>' +
            '<button type="button" data-bulk-action="delete" class="bulk-danger" disabled>Archive / Remove</button>' +
            '<button type="button" data-bulk-action="done">Done</button>' +
          '</div>' +
        '</section>'
      );
    }

    document.body.insertAdjacentHTML('beforeend',
      '<section id="bulk-editor" class="bulk-editor hidden" aria-hidden="true">' +
        '<header><button type="button" data-bulk-action="close-editor" class="bulk-back">‹</button><div><small>INVENTORY</small><h2>Bulk Edit Items</h2></div><button id="bulk-save-top" type="button" data-bulk-action="save" class="bulk-save">Save All</button></header>' +
        '<div class="bulk-editor-note">Each selected size or batch is shown separately below.</div>' +
        '<main id="bulk-editor-list"></main>' +
        '<footer><button type="button" data-bulk-action="close-editor">Cancel</button><button type="button" data-bulk-action="save" class="bulk-save">Save All Changes</button></footer>' +
      '</section>' +
      '<div id="bulk-toast" class="bulk-toast"></div>'
    );

    one('#bulk-items-toggle').addEventListener('click', toggleBulkMode);
    document.addEventListener('click', handleClick, true);
    observer = new MutationObserver(function () { enhanceCards(); });
    var list = one('#items-list');
    if (list) observer.observe(list, { childList: true, subtree: true });
    enhanceCards();
  }

  function itemIdFromElement(element) {
    if (!element) return 0;
    var direct = Number(element.getAttribute('data-id') || element.getAttribute('data-bulk-item-id') || 0);
    if (direct) return direct;
    var edit = one('[data-action="edit-item"]', element);
    return edit ? Number(edit.getAttribute('data-id') || 0) : 0;
  }

  function variantRows(card) {
    return all('.item-variant-row[data-id], .item-variant-row[data-action="edit-item"]', card);
  }

  function selectionButton(id, variant) {
    return '<button type="button" class="' + (variant ? 'bulk-variant-select-wrap' : 'bulk-select-wrap') + '" data-bulk-toggle-id="' + id + '" aria-pressed="false" aria-label="Select this size"><span>✓</span></button>';
  }

  function applySelectionState(node, id, selectedClass) {
    var on = selected.has(id);
    node.classList.toggle(selectedClass, on);
    var button = one('[data-bulk-toggle-id="' + id + '"]', node);
    if (button) button.setAttribute('aria-pressed', on ? 'true' : 'false');
  }

  function enhanceCards() {
    all('#items-list .item-card').forEach(function (card) {
      var rows = variantRows(card);
      card.classList.toggle('bulk-mode', bulkMode);

      if (rows.length) {
        all(':scope > .bulk-select-wrap', card).forEach(function (old) { old.remove(); });
        card.removeAttribute('data-bulk-item-id');
        rows.forEach(function (row) {
          var id = itemIdFromElement(row);
          if (!id) return;
          row.setAttribute('data-bulk-item-id', String(id));
          row.classList.toggle('bulk-variant-mode', bulkMode);
          if (!one('[data-bulk-toggle-id="' + id + '"]', row)) {
            row.insertAdjacentHTML('afterbegin', selectionButton(id, true));
          }
          applySelectionState(row, id, 'bulk-variant-selected');
        });
        card.classList.toggle('bulk-selected', rows.some(function (row) {
          return selected.has(itemIdFromElement(row));
        }));
        return;
      }

      var id = itemIdFromElement(card);
      if (!id) return;
      card.setAttribute('data-bulk-item-id', String(id));
      if (!one(':scope > [data-bulk-toggle-id="' + id + '"]', card)) {
        card.insertAdjacentHTML('afterbegin', selectionButton(id, false));
      }
      applySelectionState(card, id, 'bulk-selected');
    });
  }

  function toggleSelection(id) {
    id = Number(id || 0);
    if (!id) return;
    if (selected.has(id)) selected.delete(id); else selected.add(id);
    enhanceCards();
    updateToolbar();
  }

  function toggleBulkMode() {
    bulkMode = !bulkMode;
    if (!bulkMode) selected.clear();
    var toolbar = one('#bulk-items-toolbar');
    if (toolbar) toolbar.classList.toggle('hidden', !bulkMode);
    one('#bulk-items-toggle').textContent = bulkMode ? 'Cancel Bulk' : 'Bulk Edit';
    enhanceCards();
    updateToolbar();
  }

  function updateToolbar() {
    var count = selected.size;
    var label = one('#bulk-selected-count');
    if (label) label.textContent = count + (count === 1 ? ' size / item selected' : ' sizes / items selected');
    all('[data-bulk-action="edit"], [data-bulk-action="delete"]').forEach(function (button) {
      button.disabled = count === 0;
    });
  }

  function handleClick(event) {
    var selection = event.target.closest('[data-bulk-toggle-id]');
    if (selection && bulkMode) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      toggleSelection(Number(selection.getAttribute('data-bulk-toggle-id')));
      return;
    }

    var action = event.target.closest('[data-bulk-action]');
    if (action) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      var name = action.getAttribute('data-bulk-action');
      if (name === 'select-visible') selectVisible();
      if (name === 'edit') openEditor();
      if (name === 'delete') deleteSelected();
      if (name === 'done') toggleBulkMode();
      if (name === 'close-editor') closeEditor();
      if (name === 'save') saveBulkEdits();
      return;
    }

    if (!bulkMode) return;

    var row = event.target.closest('#items-list .item-variant-row[data-bulk-item-id]');
    if (row) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      toggleSelection(Number(row.getAttribute('data-bulk-item-id')));
      return;
    }

    var card = event.target.closest('#items-list .item-card[data-bulk-item-id]');
    if (card && !event.target.closest('input, select, textarea')) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      toggleSelection(Number(card.getAttribute('data-bulk-item-id')));
    }
  }

  function visibleIds() {
    var ids = [];
    all('#items-list .item-variant-row[data-bulk-item-id]').forEach(function (row) {
      if (row.offsetParent !== null) ids.push(Number(row.getAttribute('data-bulk-item-id')));
    });
    all('#items-list .item-card[data-bulk-item-id]').forEach(function (card) {
      if (card.offsetParent !== null) ids.push(Number(card.getAttribute('data-bulk-item-id')));
    });
    return Array.from(new Set(ids.filter(Boolean)));
  }

  function selectVisible() {
    var ids = visibleIds();
    var allSelected = ids.length > 0 && ids.every(function (id) { return selected.has(id); });
    ids.forEach(function (id) {
      if (allSelected) selected.delete(id); else selected.add(id);
    });
    enhanceCards();
    updateToolbar();
  }

  async function openEditor() {
    if (!selected.size) return;
    try {
      var items = await api('/api/items?limit=2000');
      var rows = items.filter(function (item) { return selected.has(Number(item.id)); });
      if (!rows.length) throw new Error('Selected sizes were not found');
      one('#bulk-editor-list').innerHTML = rows.map(editorRow).join('');
      one('#bulk-editor').classList.remove('hidden');
      one('#bulk-editor').setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
    } catch (error) {
      notify(error.message, true);
    }
  }

  function editorRow(item) {
    return '<article class="bulk-edit-card" data-bulk-edit-id="' + Number(item.id) + '">' +
      '<div class="bulk-edit-title"><strong>' + esc(item.name) + '</strong><small>' + esc(item.size || item.unit || '') + (item.sku ? ' · ' + esc(item.sku) : '') + '</small></div>' +
      '<div class="bulk-edit-grid">' +
        field('Name', 'name', item.name, 'text', true) +
        field('Size', 'size', item.size || '', 'text') +
        field('Unit', 'unit', item.unit || 'pcs', 'text') +
        field('SKU', 'sku', item.sku || '', 'text') +
        field('Category', 'category', item.category || '', 'text') +
        field('Sale Rate', 'sale_price', item.sale_price, 'number') +
        field('Purchase Rate', 'purchase_price', item.purchase_price, 'number') +
        field('Stock', 'stock', item.stock, 'number') +
        field('Minimum Stock', 'min_stock', item.min_stock, 'number') +
        field('GST %', 'gst_rate', item.gst_rate, 'number') +
        field('MRP', 'mrp', item.mrp, 'number') +
      '</div>' +
      '<input type="hidden" data-bulk-field="barcode" value="' + esc(item.barcode || '') + '">' +
      '<input type="hidden" data-bulk-field="hsn" value="' + esc(item.hsn || '') + '">' +
    '</article>';
  }

  function field(label, key, value, type, required) {
    var attrs = type === 'number' ? ' inputmode="decimal" step="0.01"' : '';
    return '<label>' + esc(label) + '<input data-bulk-field="' + key + '" type="' + type + '" value="' + esc(value) + '"' + attrs + (required ? ' required' : '') + '></label>';
  }

  function closeEditor() {
    var editor = one('#bulk-editor');
    if (!editor || editor.classList.contains('hidden')) return false;
    editor.classList.add('hidden');
    editor.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    return true;
  }

  async function refreshItemsInPlace() {
    if (typeof window.refreshMasterData === 'function') await window.refreshMasterData();
    if (typeof window.renderItems === 'function') window.renderItems();
    enhanceCards();
    updateToolbar();
  }

  async function saveBulkEdits() {
    var cards = all('#bulk-editor-list [data-bulk-edit-id]');
    if (!cards.length) return;
    var items = cards.map(function (card) {
      function value(key) { var input = one('[data-bulk-field="' + key + '"]', card); return input ? input.value : ''; }
      return {
        id: Number(card.getAttribute('data-bulk-edit-id')),
        name: value('name').trim(),
        size: value('size').trim(),
        unit: value('unit').trim() || 'pcs',
        sku: value('sku').trim(),
        category: value('category').trim(),
        sale_price: num(value('sale_price')),
        purchase_price: num(value('purchase_price')),
        stock: num(value('stock')),
        min_stock: num(value('min_stock')),
        gst_rate: num(value('gst_rate')),
        mrp: num(value('mrp')),
        barcode: value('barcode'),
        hsn: value('hsn')
      };
    });
    if (items.some(function (item) { return !item.name; })) return notify('Every item needs a name', true);

    var buttons = all('[data-bulk-action="save"]');
    buttons.forEach(function (button) { button.disabled = true; button.textContent = 'Saving...'; });
    try {
      var result = await api('/api/items/bulk-update', { method: 'POST', body: { items: items } });
      notify(result.updated + ' size / item updated');
      buttons.forEach(function (button) {
        button.disabled = false;
        button.textContent = button.id === 'bulk-save-top' ? 'Save All' : 'Save All Changes';
      });
      closeEditor();
      await refreshItemsInPlace();
    } catch (error) {
      buttons.forEach(function (button) {
        button.disabled = false;
        button.textContent = button.id === 'bulk-save-top' ? 'Save All' : 'Save All Changes';
      });
      notify(error.message, true);
    }
  }

  async function deleteSelected() {
    if (!selected.size) return;
    var count = selected.size;
    if (!window.confirm('Remove ' + count + (count === 1 ? ' selected size / item?' : ' selected sizes / items?') + '\n\nSizes used in bills will be archived and hidden. Never-used sizes will be permanently deleted. Historical bills stay safe.')) return;
    try {
      var result = await api('/api/items/bulk-delete', {
        method: 'POST',
        body: { ids: Array.from(selected) }
      });
      var message = (result.archived || 0) + ' billed size archived, ' + (result.deleted || 0) + ' unused size deleted.';
      notify(message, false);
      (result.deleted_ids || []).forEach(function (id) { selected.delete(Number(id)); });
      (result.archived_ids || []).forEach(function (id) { selected.delete(Number(id)); });
      await refreshItemsInPlace();
    } catch (error) {
      notify(error.message, true);
    }
  }

  window.KiranaBulkItems = {
    handleBack: function () {
      if (closeEditor()) return true;
      if (bulkMode) {
        toggleBulkMode();
        return true;
      }
      return false;
    }
  };

  inject();
})();
