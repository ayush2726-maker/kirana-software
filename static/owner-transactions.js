(function () {
  'use strict';

  var master = { items: [], parties: [], accounts: [] };
  var current = null;

  function one(selector, root) { return (root || document).querySelector(selector); }
  function all(selector, root) { return Array.prototype.slice.call((root || document).querySelectorAll(selector)); }
  function num(value) { var n = Number(value || 0); return Number.isFinite(n) ? n : 0; }
  function money(value) { return '₹' + num(value).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function today() { return new Date().toISOString().slice(0, 10); }
  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char];
    });
  }

  async function api(path, options) {
    var config = options || {};
    var headers = Object.assign({ Accept: 'application/json' }, config.headers || {});
    var body = config.body;
    if (body && !(body instanceof FormData) && typeof body !== 'string') {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }
    var response = await fetch(path, Object.assign({}, config, {
      body: body,
      headers: headers,
      credentials: 'include',
      cache: 'no-store'
    }));
    var data = response.status === 204 ? null : await response.json().catch(function () { return null; });
    if (response.status === 401) {
      window.location.replace('/owner-login');
      throw new Error('Your session expired. Please log in again.');
    }
    if (!response.ok) throw new Error(data && data.detail ? data.detail : 'Request failed (' + response.status + ')');
    return data;
  }

  function notify(message, isError) {
    var node = one('#txn-toast');
    if (!node) return;
    node.textContent = String(message || 'Done');
    node.className = 'txn-toast show' + (isError ? ' error' : '');
    clearTimeout(notify.timer);
    notify.timer = setTimeout(function () { node.className = 'txn-toast'; }, 3200);
  }

  function tile(action, icon, label, extra) {
    return '<button type="button" class="txn-tile" data-txn-action="' + esc(action) + '"' + (extra || '') + '><span class="txn-tile-icon">' + icon + '</span><b>' + esc(label) + '</b></button>';
  }

  function inject() {
    if (one('#txn-center')) return;

    var showAll = one('#page-home .quick-grid button:last-child');
    if (showAll) {
      showAll.removeAttribute('data-page');
      showAll.setAttribute('data-txn-action', 'open-center');
      var label = showAll.querySelector('b');
      if (label) label.textContent = 'All Txn';
    }

    var menu = one('#page-menu .menu-list');
    if (menu) {
      menu.insertAdjacentHTML('afterbegin', '<button type="button" data-txn-action="open-center"><span>▦</span><div><b>All Transactions</b><small>Purchase, payments, returns and more</small></div><i>›</i></button>');
    }

    document.body.insertAdjacentHTML('beforeend',
      '<section id="txn-center" class="txn-center hidden" aria-hidden="true">' +
        '<header class="txn-center-head"><h2>All Transactions</h2><button type="button" class="txn-close" data-txn-action="close-center">×</button></header>' +
        '<main class="txn-center-body">' +
          '<section class="txn-section"><h3>Sale Transactions</h3><div class="txn-grid">' +
            tile('payment-in', '⇩', 'Payment-In') +
            tile('sale-return', '↩', 'Sale Return') +
            tile('delivery-challan', '🚚', 'Delivery Challan') +
            tile('estimate', '🧮', 'Estimate / Quotation') +
            tile('proforma', '🧾', 'Proforma Invoice') +
            tile('sale-order', '📄', 'Sale Order') +
            tile('new-sale', '₹', 'Sale Invoice') +
            tile('new-sale', '▣', 'Mobile POS') +
            tile('sale-asset', '🏢', 'Sale Assets') +
          '</div></section>' +
          '<section class="txn-section"><h3>Purchase Transactions</h3><div class="txn-grid">' +
            tile('purchase', '🛒', 'Purchase') +
            tile('payment-out', '⇧', 'Payment-Out') +
            tile('purchase-return', '↪', 'Purchase Return') +
            tile('purchase-order', '🛍', 'Purchase Order') +
            tile('purchase-asset', '🏭', 'Purchase Assets') +
          '</div></section>' +
          '<section class="txn-section"><h3>Other Transactions</h3><div class="txn-grid">' +
            tile('expense', '👛', 'Expenses') +
            tile('transfer', '⇄', 'P2P Transfer') +
          '</div></section>' +
        '</main>' +
      '</section>' +
      '<section id="txn-form-screen" class="txn-form-screen hidden" aria-hidden="true"><header class="txn-form-head"><button type="button" class="txn-back" data-txn-action="back-center">‹</button><h2 id="txn-form-title">Transaction</h2><button type="button" class="txn-close" data-txn-action="close-form">×</button></header><main id="txn-form-body" class="txn-form-body"></main></section>' +
      '<div id="txn-toast" class="txn-toast"></div>'
    );
  }

  async function loadMaster() {
    var results = await Promise.all([
      api('/api/items?limit=2000'),
      api('/api/parties'),
      api('/api/accounts')
    ]);
    master.items = results[0] || [];
    master.parties = results[1] || [];
    master.accounts = results[2] || [];
  }

  function showCenter() {
    one('#txn-center').classList.remove('hidden');
    one('#txn-center').setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function hideCenter() {
    one('#txn-center').classList.add('hidden');
    one('#txn-center').setAttribute('aria-hidden', 'true');
    if (one('#txn-form-screen').classList.contains('hidden')) document.body.style.overflow = '';
  }

  function showForm(title, html) {
    one('#txn-form-title').textContent = title;
    one('#txn-form-body').innerHTML = html;
    one('#txn-form-screen').classList.remove('hidden');
    one('#txn-form-screen').setAttribute('aria-hidden', 'false');
    hideCenter();
    document.body.style.overflow = 'hidden';
    one('#txn-form-screen').scrollTop = 0;
  }

  function hideForm(openCenterAgain) {
    one('#txn-form-screen').classList.add('hidden');
    one('#txn-form-screen').setAttribute('aria-hidden', 'true');
    current = null;
    if (openCenterAgain) showCenter();
    else document.body.style.overflow = '';
  }

  function partyOptions(expected, allowEmpty) {
    var rows = master.parties.filter(function (party) {
      return !expected || party.type === expected || party.type === 'both';
    });
    var first = allowEmpty ? '<option value="">No Party / Cash</option>' : '<option value="">Select Party</option>';
    return first + rows.map(function (party) {
      return '<option value="' + Number(party.id) + '">' + esc(party.name) + (party.phone ? ' · ' + esc(party.phone) : '') + '</option>';
    }).join('');
  }

  function accountOptions(allowEmpty) {
    var first = allowEmpty ? '<option value="">Default Cash Account</option>' : '<option value="">Select Account</option>';
    return first + master.accounts.map(function (account) {
      return '<option value="' + Number(account.id) + '">' + esc(account.name) + ' (' + money(account.balance) + ')</option>';
    }).join('');
  }

  function billTitle(mode, kind) {
    if (mode === 'purchase') return 'New Purchase';
    return kind === 'sale_return' ? 'Sale Return' : 'Purchase Return';
  }

  async function openBill(mode, kind) {
    try {
      await loadMaster();
      current = { type: 'bill', mode: mode, kind: kind || '', cart: [] };
      var expected = mode === 'purchase' || kind === 'purchase_return' ? 'supplier' : 'customer';
      var priceLabel = mode === 'purchase' || kind === 'purchase_return' ? 'Purchase Rate' : 'Sale Rate';
      showForm(billTitle(mode, kind),
        '<div class="txn-kind-badge">' + esc(mode === 'purchase' ? 'PURCHASE' : String(kind || '').replace('_', ' ').toUpperCase()) + '</div>' +
        '<section class="txn-form-card">' +
          '<div class="txn-two"><label>' + (expected === 'supplier' ? 'Supplier' : 'Customer') + '<select id="txn-bill-party">' + partyOptions(expected, true) + '</select></label><label>Date<input id="txn-bill-date" type="date" value="' + today() + '"></label></div>' +
          '<label>' + (mode === 'purchase' ? 'Supplier Invoice / Reference' : 'Original Bill Reference') + '<input id="txn-bill-reference" autocomplete="off"></label>' +
          '<div class="txn-search-wrap"><label>Search Item<input id="txn-item-search" type="search" autocomplete="off" placeholder="Type product name, SKU or size"></label><div id="txn-item-results" class="txn-search-results hidden"></div></div>' +
          '<small style="color:#71818d">Items will use ' + priceLabel + ' by default. You can edit Qty, Rate and GST.</small>' +
        '</section>' +
        '<div id="txn-cart" class="txn-cart"></div>' +
        '<section class="txn-form-card txn-summary">' +
          '<div class="txn-summary-row"><span>Subtotal</span><strong id="txn-subtotal">₹0.00</strong></div>' +
          '<label class="txn-summary-row"><span>Discount</span><input id="txn-discount" type="number" min="0" step="0.01" value="0"></label>' +
          '<div class="txn-summary-row"><span>Tax</span><strong id="txn-tax">₹0.00</strong></div>' +
          '<div class="txn-summary-row txn-grand"><span>Total</span><strong id="txn-total">₹0.00</strong></div>' +
          '<div class="txn-two"><label>Payment Mode<select id="txn-payment-mode"><option value="credit">Credit</option><option value="cash">Cash</option><option value="upi">UPI</option><option value="bank">Bank</option><option value="card">Card</option></select></label><label>' + (mode === 'return' ? 'Refund Settled' : 'Paid Amount') + '<input id="txn-paid" type="number" min="0" step="0.01" value="0"></label></div>' +
          '<label>Notes<textarea id="txn-notes" rows="2" placeholder="Optional notes"></textarea></label>' +
          '<button id="txn-save-bill" type="button" class="txn-primary">Save ' + esc(billTitle(mode, kind)) + '</button>' +
        '</section>'
      );
      renderCart();
    } catch (error) { notify(error.message, true); }
  }

  function itemText(item) {
    return [item.name, item.size, item.sku, item.barcode, item.category].join(' ').toLowerCase();
  }

  function renderItemResults() {
    if (!current || current.type !== 'bill') return;
    var input = one('#txn-item-search');
    var box = one('#txn-item-results');
    var query = String(input.value || '').trim().toLowerCase();
    if (!query) {
      box.classList.add('hidden');
      box.innerHTML = '';
      return;
    }
    var rows = master.items.filter(function (item) { return itemText(item).indexOf(query) >= 0; }).slice(0, 30);
    if (!rows.length) box.innerHTML = '<div class="txn-empty">No item found</div>';
    else box.innerHTML = rows.map(function (item) {
      var price = current.mode === 'purchase' || current.kind === 'purchase_return' ? item.purchase_price : item.sale_price;
      return '<button type="button" class="txn-result" data-txn-add-item="' + Number(item.id) + '"><span><b>' + esc(item.name) + '</b><small>' + esc(item.size || item.unit || '') + ' · Stock ' + esc(item.stock) + '</small></span><strong>' + money(price) + '</strong></button>';
    }).join('');
    box.classList.remove('hidden');
  }

  function addItem(itemId) {
    if (!current || current.type !== 'bill') return;
    var item = master.items.find(function (row) { return Number(row.id) === Number(itemId); });
    if (!item) return;
    var existing = current.cart.find(function (line) { return Number(line.item_id) === Number(item.id); });
    if (existing) existing.qty += 1;
    else current.cart.push({
      item_id: Number(item.id),
      item_name: item.name,
      size: item.size || '',
      unit: item.unit || 'pcs',
      qty: 1,
      rate: num(current.mode === 'purchase' || current.kind === 'purchase_return' ? item.purchase_price : item.sale_price),
      gst_rate: num(item.gst_rate)
    });
    one('#txn-item-search').value = '';
    one('#txn-item-results').classList.add('hidden');
    renderCart();
  }

  function totals() {
    var subtotal = 0;
    var tax = 0;
    (current && current.cart || []).forEach(function (line) {
      var base = num(line.qty) * num(line.rate);
      subtotal += base;
      tax += base * num(line.gst_rate) / 100;
    });
    var discount = num(one('#txn-discount') && one('#txn-discount').value);
    return { subtotal: subtotal, tax: tax, discount: discount, total: Math.max(0, subtotal + tax - discount) };
  }

  function updateSummary() {
    if (!current || current.type !== 'bill') return;
    var sum = totals();
    one('#txn-subtotal').textContent = money(sum.subtotal);
    one('#txn-tax').textContent = money(sum.tax);
    one('#txn-total').textContent = money(sum.total);
    var mode = one('#txn-payment-mode').value;
    if (mode !== 'credit' && num(one('#txn-paid').value) === 0 && sum.total > 0) one('#txn-paid').value = sum.total.toFixed(2);
  }

  function renderCart() {
    var box = one('#txn-cart');
    if (!current.cart.length) box.innerHTML = '<div class="txn-empty">Search and add an item to continue.</div>';
    else box.innerHTML = current.cart.map(function (line, index) {
      var base = num(line.qty) * num(line.rate);
      var total = base + base * num(line.gst_rate) / 100;
      return '<article class="txn-line" data-txn-line-card="' + index + '"><div class="txn-line-head"><div><h4>' + esc(line.item_name) + '</h4><small>' + esc(line.size || line.unit || '') + '</small></div><button type="button" class="txn-remove" data-txn-remove-line="' + index + '">×</button></div>' +
        '<div class="txn-line-grid"><label>Qty<input data-txn-line="' + index + '" data-txn-field="qty" inputmode="decimal" type="number" min="0.001" step="0.001" value="' + num(line.qty) + '"></label><label>Rate<input data-txn-line="' + index + '" data-txn-field="rate" inputmode="decimal" type="number" min="0" step="0.01" value="' + num(line.rate) + '"></label><label>GST %<input data-txn-line="' + index + '" data-txn-field="gst_rate" inputmode="decimal" type="number" min="0" step="0.01" value="' + num(line.gst_rate) + '"></label></div>' +
        '<div class="txn-line-total"><span>Line Total</span><strong data-txn-line-total>' + money(total) + '</strong></div></article>';
    }).join('');
    updateSummary();
  }

  function updateLineWithoutRerender(input) {
    if (!current || current.type !== 'bill') return;
    var index = Number(input.getAttribute('data-txn-line'));
    var field = input.getAttribute('data-txn-field');
    var line = current.cart[index];
    if (!line || !field) return;
    line[field] = Math.max(field === 'qty' ? 0.001 : 0, num(input.value));
    var card = input.closest('[data-txn-line-card]');
    if (card) {
      var base = num(line.qty) * num(line.rate);
      var total = base + base * num(line.gst_rate) / 100;
      var node = one('[data-txn-line-total]', card);
      if (node) node.textContent = money(total);
    }
    updateSummary();
  }

  async function saveBill() {
    if (!current || !current.cart.length) return notify('Add at least one item', true);
    var sum = totals();
    var party = one('#txn-bill-party').value ? Number(one('#txn-bill-party').value) : null;
    var lines = current.cart.map(function (line) {
      return { item_id: line.item_id, item_name: line.item_name, size: line.size || '', qty: num(line.qty), rate: num(line.rate), gst_rate: num(line.gst_rate) };
    });
    var payload;
    var path;
    if (current.mode === 'purchase') {
      path = '/api/purchases';
      payload = {
        invoice_no: one('#txn-bill-reference').value || '',
        party_id: party,
        invoice_date: one('#txn-bill-date').value || today(),
        discount: sum.discount,
        paid: Math.min(num(one('#txn-paid').value), sum.total),
        payment_mode: one('#txn-payment-mode').value,
        notes: one('#txn-notes').value || '',
        items: lines
      };
    } else {
      path = '/api/returns';
      payload = {
        kind: current.kind,
        reference_no: one('#txn-bill-reference').value || '',
        party_id: party,
        return_date: one('#txn-bill-date').value || today(),
        discount: sum.discount,
        paid: Math.min(num(one('#txn-paid').value), sum.total),
        payment_mode: one('#txn-payment-mode').value,
        notes: one('#txn-notes').value || '',
        items: lines
      };
    }
    var button = one('#txn-save-bill');
    button.disabled = true;
    button.textContent = 'Saving...';
    try {
      await api(path, { method: 'POST', body: payload });
      notify(billTitle(current.mode, current.kind) + ' saved successfully');
      setTimeout(function () { window.location.replace('/?page=home&stable=102'); }, 500);
    } catch (error) {
      button.disabled = false;
      button.textContent = 'Save ' + billTitle(current.mode, current.kind);
      notify(error.message, true);
    }
  }

  async function openPayment(type) {
    try {
      await loadMaster();
      current = { type: 'payment', paymentType: type };
      var expected = type === 'received' ? 'customer' : 'supplier';
      var title = type === 'received' ? 'Payment-In' : 'Payment-Out';
      showForm(title,
        '<form id="txn-payment-form" class="txn-form-card">' +
          '<div class="txn-kind-badge">' + esc(title.toUpperCase()) + '</div>' +
          '<label>Party<select name="party_id" required>' + partyOptions(expected, false) + '</select></label>' +
          '<div class="txn-two"><label>Amount<input name="amount" type="number" inputmode="decimal" min="0.01" step="0.01" required></label><label>Date<input name="payment_date" type="date" value="' + today() + '" required></label></div>' +
          '<label>Mode<select name="mode"><option value="cash">Cash</option><option value="upi">UPI</option><option value="bank">Bank</option><option value="card">Card</option></select></label>' +
          '<label>Note<textarea name="note" rows="3"></textarea></label>' +
          '<button class="txn-primary" type="submit">Save ' + esc(title) + '</button>' +
        '</form>'
      );
    } catch (error) { notify(error.message, true); }
  }

  async function savePayment(form) {
    var data = Object.fromEntries(new FormData(form).entries());
    data.party_id = Number(data.party_id);
    data.amount = num(data.amount);
    data.payment_type = current.paymentType;
    var button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await api('/api/payments', { method: 'POST', body: data });
      notify((current.paymentType === 'received' ? 'Payment-In' : 'Payment-Out') + ' saved');
      setTimeout(function () { window.location.replace('/?page=home&stable=102'); }, 500);
    } catch (error) { button.disabled = false; notify(error.message, true); }
  }

  async function openEntry(type) {
    try {
      await loadMaster();
      current = { type: 'entry', entryType: type };
      var names = { expense: 'Expense', transfer: 'P2P Transfer', asset_purchase: 'Purchase Assets', asset_sale: 'Sale Assets' };
      var title = names[type] || 'Business Entry';
      var transfer = type === 'transfer';
      showForm(title,
        '<form id="txn-entry-form" class="txn-form-card">' +
          '<div class="txn-kind-badge">' + esc(title.toUpperCase()) + '</div>' +
          '<input type="hidden" name="entry_type" value="' + esc(type) + '">' +
          '<div class="txn-two"><label>Title<input name="title" value="' + esc(title) + '" required></label><label>Date<input name="entry_date" type="date" value="' + today() + '" required></label></div>' +
          '<label>Party (optional)<select name="party_id">' + partyOptions('', true) + '</select></label>' +
          '<label>From Account<select name="account_id">' + accountOptions(true) + '</select></label>' +
          (transfer ? '<label>To Account<select name="to_account_id" required>' + accountOptions(false) + '</select></label>' : '<input type="hidden" name="to_account_id" value="">') +
          '<div class="txn-two"><label>Amount<input name="amount" type="number" inputmode="decimal" min="0.01" step="0.01" required></label><label>Mode<select name="mode"><option value="cash">Cash</option><option value="upi">UPI</option><option value="bank">Bank</option><option value="card">Card</option></select></label></div>' +
          '<input type="hidden" name="status" value="completed">' +
          '<label>Note<textarea name="note" rows="3"></textarea></label>' +
          '<button class="txn-primary" type="submit">Save ' + esc(title) + '</button>' +
        '</form>'
      );
    } catch (error) { notify(error.message, true); }
  }

  async function saveEntry(form) {
    var data = Object.fromEntries(new FormData(form).entries());
    data.party_id = data.party_id ? Number(data.party_id) : null;
    data.account_id = data.account_id ? Number(data.account_id) : null;
    data.to_account_id = data.to_account_id ? Number(data.to_account_id) : null;
    data.amount = num(data.amount);
    var button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await api('/api/entries', { method: 'POST', body: data });
      notify('Transaction saved');
      setTimeout(function () { window.location.replace('/?page=home&stable=102'); }, 500);
    } catch (error) { button.disabled = false; notify(error.message, true); }
  }

  async function openDocument(kind) {
    try {
      await loadMaster();
      current = { type: 'document', kind: kind };
      var names = { delivery_challan: 'Delivery Challan', estimate: 'Estimate / Quotation', proforma: 'Proforma Invoice', sale_order: 'Sale Order', purchase_order: 'Purchase Order' };
      var title = names[kind] || 'Document';
      showForm(title,
        '<form id="txn-document-form" class="txn-form-card">' +
          '<div class="txn-kind-badge">' + esc(title.toUpperCase()) + '</div>' +
          '<input type="hidden" name="kind" value="' + esc(kind) + '">' +
          '<div class="txn-two"><label>Document Number<input name="doc_no" placeholder="Auto if blank"></label><label>Date<input name="doc_date" type="date" value="' + today() + '" required></label></div>' +
          '<label>Party<select name="party_id">' + partyOptions('', true) + '</select></label>' +
          '<div class="txn-two"><label>Amount<input name="amount" type="number" inputmode="decimal" min="0" step="0.01" value="0"></label><label>Status<select name="status"><option value="open">Open</option><option value="confirmed">Confirmed</option><option value="closed">Closed</option><option value="cancelled">Cancelled</option></select></label></div>' +
          '<label>Note<textarea name="note" rows="4"></textarea></label>' +
          '<button class="txn-primary" type="submit">Save ' + esc(title) + '</button>' +
        '</form>'
      );
    } catch (error) { notify(error.message, true); }
  }

  async function saveDocument(form) {
    var data = Object.fromEntries(new FormData(form).entries());
    data.party_id = data.party_id ? Number(data.party_id) : null;
    data.amount = num(data.amount);
    var button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await api('/api/documents', { method: 'POST', body: data });
      notify('Document saved');
      setTimeout(function () { window.location.replace('/?page=home&stable=102'); }, 500);
    } catch (error) { button.disabled = false; notify(error.message, true); }
  }

  function openSalePage() {
    hideCenter();
    var button = one('[data-page="sale"]');
    if (button) button.click();
    else window.location.replace('/?page=sale&stable=102');
  }

  function routeAction(action) {
    if (action === 'open-center') return showCenter();
    if (action === 'close-center') return hideCenter();
    if (action === 'back-center') return hideForm(true);
    if (action === 'close-form') return hideForm(false);
    if (action === 'new-sale') return openSalePage();
    if (action === 'purchase') return openBill('purchase', '');
    if (action === 'sale-return') return openBill('return', 'sale_return');
    if (action === 'purchase-return') return openBill('return', 'purchase_return');
    if (action === 'payment-in') return openPayment('received');
    if (action === 'payment-out') return openPayment('paid');
    if (action === 'expense') return openEntry('expense');
    if (action === 'transfer') return openEntry('transfer');
    if (action === 'purchase-asset') return openEntry('asset_purchase');
    if (action === 'sale-asset') return openEntry('asset_sale');
    if (action === 'delivery-challan') return openDocument('delivery_challan');
    if (action === 'estimate') return openDocument('estimate');
    if (action === 'proforma') return openDocument('proforma');
    if (action === 'sale-order') return openDocument('sale_order');
    if (action === 'purchase-order') return openDocument('purchase_order');
  }

  function bind() {
    document.addEventListener('click', function (event) {
      var actionNode = event.target.closest('[data-txn-action]');
      if (actionNode) {
        event.preventDefault();
        event.stopPropagation();
        routeAction(actionNode.getAttribute('data-txn-action'));
        return;
      }
      var add = event.target.closest('[data-txn-add-item]');
      if (add) {
        event.preventDefault();
        addItem(Number(add.getAttribute('data-txn-add-item')));
        return;
      }
      var remove = event.target.closest('[data-txn-remove-line]');
      if (remove && current && current.type === 'bill') {
        current.cart.splice(Number(remove.getAttribute('data-txn-remove-line')), 1);
        renderCart();
      }
      if (event.target === one('#txn-center')) hideCenter();
    }, true);

    document.addEventListener('input', function (event) {
      if (event.target.id === 'txn-item-search') renderItemResults();
      if (event.target.hasAttribute('data-txn-line')) updateLineWithoutRerender(event.target);
      if (event.target.id === 'txn-discount') updateSummary();
    }, true);

    document.addEventListener('change', function (event) {
      if (event.target.id === 'txn-payment-mode' && current && current.type === 'bill') {
        if (event.target.value === 'credit') one('#txn-paid').value = 0;
        else one('#txn-paid').value = totals().total.toFixed(2);
      }
    }, true);

    document.addEventListener('click', function (event) {
      if (event.target.id === 'txn-save-bill') saveBill();
    });

    document.addEventListener('submit', function (event) {
      if (event.target.id === 'txn-payment-form') { event.preventDefault(); savePayment(event.target); }
      if (event.target.id === 'txn-entry-form') { event.preventDefault(); saveEntry(event.target); }
      if (event.target.id === 'txn-document-form') { event.preventDefault(); saveDocument(event.target); }
    });
  }

  inject();
  bind();
})();
