(function () {
  'use strict';

  if (window.__kiranaItemBillOpenLoaded) return;
  window.__kiranaItemBillOpenLoaded = true;

  var cache = new Map();
  var activeBill = null;
  var editState = null;
  var decorating = false;
  var saving = false;

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

  function num(value) {
    var parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function money(value) {
    return '₹ ' + num(value).toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function dateLabel(value) {
    var text = String(value || '').slice(0, 10);
    var parts = text.split('-');
    return parts.length === 3 ? parts[2] + '/' + parts[1] + '/' + parts[0] : text;
  }

  function kindLabel(kind) {
    return ({
      sale: 'Sale Invoice',
      purchase: 'Purchase Bill',
      sale_return: 'Sale Return',
      purchase_return: 'Purchase Return'
    })[String(kind || '')] || String(kind || 'Transaction').replace(/_/g, ' ');
  }

  function numberLabel(kind) {
    return String(kind || '').indexOf('return') >= 0 ? 'Return No.' : 'Bill No.';
  }

  function expectedPartyLabel(kind) {
    return ['sale', 'sale_return'].indexOf(String(kind || '')) >= 0 ? 'Customer' : 'Supplier';
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

  async function api(path, options) {
    var config = options || {};
    var headers = Object.assign({ Accept: 'application/json' }, config.headers || {});
    var body = config.body;
    if (body && typeof body !== 'string' && !(body instanceof FormData)) {
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
    if (one('#item-bill-open-style')) return;
    var style = document.createElement('style');
    style.id = 'item-bill-open-style';
    style.textContent =
      '.item-history-row.item-history-openable{cursor:pointer;touch-action:manipulation;position:relative;padding-right:34px}' +
      '.item-history-row.item-history-openable:active{background:#eef7fc}' +
      '.item-history-row.item-history-openable:after{content:"›";position:absolute;right:12px;top:50%;transform:translateY(-50%);font-size:29px;color:#82919c}' +
      '.item-bill-overlay,.item-bill-edit-overlay{position:fixed;inset:0;background:#f3f7fa;overflow:auto;color:#1f2d39}' +
      '.item-bill-overlay{z-index:4800}.item-bill-edit-overlay{z-index:4900}' +
      '.item-bill-overlay.hidden,.item-bill-edit-overlay.hidden{display:none!important}' +
      '.item-bill-head,.item-bill-edit-head{position:sticky;top:0;z-index:2;background:#fff;border-bottom:1px solid #dce5ea;padding:calc(10px + env(safe-area-inset-top)) 14px 10px;display:grid;grid-template-columns:48px minmax(0,1fr) auto;align-items:center;gap:8px}' +
      '.item-bill-head h1,.item-bill-edit-head h1{margin:0;font-size:23px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' +
      '.item-bill-head button,.item-bill-edit-head button{height:46px;border:0;border-radius:50%;background:transparent;font-size:29px;color:#087fbd}.item-bill-head button:active,.item-bill-edit-head button:active{background:#edf5f9}' +
      '.item-bill-head>button:first-child,.item-bill-edit-head>button:first-child{width:46px}' +
      '.item-bill-actions{display:flex;align-items:center;justify-content:flex-end}.item-bill-actions button{width:44px}' +
      '.item-bill-edit-head .item-bill-save-top{width:auto;border-radius:12px;background:#0b82c2;color:#fff;font-size:15px;font-weight:900;padding:0 15px}' +
      '.item-bill-body{padding:16px 14px calc(28px + env(safe-area-inset-bottom));display:grid;gap:13px}' +
      '.item-bill-card{background:#fff;border:1px solid #dce5ea;border-radius:17px;padding:16px;box-shadow:0 7px 20px rgba(30,75,100,.09)}' +
      '.item-bill-title{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}.item-bill-title h2{margin:0;font-size:21px}.item-bill-title small{display:block;margin-top:5px;color:#74818c}.item-bill-title strong{font-size:20px;white-space:nowrap}' +
      '.item-bill-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:14px}.item-bill-grid div{background:#f3f7fa;border-radius:11px;padding:10px}.item-bill-grid small{display:block;color:#75818b}.item-bill-grid b{display:block;margin-top:3px}' +
      '.item-bill-line{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;padding:12px 0;border-bottom:1px solid #edf1f4}.item-bill-line:last-child{border-bottom:0}.item-bill-line small{display:block;color:#74818c;margin-top:4px}.item-bill-line strong{white-space:nowrap}' +
      '.item-bill-loading,.item-bill-error{text-align:center;padding:52px 18px;color:#74818c;font-weight:800}.item-bill-error{color:#cc3f5d}.item-bill-retry{display:block;margin:16px auto 0;border:0;border-radius:12px;background:#0b82c2;color:#fff;padding:11px 20px;font-weight:850}' +
      '.item-bill-edit-body{padding:14px 12px calc(100px + env(safe-area-inset-bottom));display:grid;gap:12px}.item-bill-edit-card{background:#fff;border:1px solid #dce5ea;border-radius:17px;padding:14px;box-shadow:0 6px 18px rgba(30,75,100,.08)}' +
      '.item-bill-edit-card h3{margin:0 0 12px;font-size:18px}.item-bill-edit-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.item-bill-edit-card label{display:grid;gap:6px;color:#667480;font-size:12px;font-weight:800}.item-bill-edit-card input,.item-bill-edit-card select,.item-bill-edit-card textarea{width:100%;border:1px solid #cbd9e2;border-radius:11px;background:#fff;color:#20303c;padding:11px;font:inherit;font-size:15px}.item-bill-edit-card input:focus,.item-bill-edit-card select:focus,.item-bill-edit-card textarea:focus{outline:2px solid rgba(11,130,194,.18);border-color:#0b82c2}' +
      '.item-bill-edit-line{border:1px solid #dbe5eb;border-radius:14px;padding:12px;margin-top:10px;background:#fbfdfe}.item-bill-edit-line-head{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.item-bill-edit-line-head b{display:block}.item-bill-edit-line-head small{display:block;margin-top:3px;color:#788590}.item-bill-remove-line{width:36px;height:36px;border:0;border-radius:50%;background:#fff0f3;color:#c93556;font-size:23px}.item-bill-line-fields{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}' +
      '.item-bill-search-wrap{position:relative;margin-top:12px}.item-bill-search-results{position:absolute;left:0;right:0;top:100%;z-index:4;max-height:290px;overflow:auto;background:#fff;border:1px solid #cbd9e2;border-radius:12px;box-shadow:0 12px 28px rgba(20,55,75,.18)}.item-bill-search-results.hidden{display:none}.item-bill-search-result{width:100%;border:0;border-bottom:1px solid #edf1f4;background:#fff;padding:12px;display:flex;justify-content:space-between;gap:10px;text-align:left;color:inherit}.item-bill-search-result:last-child{border-bottom:0}.item-bill-search-result small{display:block;color:#788590;margin-top:3px}.item-bill-search-result strong{white-space:nowrap;color:#087fbd}' +
      '.item-bill-edit-summary{display:grid;gap:8px}.item-bill-edit-summary-row{display:flex;justify-content:space-between;gap:15px}.item-bill-edit-summary-row.grand{border-top:2px solid #253642;padding-top:10px;font-size:20px}.item-bill-linked-note{margin-top:10px;border-radius:10px;background:#fff7df;color:#7a5d00;padding:10px;font-size:12px;font-weight:800}' +
      '.item-bill-save-bottom{position:fixed;z-index:5;left:14px;right:14px;bottom:calc(14px + env(safe-area-inset-bottom));border:0;border-radius:16px;background:#0b82c2;color:#fff;padding:15px;font-size:18px;font-weight:900;box-shadow:0 10px 28px rgba(11,130,194,.34)}.item-bill-save-bottom:disabled,.item-bill-save-top:disabled{opacity:.6}' +
      '@media(max-width:430px){.item-bill-edit-grid{grid-template-columns:1fr}.item-bill-line-fields{grid-template-columns:1fr 1fr 1fr}.item-bill-edit-card input,.item-bill-edit-card select{padding:10px 8px}}' +
      '@media(min-width:760px){.item-bill-overlay,.item-bill-edit-overlay{left:50%;right:auto;width:min(720px,100%);transform:translateX(-50%);box-shadow:0 0 45px rgba(20,50,70,.22)}.item-bill-save-bottom{left:50%;right:auto;width:min(680px,calc(100% - 40px));transform:translateX(-50%)}}';
    document.head.appendChild(style);
  }

  function ensureOverlay() {
    var overlay = one('#item-bill-overlay');
    if (overlay) return overlay;
    overlay = document.createElement('section');
    overlay.id = 'item-bill-overlay';
    overlay.className = 'item-bill-overlay hidden';
    overlay.setAttribute('aria-hidden', 'true');
    overlay.innerHTML =
      '<header class="item-bill-head">' +
        '<button type="button" data-close-item-bill aria-label="Back">←</button>' +
        '<h1 id="item-bill-heading">Bill Details</h1>' +
        '<div class="item-bill-actions"><button type="button" data-edit-item-bill aria-label="Edit bill">✎</button><button type="button" data-print-item-bill aria-label="Print bill">🖨</button></div>' +
      '</header>' +
      '<main id="item-bill-body" class="item-bill-body"></main>';
    document.body.appendChild(overlay);
    return overlay;
  }

  function ensureEditOverlay() {
    var overlay = one('#item-bill-edit-overlay');
    if (overlay) return overlay;
    overlay = document.createElement('section');
    overlay.id = 'item-bill-edit-overlay';
    overlay.className = 'item-bill-edit-overlay hidden';
    overlay.setAttribute('aria-hidden', 'true');
    overlay.innerHTML =
      '<header class="item-bill-edit-head">' +
        '<button type="button" data-close-item-bill-edit aria-label="Back">←</button>' +
        '<h1>Edit Bill</h1>' +
        '<button type="button" class="item-bill-save-top" data-save-item-bill>Save</button>' +
      '</header>' +
      '<main id="item-bill-edit-body" class="item-bill-edit-body"></main>' +
      '<button type="button" class="item-bill-save-bottom" data-save-item-bill>Save Changes</button>';
    document.body.appendChild(overlay);
    return overlay;
  }

  function showOverlay() {
    var overlay = ensureOverlay();
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    overlay.scrollTop = 0;
    document.body.style.overflow = 'hidden';
  }

  function closeOverlay() {
    var overlay = one('#item-bill-overlay');
    if (!overlay) return;
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
    activeBill = null;
    document.body.style.overflow = 'hidden';
  }

  function showEditOverlay() {
    var overlay = ensureEditOverlay();
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    overlay.scrollTop = 0;
    document.body.style.overflow = 'hidden';
  }

  function closeEditOverlay() {
    var overlay = one('#item-bill-edit-overlay');
    if (!overlay) return;
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
    editState = null;
    saving = false;
    document.body.style.overflow = 'hidden';
  }

  function itemLine(item) {
    return '<div class="item-bill-line"><div><b>' + esc(item.item_name || 'Item') + '</b><small>' +
      esc(item.size || '') + (item.size ? ' · ' : '') + 'Qty ' + esc(item.qty) + ' × ' + money(item.rate) +
      (num(item.gst_rate) ? ' · GST ' + esc(item.gst_rate) + '%' : '') +
      '</small></div><strong>' + money(item.line_total) + '</strong></div>';
  }

  function renderBill(detail) {
    var overlay = ensureOverlay();
    var title = kindLabel(detail.kind);
    var items = Array.isArray(detail.items) ? detail.items : [];
    if (activeBill) activeBill.detail = detail;
    one('#item-bill-heading', overlay).textContent = title;
    one('#item-bill-body', overlay).innerHTML =
      '<section class="item-bill-card"><div class="item-bill-title"><div><h2>' + esc(detail.party_name || detail.title || 'Cash Customer') + '</h2><small>' +
        esc(detail.number || detail.reference || '') + (detail.date ? ' · ' + dateLabel(detail.date) : '') +
        '</small></div><strong>' + money(detail.total) + '</strong></div>' +
        '<div class="item-bill-grid">' +
          '<div><small>Subtotal</small><b>' + money(detail.subtotal) + '</b></div>' +
          '<div><small>Tax</small><b>' + money(detail.tax) + '</b></div>' +
          '<div><small>Discount</small><b>' + money(detail.discount) + '</b></div>' +
          '<div><small>Paid</small><b>' + money(detail.paid) + '</b></div>' +
          '<div><small>Due</small><b>' + money(detail.due) + '</b></div>' +
          '<div><small>Payment Mode</small><b>' + esc(detail.payment_mode || '—') + '</b></div>' +
        '</div></section>' +
      (items.length ? '<section class="item-bill-card"><h3>Items</h3>' + items.map(itemLine).join('') + '</section>' : '') +
      (detail.notes ? '<section class="item-bill-card"><h3>Notes</h3><div>' + esc(detail.notes) + '</div></section>' : '');
  }

  async function openBill(kind, transactionId) {
    kind = String(kind || '');
    transactionId = Number(transactionId || 0);
    if (!kind || !transactionId) return;
    activeBill = { kind: kind, id: transactionId, detail: null };
    var overlay = ensureOverlay();
    one('#item-bill-heading', overlay).textContent = kindLabel(kind);
    one('#item-bill-body', overlay).innerHTML = '<div class="item-bill-loading">Loading bill details...</div>';
    showOverlay();
    try {
      var detail = await api('/api/transaction-detail/' + encodeURIComponent(kind) + '/' + transactionId);
      if (activeBill && activeBill.kind === kind && activeBill.id === transactionId) renderBill(detail);
    } catch (error) {
      if (!activeBill) return;
      one('#item-bill-body', overlay).innerHTML = '<div class="item-bill-error">Bill could not be opened.<button type="button" class="item-bill-retry" data-retry-item-bill>Retry</button></div>';
      toast(error.message || 'Bill could not be opened', true);
    }
  }

  function partyOptions(data) {
    var bill = data.bill || {};
    var options = '<option value="">Cash / No Party</option>';
    (data.parties || []).forEach(function (party) {
      options += '<option value="' + Number(party.id) + '"' + (Number(party.id) === Number(bill.party_id) ? ' selected' : '') + '>' + esc(party.name) + (party.phone ? ' · ' + esc(party.phone) : '') + '</option>';
    });
    return options;
  }

  function paymentOptions(value) {
    return ['cash', 'credit', 'upi', 'bank', 'card', 'cheque'].map(function (mode) {
      return '<option value="' + mode + '"' + (String(value || '').toLowerCase() === mode ? ' selected' : '') + '>' + mode.toUpperCase() + '</option>';
    }).join('');
  }

  function editLineMarkup(line, index) {
    return '<article class="item-bill-edit-line" data-edit-line-card="' + index + '">' +
      '<div class="item-bill-edit-line-head"><div><b>' + esc(line.item_name || 'Item') + '</b><small>' + esc(line.size || line.unit || '') + '</small></div><button type="button" class="item-bill-remove-line" data-remove-edit-line="' + index + '">×</button></div>' +
      '<div class="item-bill-line-fields">' +
        '<label>Qty<input type="number" min="0.001" step="0.001" data-edit-line-index="' + index + '" data-edit-line-field="qty" value="' + esc(line.qty) + '"></label>' +
        '<label>Rate<input type="number" min="0" step="0.01" data-edit-line-index="' + index + '" data-edit-line-field="rate" value="' + esc(line.rate) + '"></label>' +
        '<label>GST %<input type="number" min="0" step="0.01" data-edit-line-index="' + index + '" data-edit-line-field="gst_rate" value="' + esc(line.gst_rate) + '"></label>' +
      '</div>' +
    '</article>';
  }

  function renderEditLines() {
    if (!editState) return;
    var box = one('#item-bill-edit-lines');
    if (!box) return;
    if (!editState.lines.length) box.innerHTML = '<div class="item-bill-loading">At least one item is required.</div>';
    else box.innerHTML = editState.lines.map(editLineMarkup).join('');
    updateEditTotals();
  }

  function editTotals() {
    var subtotal = 0;
    var tax = 0;
    (editState && editState.lines || []).forEach(function (line) {
      var base = num(line.qty) * num(line.rate);
      subtotal += base;
      tax += base * num(line.gst_rate) / 100;
    });
    var discount = num(one('#item-bill-edit-discount') && one('#item-bill-edit-discount').value);
    var total = Math.max(0, subtotal + tax - discount);
    var initialPaid = num(one('#item-bill-edit-paid') && one('#item-bill-edit-paid').value);
    var allocated = num(editState && editState.bill && editState.bill.allocated_paid);
    var paid = Math.min(total, initialPaid + allocated);
    return { subtotal: subtotal, tax: tax, discount: discount, total: total, paid: paid, due: Math.max(0, total - paid), allocated: allocated };
  }

  function updateEditTotals() {
    var totals = editTotals();
    var values = {
      '#item-bill-edit-subtotal': money(totals.subtotal),
      '#item-bill-edit-tax': money(totals.tax),
      '#item-bill-edit-total': money(totals.total),
      '#item-bill-edit-total-paid': money(totals.paid),
      '#item-bill-edit-due': money(totals.due)
    };
    Object.keys(values).forEach(function (selector) {
      var node = one(selector);
      if (node) node.textContent = values[selector];
    });
  }

  function renderEdit(data) {
    editState = {
      kind: activeBill.kind,
      id: activeBill.id,
      bill: data.bill || {},
      parties: data.parties || [],
      items: data.items || [],
      partyLocked: Boolean(data.party_locked),
      lines: (data.bill && data.bill.items || []).map(function (line) {
        return {
          item_id: line.item_id ? Number(line.item_id) : null,
          item_name: line.item_name || 'Item',
          size: line.size || '',
          unit: line.unit || '',
          qty: num(line.qty),
          rate: num(line.rate),
          gst_rate: num(line.gst_rate)
        };
      })
    };
    var bill = editState.bill;
    var isReturn = String(editState.kind).indexOf('return') >= 0;
    var linked = num(bill.allocated_paid);
    one('#item-bill-edit-body').innerHTML =
      '<section class="item-bill-edit-card"><h3>Bill Information</h3><div class="item-bill-edit-grid">' +
        '<label>' + esc(numberLabel(editState.kind)) + '<input id="item-bill-edit-number" value="' + esc(bill.number || bill.reference || '') + '"></label>' +
        '<label>Date<input id="item-bill-edit-date" type="date" value="' + esc(String(bill.date || '').slice(0, 10)) + '"></label>' +
        '<label>' + esc(expectedPartyLabel(editState.kind)) + '<select id="item-bill-edit-party"' + (editState.partyLocked ? ' disabled' : '') + '>' + partyOptions(data) + '</select></label>' +
        '<label>Payment Mode<select id="item-bill-edit-mode">' + paymentOptions(bill.payment_mode) + '</select></label>' +
        (isReturn ? '<label>Original Bill Reference<input id="item-bill-edit-reference" value="' + esc(bill.reference || '') + '"></label>' : '') +
      '</div>' +
      (editState.partyLocked ? '<div class="item-bill-linked-note">Linked payment laga hua hai, isliye party lock rahegi.</div>' : '') +
      '</section>' +
      '<section class="item-bill-edit-card"><h3>Items</h3><div id="item-bill-edit-lines"></div>' +
        '<div class="item-bill-search-wrap"><label>Add Item<input id="item-bill-add-search" type="search" autocomplete="off" placeholder="Product name, size or SKU"></label><div id="item-bill-search-results" class="item-bill-search-results hidden"></div></div>' +
      '</section>' +
      '<section class="item-bill-edit-card"><h3>Amounts</h3><div class="item-bill-edit-grid">' +
        '<label>Discount<input id="item-bill-edit-discount" type="number" min="0" step="0.01" value="' + esc(bill.discount || 0) + '"></label>' +
        '<label>Paid at Bill<input id="item-bill-edit-paid" type="number" min="0" step="0.01" value="' + esc(bill.initial_paid || 0) + '"></label>' +
      '</div>' +
      (linked ? '<div class="item-bill-linked-note">Linked payment ' + money(linked) + ' सुरक्षित रहेगा और edit में नहीं हटेगा.</div>' : '') +
      '<div class="item-bill-edit-summary" style="margin-top:14px">' +
        '<div class="item-bill-edit-summary-row"><span>Subtotal</span><b id="item-bill-edit-subtotal">₹ 0.00</b></div>' +
        '<div class="item-bill-edit-summary-row"><span>Tax</span><b id="item-bill-edit-tax">₹ 0.00</b></div>' +
        '<div class="item-bill-edit-summary-row grand"><span>Total</span><b id="item-bill-edit-total">₹ 0.00</b></div>' +
        '<div class="item-bill-edit-summary-row"><span>Total Paid</span><b id="item-bill-edit-total-paid">₹ 0.00</b></div>' +
        '<div class="item-bill-edit-summary-row"><span>Due</span><b id="item-bill-edit-due">₹ 0.00</b></div>' +
      '</div></section>' +
      '<section class="item-bill-edit-card"><label>Notes<textarea id="item-bill-edit-notes" rows="3">' + esc(bill.notes || '') + '</textarea></label></section>';
    renderEditLines();
  }

  async function openEdit() {
    if (!activeBill) return;
    var overlay = ensureEditOverlay();
    one('#item-bill-edit-body', overlay).innerHTML = '<div class="item-bill-loading">Loading bill for editing...</div>';
    showEditOverlay();
    try {
      var data = await api('/api/bill-edit/' + encodeURIComponent(activeBill.kind) + '/' + activeBill.id);
      if (!activeBill) return;
      renderEdit(data);
    } catch (error) {
      one('#item-bill-edit-body', overlay).innerHTML = '<div class="item-bill-error">' + esc(error.message || 'Bill edit could not load') + '</div>';
      toast(error.message || 'Bill edit could not load', true);
    }
  }

  function renderItemSearch() {
    if (!editState) return;
    var input = one('#item-bill-add-search');
    var box = one('#item-bill-search-results');
    if (!input || !box) return;
    var query = String(input.value || '').trim().toLowerCase();
    if (!query) {
      box.classList.add('hidden');
      box.innerHTML = '';
      return;
    }
    var rows = editState.items.filter(function (item) {
      return [item.name, item.size, item.unit, item.sku].join(' ').toLowerCase().indexOf(query) >= 0;
    }).slice(0, 35);
    if (!rows.length) box.innerHTML = '<div class="item-bill-loading">No item found</div>';
    else box.innerHTML = rows.map(function (item) {
      var price = ['sale', 'sale_return'].indexOf(editState.kind) >= 0 ? item.sale_price : item.purchase_price;
      return '<button type="button" class="item-bill-search-result" data-add-edit-item="' + Number(item.id) + '"><span><b>' + esc(item.name) + '</b><small>' + esc(item.size || item.unit || '') + ' · Stock ' + esc(item.stock) + '</small></span><strong>' + money(price) + '</strong></button>';
    }).join('');
    box.classList.remove('hidden');
  }

  function addEditItem(itemId) {
    if (!editState) return;
    var item = editState.items.find(function (row) { return Number(row.id) === Number(itemId); });
    if (!item) return;
    var existing = editState.lines.find(function (line) { return Number(line.item_id) === Number(item.id); });
    if (existing) existing.qty = num(existing.qty) + 1;
    else editState.lines.push({
      item_id: Number(item.id),
      item_name: item.name,
      size: item.size || '',
      unit: item.unit || '',
      qty: 1,
      rate: num(['sale', 'sale_return'].indexOf(editState.kind) >= 0 ? item.sale_price : item.purchase_price),
      gst_rate: num(item.gst_rate)
    });
    one('#item-bill-add-search').value = '';
    one('#item-bill-search-results').classList.add('hidden');
    renderEditLines();
  }

  function setSaving(on) {
    saving = on;
    all('[data-save-item-bill]').forEach(function (button) {
      button.disabled = on;
      button.textContent = on ? 'Saving...' : (button.classList.contains('item-bill-save-top') ? 'Save' : 'Save Changes');
    });
  }

  async function saveEdit() {
    if (!editState || saving) return;
    if (!editState.lines.length) return toast('Bill me kam se kam ek item hona chahiye', true);
    var partySelect = one('#item-bill-edit-party');
    var payload = {
      number: String(one('#item-bill-edit-number').value || '').trim(),
      party_id: partySelect && partySelect.value ? Number(partySelect.value) : (editState.partyLocked ? (editState.bill.party_id || null) : null),
      date: one('#item-bill-edit-date').value,
      reference_no: one('#item-bill-edit-reference') ? one('#item-bill-edit-reference').value : '',
      discount: num(one('#item-bill-edit-discount').value),
      initial_paid: num(one('#item-bill-edit-paid').value),
      payment_mode: one('#item-bill-edit-mode').value,
      notes: one('#item-bill-edit-notes').value,
      items: editState.lines.map(function (line) {
        return {
          item_id: line.item_id || null,
          item_name: line.item_name || 'Item',
          size: line.size || '',
          qty: Math.max(0.001, num(line.qty)),
          rate: Math.max(0, num(line.rate)),
          gst_rate: Math.max(0, num(line.gst_rate))
        };
      })
    };
    if (!payload.date) return toast('Bill date select karein', true);
    setSaving(true);
    try {
      var data = await api('/api/bill-edit/' + encodeURIComponent(editState.kind) + '/' + editState.id, {
        method: 'PUT',
        body: payload
      });
      cache.clear();
      closeEditOverlay();
      if (data && data.bill) renderBill(data.bill);
      var historyOverlay = one('#item-history-overlay');
      var historyEdit = historyOverlay && one('[data-item-history-edit]', historyOverlay);
      var itemId = Number(historyEdit && historyEdit.getAttribute('data-id') || 0);
      if (itemId && window.KiranaItemHistory && typeof window.KiranaItemHistory.open === 'function') {
        window.KiranaItemHistory.open(itemId);
      }
      toast('Bill updated successfully');
    } catch (error) {
      toast(error.message || 'Bill update nahi hua', true);
    } finally {
      setSaving(false);
    }
  }

  async function historyFor(itemId) {
    itemId = Number(itemId || 0);
    if (!itemId) return null;
    if (cache.has(itemId)) return cache.get(itemId);
    var promise = api('/api/item-history/' + itemId).catch(function (error) {
      cache.delete(itemId);
      throw error;
    });
    cache.set(itemId, promise);
    return promise;
  }

  async function decorateRows() {
    if (decorating) return;
    var overlay = one('#item-history-overlay');
    if (!overlay || overlay.classList.contains('hidden')) return;
    var rows = all('.item-history-row', overlay);
    if (!rows.length) return;
    var edit = one('[data-item-history-edit]', overlay);
    var itemId = Number(edit && edit.getAttribute('data-id') || 0);
    if (!itemId) return;
    decorating = true;
    try {
      var data = await historyFor(itemId);
      var transactions = data && Array.isArray(data.transactions) ? data.transactions : [];
      rows.forEach(function (row, index) {
        var transaction = transactions[index];
        row.setAttribute('data-item-history-index', String(index));
        if (transaction && transaction.transaction_id && ['sale', 'purchase', 'sale_return', 'purchase_return'].indexOf(String(transaction.kind)) >= 0) {
          row.classList.add('item-history-openable');
          row.setAttribute('aria-label', 'Open ' + kindLabel(transaction.kind));
        } else {
          row.classList.remove('item-history-openable');
        }
      });
    } catch (error) {
      console.error('Item bill row decoration failed', error);
    } finally {
      decorating = false;
    }
  }

  async function openRow(row) {
    var overlay = one('#item-history-overlay');
    var edit = overlay && one('[data-item-history-edit]', overlay);
    var itemId = Number(edit && edit.getAttribute('data-id') || 0);
    var index = Number(row.getAttribute('data-item-history-index'));
    if (!Number.isInteger(index) || index < 0) index = all('.item-history-row', overlay).indexOf(row);
    try {
      var data = await historyFor(itemId);
      var transaction = data && data.transactions ? data.transactions[index] : null;
      if (!transaction || !transaction.transaction_id) {
        toast('This is a stock adjustment. No bill is attached.', true);
        return;
      }
      openBill(transaction.kind, transaction.transaction_id);
    } catch (error) {
      toast(error.message || 'Bill could not be opened', true);
    }
  }

  document.addEventListener('input', function (event) {
    if (event.target && event.target.id === 'item-bill-add-search') {
      renderItemSearch();
      return;
    }
    var index = event.target.getAttribute && event.target.getAttribute('data-edit-line-index');
    var field = event.target.getAttribute && event.target.getAttribute('data-edit-line-field');
    if (editState && index != null && field && editState.lines[Number(index)]) {
      editState.lines[Number(index)][field] = num(event.target.value);
      updateEditTotals();
      return;
    }
    if (event.target && ['item-bill-edit-discount', 'item-bill-edit-paid'].indexOf(event.target.id) >= 0) updateEditTotals();
  }, true);

  document.addEventListener('click', function (event) {
    var closeEdit = event.target.closest('[data-close-item-bill-edit]');
    if (closeEdit) {
      event.preventDefault();
      event.stopPropagation();
      closeEditOverlay();
      return;
    }

    var save = event.target.closest('[data-save-item-bill]');
    if (save) {
      event.preventDefault();
      saveEdit();
      return;
    }

    var remove = event.target.closest('[data-remove-edit-line]');
    if (remove && editState) {
      event.preventDefault();
      editState.lines.splice(Number(remove.getAttribute('data-remove-edit-line')), 1);
      renderEditLines();
      return;
    }

    var add = event.target.closest('[data-add-edit-item]');
    if (add) {
      event.preventDefault();
      addEditItem(Number(add.getAttribute('data-add-edit-item')));
      return;
    }

    var editBill = event.target.closest('[data-edit-item-bill]');
    if (editBill) {
      event.preventDefault();
      openEdit();
      return;
    }

    var close = event.target.closest('[data-close-item-bill]');
    if (close) {
      event.preventDefault();
      event.stopPropagation();
      closeOverlay();
      return;
    }

    var retry = event.target.closest('[data-retry-item-bill]');
    if (retry && activeBill) {
      event.preventDefault();
      openBill(activeBill.kind, activeBill.id);
      return;
    }

    var print = event.target.closest('[data-print-item-bill]');
    if (print) {
      event.preventDefault();
      if (!activeBill) return;
      location.assign('/owner/bulk-print?items=' + encodeURIComponent(activeBill.kind + ':' + activeBill.id));
      return;
    }

    var row = event.target.closest('#item-history-overlay .item-history-row');
    if (!row) return;
    event.preventDefault();
    event.stopPropagation();
    openRow(row);
  }, true);

  function scheduleDecorate() {
    window.clearTimeout(scheduleDecorate.timer);
    scheduleDecorate.timer = window.setTimeout(decorateRows, 80);
  }

  function boot() {
    injectStyle();
    ensureOverlay();
    ensureEditOverlay();
    if (typeof MutationObserver !== 'undefined') {
      new MutationObserver(scheduleDecorate).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'data-id'] });
    }
    document.addEventListener('click', scheduleDecorate, true);
    [400, 1000, 2200].forEach(function (delay) { window.setTimeout(scheduleDecorate, delay); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
