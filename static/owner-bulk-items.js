(function () {
  'use strict';

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
    if (!response.ok) throw new Error(data && data.detail ? data.detail : 'Request failed (' + response.status + ')');
    return data;
  }

  function notify(message, error) {
    var node = one('#bulk-toast');
    if (!node) return;
    node.textContent = String(message || 'Done');
    node.className = 'bulk-toast show' + (error ? ' error' : '');
    clearTimeout(notify.timer);
    notify.timer = setTimeout(function () { node.className = 'bulk-toast'; }, 3600);
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
          '<div><strong id="bulk-selected-count">0 selected</strong><small>Select items to edit or delete together</small></div>' +
          '<div class="bulk-toolbar-actions">' +
            '<button type="button" data-bulk-action="select-visible">Select Visible</button>' +
            '<button type="button" data-bulk-action="edit" class="bulk-primary" disabled>Edit Selected</button>' +
            '<button type="button" data-bulk-action="delete" class="bulk-danger" disabled>Delete</button>' +
            '<button type="button" data-bulk-action="done">Done</button>' +
          '</div>' +
        '</section>'
      );
    }

    document.body.insertAdjacentHTML('beforeend',
      '<section id="bulk-editor" class="bulk-editor hidden" aria-hidden="true">' +
        '<header><button type="button" data-bulk-action="close-editor" class="bulk-back">‹</button><div><small>INVENTORY</small><h2>Bulk Edit Items</h2></div><button id="bulk-save-top" type="button" data-bulk-action="save" class="bulk-save">Save All</button></header>' +
        '<div class="bulk-editor-note">Edit each selected item below. All changes will be saved together.</div>' +
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

  function itemIdFromCard(card) {
    var edit = one('[data-action="edit-item"]', card);
    return edit ? Number(edit.getAttribute('data-id') || 0) : 0;
  }

  function enhanceCards() {
    all('#items-list .item-card').forEach(function (card) {
      var id = itemIdFromCard(card);
      if (!id) return;
      card.setAttribute('data-bulk-item-id', String(id));
      if (!one('.bulk-select-wrap', card)) {
        card.insertAdjacentHTML('afterbegin',
          '<label class="bulk-select-wrap"><input type="checkbox" data-bulk-select="' + id + '" aria-label="Select item"><span>✓</span></label>'
        );
      }
      card.classList.toggle('bulk-mode', bulkMode);
      card.classList.toggle('bulk-selected', selected.has(id));
      var checkbox = one('[data-bulk-select]', card);
      if (checkbox) checkbox.checked = selected.has(id);
    });
  }

  function toggleBulkMode() {
    bulkMode = !bulkMode;
    if (!bulkMode) selected.clear();
    one('#bulk-items-toolbar').classList.toggle('hidden', !bulkMode);
    one('#bulk-items-toggle').textContent = bulkMode ? 'Cancel Bulk' : 'Bulk Edit';
    enhanceCards();
    updateToolbar();
  }

  function updateToolbar() {
    var count = selected.size;
    var label = one('#bulk-selected-count');
    if (label) label.textContent = count + (count === 1 ? ' item selected' : ' items selected');
    all('[data-bulk-action="edit"], [data-bulk-action="delete"]').forEach(function (button) {
      button.disabled = count === 0;
    });
  }

  function handleClick(event) {
    var checkbox = event.target.closest('[data-bulk-select]');
    if (checkbox) {
      if (!bulkMode) return;
      event.stopPropagation();
      var id = Number(checkbox.getAttribute('data-bulk-select'));
      if (checkbox.checked) selected.add(id); else selected.delete(id);
      var card = checkbox.closest('.item-card');
      if (card) card.classList.toggle('bulk-selected', checkbox.checked);
      updateToolbar();
      return;
    }

    if (bulkMode) {
      var card = event.target.closest('#items-list .item-card');
      if (card && !event.target.closest('button, input, select, textarea, label')) {
        event.preventDefault();
        event.stopPropagation();
        var cardId = Number(card.getAttribute('data-bulk-item-id'));
        var cardCheckbox = one('[data-bulk-select]', card);
        if (cardCheckbox) {
          cardCheckbox.checked = !cardCheckbox.checked;
          if (cardCheckbox.checked) selected.add(cardId); else selected.delete(cardId);
          card.classList.toggle('bulk-selected', cardCheckbox.checked);
          updateToolbar();
        }
        return;
      }
    }

    var action = event.target.closest('[data-bulk-action]');
    if (!action) return;
    event.preventDefault();
    event.stopPropagation();
    var name = action.getAttribute('data-bulk-action');
    if (name === 'select-visible') selectVisible();
    if (name === 'edit') openEditor();
    if (name === 'delete') deleteSelected();
    if (name === 'done') toggleBulkMode();
    if (name === 'close-editor') closeEditor();
    if (name === 'save') saveBulkEdits();
  }

  function selectVisible() {
    var visibleIds = all('#items-list .item-card').filter(function (card) {
      return card.offsetParent !== null;
    }).map(itemIdFromCard).filter(Boolean);
    var allSelected = visibleIds.length > 0 && visibleIds.every(function (id) { return selected.has(id); });
    visibleIds.forEach(function (id) {
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
      if (!rows.length) throw new Error('Selected items were not found');
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
      '<div class="bulk-edit-title"><strong>' + esc(item.name) + '</strong><small>' + esc(item.sku || '') + '</small></div>' +
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
      notify(result.updated + ' items updated');
      setTimeout(function () { window.location.replace('/?page=items&stable=103'); }, 500);
    } catch (error) {
      buttons.forEach(function (button) { button.disabled = false; button.textContent = button.id === 'bulk-save-top' ? 'Save All' : 'Save All Changes'; });
      notify(error.message, true);
    }
  }

  async function deleteSelected() {
    if (!selected.size) return;
    var count = selected.size;
    if (!window.confirm('Delete ' + count + (count === 1 ? ' selected item?' : ' selected items?') + '\n\nItems already used in bills will be kept to protect transaction history.')) return;
    try {
      var result = await api('/api/items/bulk-delete', { method: 'POST', body: { ids: Array.from(selected) } });
      var message = result.deleted + ' item(s) deleted.';
      if (result.blocked && result.blocked.length) message += ' ' + result.blocked.length + ' item(s) were kept because they are used in transactions.';
      notify(message, Boolean(result.blocked && result.blocked.length && !result.deleted));
      setTimeout(function () { window.location.replace('/?page=items&stable=103'); }, 900);
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
