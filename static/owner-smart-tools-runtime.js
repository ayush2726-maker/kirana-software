(function () {
  'use strict';

  // The original smart-tools page shipped with an inline runtime. Some Android
  // WebViews render the HTML/CSS but do not execute that inline block. Only
  // activate this external fallback when the original runtime did not select a
  // panel, which prevents duplicate Save/Generate handlers on healthy clients.
  if (window.__kiranaSmartToolsRuntime136) return;
  if (document.querySelector('.panel.active')) return;
  window.__kiranaSmartToolsRuntime136 = true;

  var items = [];
  var parties = [];
  var draftLines = [];
  var selectedBarcodes = new Set();
  var busy = false;

  function q(id) {
    return document.getElementById(id);
  }

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char];
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

  function today() {
    var now = new Date();
    var local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 10);
  }

  function readableError(data, fallback) {
    if (!data) return fallback || 'Request failed';
    if (typeof data === 'string') return data;
    if (Array.isArray(data)) {
      return data.map(function (row) {
        if (typeof row === 'string') return row;
        return row && (row.msg || row.message) ? (row.msg || row.message) : JSON.stringify(row);
      }).join('\n');
    }
    if (data.detail) return readableError(data.detail, fallback);
    if (data.message) return String(data.message);
    return fallback || 'Request failed';
  }

  function toast(message, isError) {
    var node = q('toast');
    if (!node) return;
    node.textContent = String(message || 'Done');
    node.className = 'toast show' + (isError ? ' error' : '');
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(function () {
      node.className = 'toast';
    }, 3600);
  }

  function setStatus(message, isError) {
    var node = q('ocr-status');
    if (!node) return;
    node.textContent = String(message || '');
    node.className = 'status show' + (isError ? ' error' : '');
  }

  function api(path, options) {
    var config = options || {};
    var headers = Object.assign({ Accept: 'application/json' }, config.headers || {});
    var body = config.body;
    if (body && !(body instanceof FormData) && typeof body !== 'string') {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }
    return fetch(path, Object.assign({}, config, {
      body: body,
      headers: headers,
      credentials: 'include',
      cache: 'no-store'
    })).then(function (response) {
      return response.json().catch(function () { return null; }).then(function (data) {
        if (response.status === 401) {
          window.location.replace('/owner-login');
          throw new Error('Owner session expired');
        }
        if (!response.ok) {
          throw new Error(readableError(data, 'Request failed (' + response.status + ')'));
        }
        return data;
      });
    });
  }

  function setTab(name) {
    ['photo', 'barcode'].forEach(function (tab) {
      var button = q('tab-' + tab);
      var panel = q('panel-' + tab);
      if (button) button.classList.toggle('active', tab === name);
      if (panel) panel.classList.toggle('active', tab === name);
    });
    try {
      history.replaceState(null, '', name === 'barcode' ? '/owner/smart-tools#barcode' : '/owner/smart-tools#photo');
    } catch (ignore) {}
    if (name === 'barcode') renderBarcodeItems();
  }

  function itemLabel(item) {
    return String(item.name || '') + (item.size ? ' | ' + item.size : '');
  }

  function findItemByLabel(value) {
    var clean = String(value || '').trim().toLowerCase();
    var exact = items.find(function (item) {
      return itemLabel(item).toLowerCase() === clean;
    });
    if (exact) return exact;
    return items.find(function (item) {
      return String(item.name || '').toLowerCase() === clean;
    }) || null;
  }

  function fillItemOptions() {
    var list = q('item-options');
    if (!list) return;
    list.innerHTML = items.map(function (item) {
      return '<option value="' + esc(itemLabel(item)) + '"></option>';
    }).join('');
  }

  function fillParties(suggestedId) {
    var select = q('party-id');
    var billType = q('bill-type');
    if (!select || !billType) return;
    var wanted = billType.value === 'purchase' ? 'supplier' : 'customer';
    var rows = parties.filter(function (party) {
      return party.type === wanted || party.type === 'both';
    });
    select.innerHTML = '<option value="">Cash / No party</option>' + rows.map(function (party) {
      return '<option value="' + Number(party.id) + '">' + esc(party.name) + (party.phone ? ' · ' + esc(party.phone) : '') + '</option>';
    }).join('');
    if (suggestedId && rows.some(function (party) { return Number(party.id) === Number(suggestedId); })) {
      select.value = String(suggestedId);
    }
  }

  function blankLine() {
    return {
      item_id: null,
      item_name: '',
      size: '',
      qty: 1,
      rate: 0,
      gst_rate: 0,
      match_confidence: 0
    };
  }

  function lineAmount(line) {
    var base = num(line.qty) * num(line.rate);
    return base + (base * num(line.gst_rate) / 100);
  }

  function updateTotal() {
    var totalNode = q('draft-total');
    if (!totalNode) return;
    var subtotal = draftLines.reduce(function (sum, line) {
      return sum + lineAmount(line);
    }, 0);
    var discount = q('discount') ? num(q('discount').value) : 0;
    totalNode.textContent = money(Math.max(0, subtotal - discount));
  }

  function renderDraft() {
    var body = q('draft-lines');
    if (!body) return;
    if (!draftLines.length) draftLines = [blankLine()];
    body.innerHTML = draftLines.map(function (line, index) {
      var confidence = num(line.match_confidence);
      var matchText = line.item_id ? (confidence >= 0.75 ? 'Matched' : 'Check match') : '';
      var displayedName = line.item_name + (line.item_id && line.size ? ' | ' + line.size : '');
      return '<tr data-index="' + index + '">' +
        '<td>' + (index + 1) + '</td>' +
        '<td><input class="item" data-field="item_name" list="item-options" value="' + esc(displayedName) + '" placeholder="Item name" />' +
          (matchText ? '<span class="match ' + (confidence < 0.75 ? 'low' : '') + '">' + matchText + ' ' + Math.round(confidence * 100) + '%</span>' : '') + '</td>' +
        '<td><input class="size" data-field="size" value="' + esc(line.size || '') + '" /></td>' +
        '<td><input class="num" data-field="qty" type="number" min="0.001" step="0.001" value="' + num(line.qty) + '" /></td>' +
        '<td><input class="num" data-field="rate" type="number" min="0" step="0.01" value="' + num(line.rate) + '" /></td>' +
        '<td><input class="num" data-field="gst_rate" type="number" min="0" step="0.01" value="' + num(line.gst_rate) + '" /></td>' +
        '<td class="num"><b>' + money(lineAmount(line)) + '</b></td>' +
        '<td><button type="button" class="remove" data-remove="' + index + '">×</button></td>' +
        '</tr>';
    }).join('');
    updateTotal();
  }

  function loadData() {
    return Promise.all([
      api('/api/items?limit=2000'),
      api('/api/parties')
    ]).then(function (results) {
      items = results[0] || [];
      parties = results[1] || [];
      fillItemOptions();
      fillParties();
      renderBarcodeItems();
    }).catch(function (error) {
      toast(error.message, true);
      var count = q('barcode-count');
      if (count) count.textContent = 'Items load nahi hue: ' + error.message;
    });
  }

  function readPhoto() {
    if (busy) return;
    var input = q('bill-photo');
    var file = input && input.files ? input.files[0] : null;
    if (!file) {
      toast('Bill photo choose karein', true);
      return;
    }
    busy = true;
    q('read-photo').disabled = true;
    setStatus('Photo read ho rahi hai… OCR ke baad editable draft khulega.');
    var form = new FormData();
    form.append('file', file);
    form.append('bill_type', q('bill-type').value);
    api('/api/photo-bill/ocr', { method: 'POST', body: form }).then(function (data) {
      draftLines = (data.items || []).map(function (row) {
        return Object.assign(blankLine(), row);
      });
      q('invoice-no').value = data.invoice_no || '';
      q('invoice-date').value = data.invoice_date || today();
      q('ocr-raw').textContent = data.ocr_text || '';
      q('paid').value = '0';
      q('discount').value = '0';
      q('payment-mode').value = 'credit';
      var suggestedParty = null;
      if (data.party_matches && data.party_matches.length && num(data.party_matches[0].score) >= 0.78) {
        suggestedParty = data.party_matches[0].id;
      }
      fillParties(suggestedParty);
      renderDraft();
      q('bill-draft').classList.add('show');
      setStatus(String(data.detected_lines || 0) + ' item rows detect hui. Save se pehle qty/rate/item ek baar check karein.');
      q('bill-draft').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }).catch(function (error) {
      setStatus(error.message, true);
      toast(error.message, true);
    }).finally(function () {
      busy = false;
      q('read-photo').disabled = false;
    });
  }

  function saveBill() {
    if (busy) return;
    var clean = draftLines.filter(function (line) {
      return String(line.item_name || '').trim() && num(line.qty) > 0;
    });
    if (!clean.length) {
      toast('Kam se kam ek valid item row chahiye', true);
      return;
    }
    var payload = {
      invoice_no: q('invoice-no').value.trim(),
      party_id: q('party-id').value ? Number(q('party-id').value) : null,
      invoice_date: q('invoice-date').value || today(),
      discount: num(q('discount').value),
      paid: num(q('paid').value),
      payment_mode: q('payment-mode').value || 'credit',
      notes: 'Created from bill photo OCR; reviewed before save',
      items: clean.map(function (line) {
        return {
          item_id: line.item_id ? Number(line.item_id) : null,
          item_name: String(line.item_name || '').split(' | ')[0].trim(),
          size: String(line.size || '').trim(),
          qty: num(line.qty),
          rate: num(line.rate),
          gst_rate: num(line.gst_rate)
        };
      })
    };
    busy = true;
    q('save-bill').disabled = true;
    var type = q('bill-type').value;
    api(type === 'purchase' ? '/api/purchases' : '/api/sales', {
      method: 'POST',
      body: payload
    }).then(function (saved) {
      toast((type === 'purchase' ? 'Purchase' : 'Sale') + ' bill saved');
      setStatus('Bill save ho gaya: ' + String(saved.invoice_no || ''));
      q('save-bill').textContent = 'Saved ✓';
      window.setTimeout(function () { q('save-bill').textContent = 'Save Bill'; }, 1800);
    }).catch(function (error) {
      toast(error.message, true);
      setStatus(error.message, true);
    }).finally(function () {
      busy = false;
      q('save-bill').disabled = false;
    });
  }

  function resetPhoto() {
    q('bill-photo').value = '';
    q('photo-name').textContent = 'Clear, straight full bill photo best rahegi';
    q('bill-draft').classList.remove('show');
    q('ocr-status').className = 'status';
    draftLines = [];
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function visibleBarcodeRows() {
    var search = q('barcode-search');
    var query = String(search ? search.value : '').trim().toLowerCase();
    return items.filter(function (item) {
      return !query || [item.name, item.size, item.sku, item.barcode].join(' ').toLowerCase().indexOf(query) >= 0;
    });
  }

  function renderBarcodeItems() {
    var container = q('barcode-list');
    var count = q('barcode-count');
    if (!container || !count) return;
    var rows = visibleBarcodeRows();
    count.textContent = selectedBarcodes.size + ' selected · ' + rows.length + ' visible';
    if (!rows.length) {
      container.innerHTML = '<div class="empty">No matching items</div>';
      return;
    }
    container.innerHTML = rows.map(function (item) {
      var checked = selectedBarcodes.has(Number(item.id));
      return '<label class="barcode-row">' +
        '<input type="checkbox" data-barcode-id="' + Number(item.id) + '" ' + (checked ? 'checked' : '') + ' />' +
        '<div><b>' + esc(item.name) + '</b><small>' + esc(item.size || item.unit || '') + (item.sku ? ' · ' + esc(item.sku) : '') + '</small></div>' +
        '<span class="code-pill">' + esc(item.barcode || 'Barcode will be generated') + '</span>' +
        '</label>';
    }).join('');
  }

  function generateAndPrint() {
    if (!selectedBarcodes.size) {
      toast('Barcode ke liye item select karein', true);
      return;
    }
    var ids = Array.from(selectedBarcodes);
    var copies = Math.max(1, Math.min(20, Number(q('barcode-copies').value || 1)));
    q('generate-print').disabled = true;
    api('/api/barcodes/generate', {
      method: 'POST',
      body: { item_ids: ids, force: false }
    }).then(function (data) {
      (data.items || []).forEach(function (updated) {
        var index = items.findIndex(function (item) { return Number(item.id) === Number(updated.id); });
        if (index >= 0) items[index] = Object.assign({}, items[index], updated);
      });
      renderBarcodeItems();
      window.location.assign('/owner/barcodes/print?ids=' + encodeURIComponent(ids.join(',')) + '&copies=' + encodeURIComponent(copies));
    }).catch(function (error) {
      toast(error.message, true);
    }).finally(function () {
      q('generate-print').disabled = false;
    });
  }

  // Tabs and top navigation.
  q('back').addEventListener('click', function () { window.location.assign('/'); });
  document.querySelectorAll('[data-tab]').forEach(function (button) {
    button.addEventListener('click', function () { setTab(button.getAttribute('data-tab')); });
  });

  // Photo-bill handlers.
  q('bill-photo').addEventListener('change', function () {
    var file = this.files && this.files[0];
    q('photo-name').textContent = file ? file.name : 'Clear, straight full bill photo best rahegi';
  });
  q('bill-type').addEventListener('change', function () { fillParties(); resetPhoto(); });
  q('read-photo').addEventListener('click', readPhoto);
  q('save-bill').addEventListener('click', saveBill);
  q('scan-again').addEventListener('click', resetPhoto);
  q('add-line').addEventListener('click', function () { draftLines.push(blankLine()); renderDraft(); });
  q('discount').addEventListener('input', updateTotal);
  q('draft-lines').addEventListener('input', function (event) {
    var row = event.target.closest('tr');
    var field = event.target.getAttribute('data-field');
    if (!row || !field) return;
    var index = Number(row.getAttribute('data-index'));
    var line = draftLines[index];
    if (!line) return;
    if (['qty', 'rate', 'gst_rate'].indexOf(field) >= 0) line[field] = num(event.target.value);
    else line[field] = event.target.value;
    if (field === 'item_name') {
      var matched = findItemByLabel(event.target.value);
      if (matched) {
        line.item_id = Number(matched.id);
        line.item_name = matched.name;
        line.size = matched.size || '';
        line.gst_rate = num(matched.gst_rate);
        if (num(line.rate) <= 0) {
          line.rate = num(q('bill-type').value === 'purchase' ? matched.purchase_price : matched.sale_price);
        }
        line.match_confidence = 1;
      } else {
        line.item_id = null;
        line.match_confidence = 0;
      }
    }
    updateTotal();
  });
  q('draft-lines').addEventListener('change', function (event) {
    if (event.target.getAttribute('data-field') === 'item_name') renderDraft();
  });
  q('draft-lines').addEventListener('click', function (event) {
    var index = event.target.getAttribute('data-remove');
    if (index == null) return;
    draftLines.splice(Number(index), 1);
    renderDraft();
  });

  // Barcode handlers.
  q('barcode-search').addEventListener('input', renderBarcodeItems);
  q('barcode-list').addEventListener('change', function (event) {
    var id = event.target.getAttribute('data-barcode-id');
    if (!id) return;
    if (event.target.checked) selectedBarcodes.add(Number(id));
    else selectedBarcodes.delete(Number(id));
    renderBarcodeItems();
  });
  q('select-visible').addEventListener('click', function () {
    visibleBarcodeRows().forEach(function (item) { selectedBarcodes.add(Number(item.id)); });
    renderBarcodeItems();
  });
  q('clear-selected').addEventListener('click', function () {
    selectedBarcodes.clear();
    renderBarcodeItems();
  });
  q('generate-print').addEventListener('click', generateAndPrint);

  q('invoice-date').value = today();
  setTab(window.location.hash === '#barcode' ? 'barcode' : 'photo');
  loadData();
})();
