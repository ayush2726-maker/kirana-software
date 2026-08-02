(function () {
  'use strict';

  if (window.__kiranaOwnerImportCenterLoaded) return;
  window.__kiranaOwnerImportCenterLoaded = true;

  var importing = false;
  var lastType = 'items';

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

  function readableError(value) {
    if (!value) return 'Import failed';
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) {
      return value.map(function (row) {
        if (typeof row === 'string') return row;
        var location = row && row.loc ? row.loc.join(' → ') + ': ' : '';
        return location + (row && (row.msg || row.message) ? (row.msg || row.message) : JSON.stringify(row));
      }).join('\n');
    }
    if (value.detail) return readableError(value.detail);
    if (value.message) return String(value.message);
    try { return JSON.stringify(value); } catch (ignore) { return String(value); }
  }

  function toast(message, isError) {
    var node = one('#toast') || one('#txn-toast');
    if (!node) {
      window.alert(String(message || 'Done'));
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
    var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timeout = window.setTimeout(function () {
      if (controller) controller.abort();
    }, 90000);
    try {
      var response = await fetch(path, Object.assign({}, config, {
        credentials: 'include',
        cache: 'no-store',
        signal: controller ? controller.signal : undefined,
        headers: Object.assign({ Accept: 'application/json' }, config.headers || {})
      }));
      var data = await response.json().catch(function () { return null; });
      if (response.status === 401) {
        window.location.replace('/owner-login');
        throw new Error('Owner session expired');
      }
      if (!response.ok) throw new Error(readableError(data || ('Request failed (' + response.status + ')')));
      return data;
    } catch (error) {
      if (error && error.name === 'AbortError') throw new Error('Import request timed out. File chhoti karke dobara try karein.');
      throw error;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function typeLabel(type) {
    return ({
      items: 'Items / Stock',
      parties: 'Customers & Suppliers',
      sales: 'Sale Invoices',
      purchases: 'Purchase Invoices'
    })[type] || type;
  }

  function detectType(headers, filename) {
    var file = String(filename || '').toLowerCase();
    if (file.indexOf('party') >= 0) return 'parties';
    if (file.indexOf('purchase') >= 0) return 'purchases';
    if (file.indexOf('sale') >= 0) return 'sales';
    if (file.indexOf('item') >= 0 || file.indexOf('stock') >= 0 || file.indexOf('product') >= 0) return 'items';
    var values = (headers || []).map(function (value) { return String(value || '').toLowerCase(); });
    function has() {
      var names = Array.prototype.slice.call(arguments);
      return names.some(function (name) { return values.indexOf(name) >= 0; });
    }
    if (has('invoice_no', 'invoice_number', 'bill_no', 'transaction_no')) {
      if (has('supplier_name', 'purchase_price', 'purchase_rate')) return 'purchases';
      return 'sales';
    }
    if (has('party_name', 'mobile_number', 'opening_balance', 'current_balance', 'gstin')) return 'parties';
    if (has('item_name', 'product_name', 'sale_price', 'purchase_price', 'current_stock', 'opening_stock')) return 'items';
    return '';
  }

  function injectStyle() {
    if (one('#owner-import-center-style')) return;
    var style = document.createElement('style');
    style.id = 'owner-import-center-style';
    style.textContent =
      '#page-import .import-hero{background:linear-gradient(145deg,#087fbf,#0da1d2);color:#fff;border:0}' +
      '#page-import .import-hero h2{margin:6px 0 4px;font-size:27px}#page-import .import-hero p{margin:0;opacity:.92}' +
      '.import-type-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:16px 0}' +
      '.import-type-grid button{border:1px solid #c8dce7;border-radius:14px;background:#fff;padding:14px 9px;font-weight:850;color:#304252}' +
      '.import-type-grid button.active{background:#e7f6ff;border-color:#0b88c4;color:#0879b1;box-shadow:0 0 0 2px rgba(11,136,196,.12)}' +
      '.import-file-box{display:grid;gap:9px;border:2px dashed #b9d3e2;border-radius:16px;background:#f7fbfe;padding:18px;text-align:center;cursor:pointer}' +
      '.import-file-box input{width:100%;font-size:15px}.import-file-box strong{font-size:17px}.import-file-box small{color:#71808c}' +
      '.import-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}.import-actions button{min-height:52px}' +
      '.import-result{margin-top:14px;border:1px solid #d6e4ec;border-radius:14px;padding:14px;background:#f9fcfe;white-space:normal}' +
      '.import-result.hidden{display:none}.import-result pre{overflow:auto;max-height:260px;background:#172533;color:#eef8ff;padding:11px;border-radius:10px;font-size:11px}' +
      '.import-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0}.import-metrics div{background:#fff;border:1px solid #dbe7ed;border-radius:11px;padding:10px;text-align:center}.import-metrics small{display:block;color:#75838f}.import-metrics b{font-size:18px}' +
      '.import-history-row{display:flex;justify-content:space-between;gap:12px;padding:12px 0;border-bottom:1px solid #e7edf1}.import-history-row:last-child{border-bottom:0}.import-history-row div{min-width:0}.import-history-row b,.import-history-row small{display:block}.import-history-row small{color:#75838f;margin-top:4px;overflow-wrap:anywhere}' +
      '.import-note{border-left:4px solid #0b88c4;background:#edf8fe;padding:12px 14px;border-radius:10px;margin-top:12px;color:#425666}' +
      '@media(min-width:800px){#page-import{max-width:920px;margin:0 auto}.import-type-grid{grid-template-columns:repeat(4,1fr)}}';
    document.head.appendChild(style);
  }

  function pageMarkup() {
    return '' +
      '<section id="page-import" class="page" data-page-name="import">' +
        '<div class="page-heading sticky-heading"><button class="back-button" type="button" data-import-back>‹</button><div><small>DATA MIGRATION</small><h1>Import Data</h1></div></div>' +
        '<article class="card import-hero"><small>VYAPAR / EXCEL / CSV</small><h2>Import Sale, Purchase & Items</h2><p>File ko pehle preview karein, phir safe import start karein.</p></article>' +
        '<article class="card form-card">' +
          '<label>What do you want to import?<select id="owner-import-type"><option value="items">Items / Stock</option><option value="sales">Sale Invoices</option><option value="purchases">Purchase Invoices</option><option value="parties">Customers & Suppliers</option></select></label>' +
          '<div class="import-type-grid"><button type="button" class="active" data-owner-import-type="items">📦 Items</button><button type="button" data-owner-import-type="sales">₹ Sale</button><button type="button" data-owner-import-type="purchases">🛒 Purchase</button><button type="button" data-owner-import-type="parties">👥 Parties</button></div>' +
          '<label class="import-file-box"><strong>Choose CSV or Excel file</strong><input id="owner-import-file" type="file" accept=".csv,.xlsx,.xlsm,.xls,.txt" /><small id="owner-import-file-name">CSV, XLSX, XLSM and XLS supported</small></label>' +
          '<div class="import-actions"><button class="secondary-wide" type="button" data-owner-import-preview>Preview File</button><button class="primary-wide" type="button" data-owner-import-start>Start Import</button></div>' +
          '<div id="owner-import-result" class="import-result hidden"></div>' +
          '<div class="import-note"><b>Recommended order:</b> Items → Parties → Sales/Purchases. Existing business data delete nahi hoga.</div>' +
        '</article>' +
        '<article class="card"><div class="card-title"><h2>Import History</h2><button class="text-button" type="button" data-owner-import-refresh>Refresh</button></div><div id="owner-import-history"><div class="empty-state">Open Import Data to load history.</div></div></article>' +
      '</section>';
  }

  function menuButtonMarkup() {
    return '<button type="button" data-import-open><span>⇪</span><div><b>Import Data</b><small>Import Items, Sales and Purchases</small></div><i>›</i></button>';
  }

  function ensureUi() {
    injectStyle();
    var main = one('.main-content');
    if (main && !one('#page-import')) main.insertAdjacentHTML('beforeend', pageMarkup());

    var menuList = one('#page-menu .menu-list');
    if (menuList && !one('#page-menu [data-import-open]')) {
      var settings = one('#page-menu [data-page="settings"]');
      if (settings) settings.insertAdjacentHTML('beforebegin', menuButtonMarkup());
      else menuList.insertAdjacentHTML('beforeend', menuButtonMarkup());
    }

    var settingsList = one('#page-settings .menu-list');
    if (settingsList && !one('#page-settings [data-import-open]')) {
      settingsList.insertAdjacentHTML('afterbegin', menuButtonMarkup());
    }
  }

  function activatePage(name) {
    var page = one('#page-' + name);
    if (!page) return;
    all('.page').forEach(function (node) { node.classList.toggle('active', node === page); });
    all('.bottom-nav button').forEach(function (button) {
      button.classList.toggle('active', button.getAttribute('data-page') === name);
    });
    window.scrollTo(0, 0);
    try { history.replaceState(null, '', '/?page=' + encodeURIComponent(name) + '&stable=124'); } catch (ignore) {}
    if (name === 'import') loadHistory();
  }

  function setType(type) {
    lastType = type;
    var select = one('#owner-import-type');
    if (select) select.value = type;
    all('[data-owner-import-type]').forEach(function (button) {
      button.classList.toggle('active', button.getAttribute('data-owner-import-type') === type);
    });
  }

  function setBusy(busy, message) {
    importing = busy;
    all('[data-owner-import-preview],[data-owner-import-start]').forEach(function (button) {
      button.disabled = busy;
    });
    var start = one('[data-owner-import-start]');
    if (start) start.textContent = busy ? (message || 'Working...') : 'Start Import';
  }

  function renderPreview(data, selected, detected) {
    var result = one('#owner-import-result');
    if (!result) return;
    var preview = (data.preview || []).slice(0, 8);
    result.classList.remove('hidden');
    result.innerHTML =
      '<b>Preview ready</b>' +
      '<div class="import-metrics"><div><small>Rows</small><b>' + Number(data.rows_total || 0) + '</b></div><div><small>Selected</small><b>' + esc(typeLabel(selected)) + '</b></div><div><small>Detected</small><b>' + esc(typeLabel(detected || selected)) + '</b></div></div>' +
      '<pre>' + esc(JSON.stringify(preview, null, 2)) + '</pre>';
  }

  function renderImportResult(data, selected) {
    var result = one('#owner-import-result');
    if (!result) return;
    var errors = data.errors || [];
    var firstError = errors.length ? readableError(errors[0] && (errors[0].error || errors[0])) : '';
    result.classList.remove('hidden');
    result.innerHTML =
      '<b>Import completed</b>' +
      '<div class="import-metrics"><div><small>Total</small><b>' + Number(data.rows_total || 0) + '</b></div><div><small>Imported</small><b>' + Number(data.rows_imported || 0) + '</b></div><div><small>Skipped</small><b>' + Number(data.rows_skipped || 0) + '</b></div></div>' +
      (firstError ? '<p style="color:#b1243d;white-space:pre-wrap">' + esc(firstError) + '</p>' : '') +
      '<button class="primary-wide" type="button" data-owner-import-reload>Reload ' + esc(typeLabel(selected)) + '</button>';
  }

  async function runImport(doImport) {
    if (importing) return;
    var fileInput = one('#owner-import-file');
    var file = fileInput && fileInput.files ? fileInput.files[0] : null;
    if (!file) return toast('Choose an Excel or CSV file first', true);
    var selected = one('#owner-import-type').value || 'items';
    setBusy(true, doImport ? 'Importing...' : 'Checking...');
    try {
      var previewForm = new FormData();
      previewForm.append('file', file);
      previewForm.append('entity_type', selected);
      previewForm.append('dry_run', 'true');
      var preview = await api('/api/import/vyapar', { method: 'POST', body: previewForm });
      var detected = detectType(preview.headers || [], file.name);
      if (detected && detected !== selected) {
        var result = one('#owner-import-result');
        result.classList.remove('hidden');
        result.innerHTML = '<b style="color:#b1243d">Wrong import type selected</b><p>This looks like <strong>' + esc(typeLabel(detected)) + '</strong>, but you selected <strong>' + esc(typeLabel(selected)) + '</strong>.</p><button class="secondary-wide" type="button" data-owner-import-switch="' + esc(detected) + '">Switch to ' + esc(typeLabel(detected)) + '</button>';
        return toast('Select ' + typeLabel(detected) + ' and try again', true);
      }
      if (!doImport) {
        renderPreview(preview, selected, detected);
        return;
      }

      var importForm = new FormData();
      importForm.append('file', file);
      importForm.append('entity_type', selected);
      importForm.append('dry_run', 'false');
      var imported = await api('/api/import/vyapar', { method: 'POST', body: importForm });
      renderImportResult(imported, selected);
      await loadHistory();
      toast(Number(imported.rows_imported || 0) + ' rows imported');
    } catch (error) {
      var box = one('#owner-import-result');
      if (box) {
        box.classList.remove('hidden');
        box.innerHTML = '<b style="color:#b1243d">Import failed</b><p style="white-space:pre-wrap">' + esc(error.message || error) + '</p>';
      }
      toast(error.message || 'Import failed', true);
    } finally {
      setBusy(false);
    }
  }

  async function loadHistory() {
    var host = one('#owner-import-history');
    if (!host) return;
    host.innerHTML = '<div class="empty-state">Loading import history...</div>';
    try {
      var rows = await api('/api/import/batches');
      if (!rows || !rows.length) {
        host.innerHTML = '<div class="empty-state">No imports yet</div>';
        return;
      }
      host.innerHTML = rows.slice(0, 30).map(function (row) {
        var firstError = row.errors && row.errors.length ? readableError(row.errors[0] && (row.errors[0].error || row.errors[0])) : '';
        return '<div class="import-history-row"><div><b>' + esc(typeLabel(row.entity_type)) + ' · ' + esc(row.filename || '') + '</b><small>' + esc(String(row.created_at || '').replace('T', ' ')) + (firstError ? ' · ' + esc(firstError) : '') + '</small></div><strong>' + Number(row.rows_imported || 0) + '/' + Number(row.rows_total || 0) + '</strong></div>';
      }).join('');
    } catch (error) {
      host.innerHTML = '<div class="empty-state">' + esc(error.message || 'History could not load') + '</div>';
    }
  }

  function reloadImportedData() {
    var page = lastType === 'items' ? 'items' : (lastType === 'parties' ? 'parties' : 'transactions');
    window.location.replace('/?page=' + encodeURIComponent(page) + '&imported=1&stable=124');
  }

  document.addEventListener('click', function (event) {
    var open = event.target.closest('[data-import-open]');
    var back = event.target.closest('[data-import-back]');
    var typeButton = event.target.closest('[data-owner-import-type]');
    var preview = event.target.closest('[data-owner-import-preview]');
    var start = event.target.closest('[data-owner-import-start]');
    var refresh = event.target.closest('[data-owner-import-refresh]');
    var reload = event.target.closest('[data-owner-import-reload]');
    var switchButton = event.target.closest('[data-owner-import-switch]');
    if (!open && !back && !typeButton && !preview && !start && !refresh && !reload && !switchButton) return;
    event.preventDefault();
    event.stopPropagation();
    if (open) return activatePage('import');
    if (back) return activatePage('menu');
    if (typeButton) return setType(typeButton.getAttribute('data-owner-import-type'));
    if (switchButton) return setType(switchButton.getAttribute('data-owner-import-switch'));
    if (preview) return runImport(false);
    if (start) return runImport(true);
    if (refresh) return loadHistory();
    if (reload) return reloadImportedData();
  }, true);

  document.addEventListener('change', function (event) {
    if (event.target && event.target.id === 'owner-import-type') setType(event.target.value);
    if (event.target && event.target.id === 'owner-import-file') {
      var file = event.target.files && event.target.files[0];
      var label = one('#owner-import-file-name');
      if (label) label.textContent = file ? (file.name + ' · ' + Math.max(1, Math.round(file.size / 1024)) + ' KB') : 'CSV, XLSX, XLSM and XLS supported';
    }
  }, true);

  function boot() {
    ensureUi();
    setType('items');
    var requested = new URLSearchParams(window.location.search).get('page');
    if (requested === 'import') activatePage('import');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
