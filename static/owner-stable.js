(function () {
  'use strict';

  var state = {
    me: null,
    dashboard: null,
    activity: [],
    items: [],
    parties: [],
    orders: [],
    saleLines: [],
    itemFilter: 'all',
    partyFilter: 'all',
    transactionFilter: 'all'
  };

  function one(selector, root) {
    return (root || document).querySelector(selector);
  }

  function all(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function money(value) {
    return '₹' + Number(value || 0).toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function number(value) {
    var parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char];
    });
  }

  function today() {
    return new Date().toISOString().slice(0, 10);
  }

  function toast(message, isError) {
    var node = one('#toast');
    if (!node) return;
    node.textContent = String(message || 'Done');
    node.className = 'toast show' + (isError ? ' error' : '');
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(function () {
      node.className = 'toast';
    }, 3200);
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
    if (!response.ok) {
      throw new Error(data && data.detail ? data.detail : 'Request failed (' + response.status + ')');
    }
    return data;
  }

  function setText(selector, value) {
    var node = one(selector);
    if (node) node.textContent = value;
  }

  function showEmpty(container, message) {
    container.innerHTML = '<div class="empty-state">' + escapeHtml(message) + '</div>';
  }

  function navigate(pageName) {
    var page = one('#page-' + pageName);
    if (!page) return;
    all('.page').forEach(function (node) {
      node.classList.toggle('active', node === page);
    });
    all('.bottom-nav button').forEach(function (button) {
      button.classList.toggle('active', button.getAttribute('data-page') === pageName);
    });
    window.scrollTo(0, 0);
    try {
      history.replaceState(null, '', '/?page=' + encodeURIComponent(pageName) + '&stable=100');
    } catch (ignore) {}

    if (pageName === 'dashboard') loadDashboard();
    if (pageName === 'home') loadActivity();
    if (pageName === 'items') renderItems();
    if (pageName === 'parties') renderParties();
    if (pageName === 'transactions') renderTransactions();
    if (pageName === 'orders') loadOrders();
    if (pageName === 'settings') fillBusinessForm();
    if (pageName === 'sale') prepareSalePage();
  }

  async function boot() {
    bindEvents();
    try {
      state.me = await api('/api/me');
      var business = state.me.business || {};
      setText('#business-name', business.name || 'Kirana Software');
      setText('#business-subtitle', business.phone || 'Billing, Inventory & Accounts');
      setText('#profile-button', String(business.owner_name || business.name || 'A').charAt(0).toUpperCase());
      fillBusinessForm();
      one('#customer-link').value = window.location.origin + '/customer';
      one('#sale-date').value = today();

      one('#app').classList.remove('hidden');
      one('#app-loading').classList.add('hidden');

      await loadCoreData();
      var requested = new URLSearchParams(window.location.search).get('page');
      navigate(one('#page-' + requested) ? requested : 'home');
    } catch (error) {
      one('#app-loading').innerHTML = '<div class="loading-logo">K</div><strong>App could not start</strong><span>' + escapeHtml(error.message) + '</span><button id="retry-boot" class="primary-small">Retry</button>';
      one('#retry-boot').addEventListener('click', function () { window.location.reload(); });
    }
  }

  async function loadCoreData() {
    var results = await Promise.allSettled([
      api('/api/items?limit=2000'),
      api('/api/parties'),
      api('/api/activity?limit=150'),
      api('/api/dashboard')
    ]);

    if (results[0].status === 'fulfilled') state.items = results[0].value || [];
    if (results[1].status === 'fulfilled') state.parties = results[1].value || [];
    if (results[2].status === 'fulfilled') state.activity = results[2].value || [];
    if (results[3].status === 'fulfilled') state.dashboard = results[3].value || {};

    results.forEach(function (result) {
      if (result.status === 'rejected') console.error(result.reason);
    });

    fillSalePartyOptions();
    renderItems();
    renderParties();
    renderActivity();
    renderDashboard();
  }

  async function loadActivity() {
    try {
      state.activity = await api('/api/activity?limit=150');
      renderActivity();
      renderTransactions();
    } catch (error) {
      toast(error.message, true);
    }
  }

  function activityDate(row) {
    return row.entry_date || row.invoice_date || row.created_at || '';
  }

  function activityTitle(row) {
    return row.title || row.party_name || row.ref || row.invoice_no || 'Transaction';
  }

  function activityReference(row) {
    return row.ref || row.invoice_no || row.kind || '';
  }

  function activityAmount(row) {
    return row.amount != null ? row.amount : row.total;
  }

  function transactionCard(row) {
    var kind = String(row.kind || 'transaction').toLowerCase();
    return '<article class="transaction-card">' +
      '<div class="row-top"><div><h3>' + escapeHtml(activityTitle(row)) + '</h3><small>' + escapeHtml(activityReference(row)) + ' · ' + escapeHtml(activityDate(row)) + '</small></div><strong>' + money(activityAmount(row)) + '</strong></div>' +
      '<span class="status-pill ' + escapeHtml(kind) + '">' + escapeHtml(kind.replace(/_/g, ' ').toUpperCase()) + '</span>' +
      '</article>';
  }

  function renderActivity() {
    var container = one('#activity-list');
    if (!container) return;
    var query = String(one('#activity-search').value || '').trim().toLowerCase();
    var rows = state.activity.filter(function (row) {
      return !query || (activityTitle(row) + ' ' + activityReference(row)).toLowerCase().indexOf(query) >= 0;
    }).slice(0, 50);
    if (!rows.length) return showEmpty(container, 'No transactions found');
    container.innerHTML = rows.map(transactionCard).join('');
  }

  function renderTransactions() {
    var container = one('#transactions-list');
    if (!container) return;
    var query = String(one('#transaction-search').value || '').trim().toLowerCase();
    var rows = state.activity.filter(function (row) {
      var matchesKind = state.transactionFilter === 'all' || String(row.kind || '') === state.transactionFilter;
      var matchesText = !query || (activityTitle(row) + ' ' + activityReference(row)).toLowerCase().indexOf(query) >= 0;
      return matchesKind && matchesText;
    });
    if (!rows.length) return showEmpty(container, 'No matching transactions');
    container.innerHTML = rows.map(transactionCard).join('');
  }

  async function loadDashboard() {
    try {
      state.dashboard = await api('/api/dashboard');
      renderDashboard();
    } catch (error) {
      toast(error.message, true);
    }
  }

  function renderDashboard() {
    var data = state.dashboard || {};
    setText('#dash-receivable', money(data.receivable));
    setText('#dash-payable', money(data.payable));
    setText('#dash-sales', money(data.sales_month));
    setText('#dash-purchases', money(data.purchases_month));
    setText('#dash-cash', money(data.cash_balance));
    setText('#dash-stock', money(data.stock_value));

    var activity = one('#dashboard-activity');
    var activityRows = (data.activity || []).slice(0, 8);
    if (!activityRows.length) showEmpty(activity, 'No recent activity');
    else activity.innerHTML = activityRows.map(function (row) {
      return '<div class="compact-row"><div><b>' + escapeHtml(activityTitle(row)) + '</b><small>' + escapeHtml(activityReference(row)) + '</small></div><strong>' + money(activityAmount(row)) + '</strong></div>';
    }).join('');

    var low = one('#dashboard-low-stock');
    var lowRows = data.low_items || [];
    if (!lowRows.length) showEmpty(low, 'No low-stock items');
    else low.innerHTML = lowRows.map(function (item) {
      return '<div class="compact-row"><div><b>' + escapeHtml(item.name) + '</b><small>Minimum ' + escapeHtml(item.min_stock) + ' ' + escapeHtml(item.unit) + '</small></div><strong>' + escapeHtml(item.stock) + '</strong></div>';
    }).join('');
  }

  function itemText(item) {
    return [item.name, item.size, item.sku, item.category].join(' ').toLowerCase();
  }

  function renderItems() {
    var container = one('#items-list');
    if (!container) return;
    var query = String(one('#item-search').value || '').trim().toLowerCase();
    var rows = state.items.filter(function (item) {
      var matchesText = !query || itemText(item).indexOf(query) >= 0;
      var matchesFilter = state.itemFilter !== 'low' || number(item.stock) <= number(item.min_stock);
      return matchesText && matchesFilter;
    });
    if (!rows.length) return showEmpty(container, 'No items found');
    container.innerHTML = rows.map(function (item) {
      var low = number(item.stock) <= number(item.min_stock);
      return '<article class="item-card"><div class="row-top"><div><h3>' + escapeHtml(item.name) + '</h3><small>' + escapeHtml(item.size || item.unit || '') + ' · ' + escapeHtml(item.sku || '') + '</small></div><strong>' + money(item.sale_price) + '</strong></div>' +
        '<span class="status-pill ' + (low ? 'cancelled' : 'sale') + '">Stock ' + escapeHtml(item.stock) + ' ' + escapeHtml(item.unit || '') + '</span>' +
        '<div class="row-actions"><button data-action="edit-item" data-id="' + Number(item.id) + '">Edit Item</button></div></article>';
    }).join('');
  }

  function partyText(party) {
    return [party.name, party.phone, party.gstin, party.type].join(' ').toLowerCase();
  }

  function renderParties() {
    var container = one('#parties-list');
    if (!container) return;
    var query = String(one('#party-search').value || '').trim().toLowerCase();
    var rows = state.parties.filter(function (party) {
      var type = String(party.type || 'customer');
      var matchesType = state.partyFilter === 'all' || type === state.partyFilter || type === 'both';
      return matchesType && (!query || partyText(party).indexOf(query) >= 0);
    });
    if (!rows.length) return showEmpty(container, 'No parties found');
    container.innerHTML = rows.map(function (party) {
      return '<article class="party-card"><div class="row-top"><div><h3>' + escapeHtml(party.name) + '</h3><small>' + escapeHtml(party.phone || party.type || '') + '</small></div><strong>' + money(party.balance) + '</strong></div>' +
        '<span class="status-pill">' + escapeHtml(String(party.type || 'customer').toUpperCase()) + '</span>' +
        '<div class="row-actions"><button data-action="edit-party" data-id="' + Number(party.id) + '">Edit Party</button></div></article>';
    }).join('');
  }

  function openModal(name) {
    one('#modal-backdrop').classList.remove('hidden');
    all('.modal').forEach(function (node) { node.classList.add('hidden'); });
    one('#' + name + '-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    one('#modal-backdrop').classList.add('hidden');
    all('.modal').forEach(function (node) { node.classList.add('hidden'); });
    document.body.style.overflow = '';
  }

  function openItemModal(item) {
    var form = one('#item-form');
    form.reset();
    form.elements.id.value = item ? item.id : '';
    ['name', 'size', 'unit', 'sku', 'category', 'sale_price', 'purchase_price', 'stock', 'min_stock', 'gst_rate', 'mrp', 'barcode', 'hsn'].forEach(function (key) {
      if (form.elements[key]) form.elements[key].value = item && item[key] != null ? item[key] : (['sale_price', 'purchase_price', 'stock', 'min_stock', 'gst_rate', 'mrp'].indexOf(key) >= 0 ? 0 : '');
    });
    setText('#item-modal-title', item ? 'Edit Item' : 'Add Item');
    openModal('item');
  }

  function openPartyModal(party) {
    var form = one('#party-form');
    form.reset();
    form.elements.id.value = party ? party.id : '';
    ['name', 'type', 'phone', 'opening_balance', 'gstin', 'address'].forEach(function (key) {
      if (form.elements[key]) form.elements[key].value = party && party[key] != null ? party[key] : (key === 'opening_balance' ? 0 : (key === 'type' ? 'customer' : ''));
    });
    setText('#party-modal-title', party ? 'Edit Party' : 'Add Party');
    openModal('party');
  }

  async function saveItem(event) {
    event.preventDefault();
    var form = event.currentTarget;
    var data = Object.fromEntries(new FormData(form).entries());
    var id = data.id;
    delete data.id;
    ['gst_rate', 'purchase_price', 'sale_price', 'mrp', 'stock', 'min_stock'].forEach(function (key) { data[key] = number(data[key]); });
    try {
      var saved = await api(id ? '/api/items/' + id : '/api/items', { method: id ? 'PUT' : 'POST', body: data });
      var index = state.items.findIndex(function (item) { return Number(item.id) === Number(saved.id); });
      if (index >= 0) state.items[index] = saved; else state.items.push(saved);
      state.items.sort(function (a, b) { return String(a.name).localeCompare(String(b.name)); });
      closeModal();
      renderItems();
      toast(id ? 'Item updated' : 'Item added');
    } catch (error) {
      toast(error.message, true);
    }
  }

  async function saveParty(event) {
    event.preventDefault();
    var form = event.currentTarget;
    var data = Object.fromEntries(new FormData(form).entries());
    var id = data.id;
    delete data.id;
    data.opening_balance = number(data.opening_balance);
    try {
      var saved = await api(id ? '/api/parties/' + id : '/api/parties', { method: id ? 'PUT' : 'POST', body: data });
      var index = state.parties.findIndex(function (party) { return Number(party.id) === Number(saved.id); });
      if (index >= 0) state.parties[index] = saved; else state.parties.push(saved);
      state.parties.sort(function (a, b) { return String(a.name).localeCompare(String(b.name)); });
      fillSalePartyOptions();
      closeModal();
      renderParties();
      toast(id ? 'Party updated' : 'Party added');
    } catch (error) {
      toast(error.message, true);
    }
  }

  function fillSalePartyOptions() {
    var select = one('#sale-party');
    if (!select) return;
    var current = select.value;
    select.innerHTML = '<option value="">Cash / Walk-in Customer</option>' + state.parties.filter(function (party) {
      return party.type === 'customer' || party.type === 'both';
    }).map(function (party) {
      return '<option value="' + Number(party.id) + '">' + escapeHtml(party.name) + '</option>';
    }).join('');
    select.value = current;
  }

  function prepareSalePage() {
    if (!one('#sale-date').value) one('#sale-date').value = today();
    fillSalePartyOptions();
    renderSaleLines();
  }

  function clearSale() {
    state.saleLines = [];
    one('#sale-party').value = '';
    one('#sale-item-search').value = '';
    one('#sale-discount').value = 0;
    one('#sale-paid').value = 0;
    one('#sale-payment-mode').value = 'cash';
    one('#sale-notes').value = '';
    one('#sale-date').value = today();
    one('#sale-item-results').classList.add('hidden');
    renderSaleLines();
  }

  function renderSaleSearch() {
    var box = one('#sale-item-results');
    var query = String(one('#sale-item-search').value || '').trim().toLowerCase();
    if (!query) {
      box.classList.add('hidden');
      box.innerHTML = '';
      return;
    }
    var rows = state.items.filter(function (item) { return itemText(item).indexOf(query) >= 0; }).slice(0, 25);
    if (!rows.length) box.innerHTML = '<div class="empty-state">No item found</div>';
    else box.innerHTML = rows.map(function (item) {
      return '<button type="button" class="search-result" data-action="add-sale-item" data-id="' + Number(item.id) + '"><div><b>' + escapeHtml(item.name) + '</b><small>' + escapeHtml(item.size || item.unit || '') + ' · Stock ' + escapeHtml(item.stock) + '</small></div><strong>' + money(item.sale_price) + '</strong></button>';
    }).join('');
    box.classList.remove('hidden');
  }

  function addSaleItem(itemId) {
    var item = state.items.find(function (row) { return Number(row.id) === Number(itemId); });
    if (!item) return;
    var existing = state.saleLines.find(function (line) { return Number(line.item_id) === Number(item.id); });
    if (existing) existing.qty += 1;
    else state.saleLines.push({
      item_id: item.id,
      item_name: item.name,
      size: item.size || '',
      qty: 1,
      rate: number(item.sale_price),
      gst_rate: number(item.gst_rate)
    });
    one('#sale-item-search').value = '';
    one('#sale-item-results').classList.add('hidden');
    renderSaleLines();
  }

  function saleTotals() {
    var subtotal = 0;
    var tax = 0;
    state.saleLines.forEach(function (line) {
      var lineSubtotal = number(line.qty) * number(line.rate);
      subtotal += lineSubtotal;
      tax += lineSubtotal * number(line.gst_rate) / 100;
    });
    var discount = number(one('#sale-discount').value);
    return { subtotal: subtotal, tax: tax, discount: discount, total: Math.max(0, subtotal + tax - discount) };
  }

  function renderSaleLines() {
    var container = one('#sale-lines');
    if (!state.saleLines.length) {
      showEmpty(container, 'No items added. Search an item above to start billing.');
    } else {
      container.innerHTML = state.saleLines.map(function (line, index) {
        var lineSubtotal = number(line.qty) * number(line.rate);
        var lineTax = lineSubtotal * number(line.gst_rate) / 100;
        return '<article class="sale-line"><div class="sale-line-head"><div><h3>' + escapeHtml(line.item_name) + '</h3><small>' + escapeHtml(line.size || '') + '</small></div><button type="button" data-action="remove-sale-line" data-index="' + index + '">×</button></div>' +
          '<div class="sale-line-grid"><label>Qty<input data-sale-index="' + index + '" data-sale-field="qty" type="number" min="0.01" step="0.01" value="' + number(line.qty) + '" /></label><label>Rate<input data-sale-index="' + index + '" data-sale-field="rate" type="number" min="0" step="0.01" value="' + number(line.rate) + '" /></label><label>GST %<input data-sale-index="' + index + '" data-sale-field="gst_rate" type="number" min="0" step="0.01" value="' + number(line.gst_rate) + '" /></label></div>' +
          '<div class="sale-line-total"><span>Line Total</span><strong>' + money(lineSubtotal + lineTax) + '</strong></div></article>';
      }).join('');
    }
    var totals = saleTotals();
    setText('#sale-subtotal', money(totals.subtotal));
    setText('#sale-tax', money(totals.tax));
    setText('#sale-total', money(totals.total));
    if (one('#sale-payment-mode').value !== 'credit' && number(one('#sale-paid').value) === 0 && totals.total > 0) {
      one('#sale-paid').value = totals.total.toFixed(2);
    }
  }

  async function saveSale() {
    if (!state.saleLines.length) return toast('Add at least one item', true);
    var totals = saleTotals();
    var payload = {
      party_id: one('#sale-party').value ? Number(one('#sale-party').value) : null,
      invoice_date: one('#sale-date').value || today(),
      discount: totals.discount,
      paid: Math.min(number(one('#sale-paid').value), totals.total),
      payment_mode: one('#sale-payment-mode').value,
      notes: one('#sale-notes').value || '',
      items: state.saleLines.map(function (line) {
        return {
          item_id: Number(line.item_id),
          item_name: line.item_name,
          size: line.size || '',
          qty: number(line.qty),
          rate: number(line.rate),
          gst_rate: number(line.gst_rate)
        };
      })
    };
    var button = one('#save-sale');
    button.disabled = true;
    button.textContent = 'Saving Sale...';
    try {
      var sale = await api('/api/sales', { method: 'POST', body: payload });
      toast('Sale ' + (sale.invoice_no || '') + ' saved successfully');
      clearSale();
      await loadCoreData();
      navigate('home');
    } catch (error) {
      toast(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = 'Save Sale';
    }
  }

  async function loadOrders() {
    var container = one('#orders-list');
    if (!container) return;
    try {
      state.orders = await api('/api/orders?limit=200');
      renderOrders();
    } catch (error) {
      showEmpty(container, error.message);
    }
  }

  function renderOrders() {
    var container = one('#orders-list');
    if (!state.orders.length) return showEmpty(container, 'No customer orders');
    container.innerHTML = state.orders.map(function (order) {
      var items = (order.items || []).map(function (line) {
        return '<div class="compact-row"><span>' + escapeHtml(line.item_name) + ' × ' + escapeHtml(line.qty) + '</span><strong>' + money(line.line_total) + '</strong></div>';
      }).join('');
      var disabled = order.status === 'converted' || order.status === 'cancelled';
      return '<article class="order-card"><div class="row-top"><div><h3>' + escapeHtml(order.party_name || 'Customer') + '</h3><small>' + escapeHtml(order.order_no || '') + ' · ' + escapeHtml(order.order_date || '') + '</small></div><strong>' + money(order.total) + '</strong></div><span class="status-pill ' + escapeHtml(order.status || '') + '">' + escapeHtml(String(order.status || 'pending').toUpperCase()) + '</span><div class="compact-list">' + items + '</div><div class="row-actions"><select data-order-status="' + Number(order.id) + '" ' + (order.status === 'converted' ? 'disabled' : '') + '><option value="pending">Pending</option><option value="confirmed">Confirmed</option><option value="processing">Processing</option><option value="dispatched">Dispatched</option><option value="delivered">Delivered</option><option value="cancelled">Cancelled</option></select><button data-action="convert-order" data-id="' + Number(order.id) + '" ' + (disabled ? 'disabled' : '') + '>Create Bill</button></div></article>';
    }).join('');
    all('[data-order-status]', container).forEach(function (select) {
      var order = state.orders.find(function (row) { return Number(row.id) === Number(select.getAttribute('data-order-status')); });
      if (order) select.value = order.status;
    });
  }

  async function updateOrderStatus(id, status) {
    try {
      await api('/api/orders/' + id + '/status', { method: 'PUT', body: { status: status } });
      await loadOrders();
      toast('Order status updated');
    } catch (error) {
      toast(error.message, true);
    }
  }

  async function convertOrder(id) {
    try {
      var result = await api('/api/orders/' + id + '/convert-to-sale', { method: 'POST' });
      await Promise.all([loadOrders(), loadActivity(), loadDashboard()]);
      toast('Bill ' + ((result.sale && result.sale.invoice_no) || '') + ' created');
    } catch (error) {
      toast(error.message, true);
    }
  }

  function fillBusinessForm() {
    if (!state.me || !state.me.business) return;
    var form = one('#business-form');
    var business = state.me.business;
    ['name', 'owner_name', 'phone', 'gstin', 'address', 'invoice_prefix'].forEach(function (key) {
      if (form.elements[key]) form.elements[key].value = business[key] == null ? '' : business[key];
    });
  }

  async function saveBusiness(event) {
    event.preventDefault();
    var data = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      var business = await api('/api/business', { method: 'PUT', body: data });
      state.me.business = business;
      setText('#business-name', business.name || 'Kirana Software');
      setText('#business-subtitle', business.phone || 'Billing, Inventory & Accounts');
      toast('Business settings saved');
    } catch (error) {
      toast(error.message, true);
    }
  }

  async function logout() {
    try { await api('/api/logout', { method: 'POST' }); } catch (ignore) {}
    window.location.replace('/owner-login');
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    var area = document.createElement('textarea');
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    area.remove();
    return Promise.resolve();
  }

  function bindEvents() {
    document.addEventListener('click', function (event) {
      var pageButton = event.target.closest('[data-page]');
      if (pageButton) {
        event.preventDefault();
        navigate(pageButton.getAttribute('data-page'));
        return;
      }

      var actionButton = event.target.closest('[data-action]');
      if (!actionButton) return;
      var action = actionButton.getAttribute('data-action');
      var id = Number(actionButton.getAttribute('data-id') || 0);
      event.preventDefault();

      if (action === 'home') navigate('home');
      if (action === 'refresh-dashboard') loadDashboard();
      if (action === 'new-item') openItemModal(null);
      if (action === 'edit-item') openItemModal(state.items.find(function (item) { return Number(item.id) === id; }));
      if (action === 'new-party') openPartyModal(null);
      if (action === 'edit-party') openPartyModal(state.parties.find(function (party) { return Number(party.id) === id; }));
      if (action === 'close-modal') closeModal();
      if (action === 'clear-sale') clearSale();
      if (action === 'add-sale-item') addSaleItem(id);
      if (action === 'remove-sale-line') {
        state.saleLines.splice(Number(actionButton.getAttribute('data-index')), 1);
        renderSaleLines();
      }
      if (action === 'refresh-orders') loadOrders();
      if (action === 'convert-order') convertOrder(id);
      if (action === 'copy-customer-link') {
        copyText(one('#customer-link').value).then(function () { toast('Customer link copied'); });
      }
      if (action === 'open-customer-link') window.location.href = '/customer';
      if (action === 'logout') logout();
    }, false);

    one('#modal-backdrop').addEventListener('click', function (event) {
      if (event.target === event.currentTarget) closeModal();
    });

    one('#activity-search').addEventListener('input', renderActivity);
    one('#item-search').addEventListener('input', renderItems);
    one('#party-search').addEventListener('input', renderParties);
    one('#transaction-search').addEventListener('input', renderTransactions);
    one('#sale-item-search').addEventListener('input', renderSaleSearch);
    one('#sale-item-search').addEventListener('focus', renderSaleSearch);
    one('#sale-discount').addEventListener('input', renderSaleLines);
    one('#sale-payment-mode').addEventListener('change', function () {
      if (this.value === 'credit') one('#sale-paid').value = 0;
      else one('#sale-paid').value = saleTotals().total.toFixed(2);
    });

    document.addEventListener('input', function (event) {
      var index = event.target.getAttribute('data-sale-index');
      var field = event.target.getAttribute('data-sale-field');
      if (index == null || !field || !state.saleLines[Number(index)]) return;
      state.saleLines[Number(index)][field] = Math.max(field === 'qty' ? 0.01 : 0, number(event.target.value));
      renderSaleLines();
    });

    document.addEventListener('change', function (event) {
      var orderId = event.target.getAttribute('data-order-status');
      if (orderId) updateOrderStatus(Number(orderId), event.target.value);
    });

    all('[data-item-filter]').forEach(function (button) {
      button.addEventListener('click', function () {
        state.itemFilter = button.getAttribute('data-item-filter');
        all('[data-item-filter]').forEach(function (node) { node.classList.toggle('active', node === button); });
        renderItems();
      });
    });

    all('[data-party-filter]').forEach(function (button) {
      button.addEventListener('click', function () {
        state.partyFilter = button.getAttribute('data-party-filter');
        all('[data-party-filter]').forEach(function (node) { node.classList.toggle('active', node === button); });
        renderParties();
      });
    });

    all('[data-transaction-filter]').forEach(function (button) {
      button.addEventListener('click', function () {
        state.transactionFilter = button.getAttribute('data-transaction-filter');
        all('[data-transaction-filter]').forEach(function (node) { node.classList.toggle('active', node === button); });
        renderTransactions();
      });
    });

    one('#item-form').addEventListener('submit', saveItem);
    one('#party-form').addEventListener('submit', saveParty);
    one('#business-form').addEventListener('submit', saveBusiness);
    one('#save-sale').addEventListener('click', saveSale);
  }

  window.addEventListener('error', function (event) {
    console.error('Stable owner app error', event.error || event.message);
  });

  window.addEventListener('unhandledrejection', function (event) {
    console.error('Stable owner app promise error', event.reason);
    toast(event.reason && event.reason.message ? event.reason.message : 'An unexpected error occurred', true);
  });

  boot();
})();
