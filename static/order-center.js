(() => {
  const model = { parties: [], items: [], orders: [], access: [], cart: [], tab: 'new' };
  const token = () => localStorage.getItem('ks_token') || '';
  const fmt = value => `₹${Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const safe = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  const sourceText = source => ({ fixed: 'Fixed Rate', last_bill: 'Last Bill Rate', default: 'Default Rate', manual: 'Manual Rate' }[source] || source);

  async function request(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (token()) headers.Authorization = `Bearer ${token()}`;
    if (options.body && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      options.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
    }
    const response = await fetch(path, { ...options, headers });
    const data = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.detail || `Request failed (${response.status})`);
    return data;
  }

  function notify(message, error = false) {
    const existing = document.querySelector('#toast');
    if (existing) {
      existing.textContent = message;
      existing.className = `toast show${error ? ' error' : ''}`;
      setTimeout(() => { existing.className = 'toast'; }, 3200);
      return;
    }
    alert(message);
  }

  function inject() {
    if (document.querySelector('#order-center-modal')) return;
    const drawer = document.querySelector('.drawer-nav');
    if (drawer) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'open-order-center-drawer';
      button.innerHTML = '<span class="order-menu-icon">🧾</span>Customer Orders';
      const settings = drawer.querySelector('[data-go="settings"]');
      drawer.insertBefore(button, settings || null);
    }

    const quickLinks = document.querySelector('#page-home .quick-links');
    if (quickLinks) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'open-order-center-home';
      button.innerHTML = '<span class="quick-icon blue order-quick-icon">🛒</span><b>Orders</b>';
      quickLinks.appendChild(button);
    }

    document.body.insertAdjacentHTML('beforeend', `
      <div id="order-center-modal" class="order-center-modal hidden" aria-hidden="true">
        <div class="order-center-sheet">
          <header class="order-center-head">
            <div><small>KISHORE TRADERS</small><h2>Customer Order Center</h2></div>
            <button id="close-order-center" type="button" aria-label="Close">×</button>
          </header>
          <div class="order-center-tabs">
            <button data-order-tab="new" class="active">New Order</button>
            <button data-order-tab="list">Orders</button>
            <button data-order-tab="access">Customer Login</button>
          </div>
          <div class="order-center-body">
            <section id="order-tab-new" class="order-panel active">
              <div class="order-form-grid">
                <label>Customer<select id="order-party"><option value="">Customer select karein</option></select></label>
                <label>Order Date<input id="order-date" type="date" /></label>
              </div>
              <div class="order-product-search">
                <input id="order-item-search" placeholder="Product, size ya SKU search karein" autocomplete="off" />
                <div id="order-search-results" class="order-search-results hidden"></div>
              </div>
              <div id="order-cart" class="order-cart"></div>
              <label class="order-notes">Order Note<textarea id="order-notes" rows="2" placeholder="Packing, delivery ya anya note"></textarea></label>
              <div class="order-total-row"><span>Order Total</span><strong id="order-total">₹0.00</strong></div>
              <button id="save-order" class="order-primary" type="button">Order Save Karein</button>
            </section>
            <section id="order-tab-list" class="order-panel">
              <div class="order-list-toolbar"><select id="order-status-filter"><option value="">All Orders</option><option value="pending">Pending</option><option value="confirmed">Confirmed</option><option value="processing">Processing</option><option value="dispatched">Dispatched</option><option value="delivered">Delivered</option><option value="converted">Bill Created</option><option value="cancelled">Cancelled</option></select><button id="refresh-orders" type="button">Refresh</button></div>
              <div id="owner-orders" class="owner-orders"></div>
            </section>
            <section id="order-tab-access" class="order-panel">
              <div class="customer-portal-link"><div><small>Customer order link</small><strong id="customer-portal-url"></strong></div><button id="copy-customer-link" type="button">Copy Link</button></div>
              <form id="customer-access-form" class="customer-access-form">
                <label>Customer<select id="access-party" required><option value="">Customer select karein</option></select></label>
                <label>Mobile<input id="access-phone" inputmode="tel" required /></label>
                <label>Login PIN<input id="access-pin" type="password" inputmode="numeric" minlength="4" required placeholder="4 digit ya adhik" /></label>
                <button class="order-primary" type="submit">Customer Login Banaye / Reset Karein</button>
              </form>
              <div id="customer-access-list" class="customer-access-list"></div>
            </section>
          </div>
        </div>
      </div>
    `);

    document.querySelector('#order-date').value = new Date().toISOString().slice(0, 10);
    document.querySelector('#customer-portal-url').textContent = `${location.origin}/customer`;
    bindEvents();
    renderCart();
  }

  function bindEvents() {
    document.querySelector('#open-order-center-drawer')?.addEventListener('click', openCenter);
    document.querySelector('#open-order-center-home')?.addEventListener('click', openCenter);
    document.querySelector('#close-order-center')?.addEventListener('click', closeCenter);
    document.querySelector('#order-center-modal')?.addEventListener('click', event => {
      if (event.target.id === 'order-center-modal') closeCenter();
    });
    document.querySelectorAll('[data-order-tab]').forEach(button => button.addEventListener('click', () => switchTab(button.dataset.orderTab)));
    document.querySelector('#order-party')?.addEventListener('change', () => {
      model.cart = [];
      renderCart();
    });
    document.querySelector('#order-item-search')?.addEventListener('input', renderSearchResults);
    document.querySelector('#order-item-search')?.addEventListener('focus', renderSearchResults);
    document.querySelector('#save-order')?.addEventListener('click', saveOrder);
    document.querySelector('#refresh-orders')?.addEventListener('click', loadOrders);
    document.querySelector('#order-status-filter')?.addEventListener('change', loadOrders);
    document.querySelector('#customer-access-form')?.addEventListener('submit', saveCustomerAccess);
    document.querySelector('#access-party')?.addEventListener('change', fillAccessPhone);
    document.querySelector('#copy-customer-link')?.addEventListener('click', copyPortalLink);
    document.addEventListener('click', event => {
      if (!event.target.closest('.order-product-search')) document.querySelector('#order-search-results')?.classList.add('hidden');
    });
  }

  async function openCenter() {
    const modal = document.querySelector('#order-center-modal');
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('order-center-open');
    try {
      await loadMaster();
      await Promise.all([loadOrders(), loadAccess()]);
      switchTab('new');
    } catch (error) {
      notify(error.message, true);
    }
  }

  function closeCenter() {
    const modal = document.querySelector('#order-center-modal');
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('order-center-open');
  }

  function switchTab(tab) {
    model.tab = tab;
    document.querySelectorAll('[data-order-tab]').forEach(button => button.classList.toggle('active', button.dataset.orderTab === tab));
    document.querySelectorAll('.order-panel').forEach(panel => panel.classList.toggle('active', panel.id === `order-tab-${tab}`));
    if (tab === 'list') loadOrders();
    if (tab === 'access') loadAccess();
  }

  async function loadMaster() {
    [model.parties, model.items] = await Promise.all([
      request('/api/parties?party_type=customer'),
      request('/api/items?limit=2000')
    ]);
    const customerOptions = model.parties
      .filter(party => ['customer', 'both'].includes(party.type))
      .map(party => `<option value="${party.id}">${safe(party.name)}${party.phone ? ` · ${safe(party.phone)}` : ''}</option>`)
      .join('');
    document.querySelector('#order-party').innerHTML = `<option value="">Customer select karein</option>${customerOptions}`;
    document.querySelector('#access-party').innerHTML = `<option value="">Customer select karein</option>${customerOptions}`;
  }

  function renderSearchResults() {
    const box = document.querySelector('#order-search-results');
    const query = document.querySelector('#order-item-search').value.trim().toLowerCase();
    const matches = model.items.filter(item => {
      const text = `${item.name} ${item.size || ''} ${item.sku || ''} ${item.category || ''}`.toLowerCase();
      return !query || text.includes(query);
    }).slice(0, 15);
    box.innerHTML = matches.length ? matches.map(item => `
      <button type="button" data-add-order-item="${item.id}">
        <span><strong>${safe(item.name)}</strong><small>${safe(item.size || item.unit || '')} · Stock ${Number(item.stock || 0)}</small></span>
        <b>${fmt(item.sale_price)}</b>
      </button>
    `).join('') : '<div class="order-empty">Product nahi mila</div>';
    box.classList.remove('hidden');
    box.querySelectorAll('[data-add-order-item]').forEach(button => button.addEventListener('click', () => addItem(Number(button.dataset.addOrderItem))));
  }

  async function addItem(itemId) {
    const partyId = Number(document.querySelector('#order-party').value);
    if (!partyId) {
      notify('Pehle customer select karein', true);
      return;
    }
    const existing = model.cart.find(line => line.item_id === itemId);
    if (existing) {
      existing.qty += 1;
      renderCart();
      return;
    }
    try {
      const rate = await request(`/api/order-rate?party_id=${partyId}&item_id=${itemId}`);
      model.cart.push({
        item_id: itemId,
        name: rate.name,
        size: rate.size || rate.unit || '',
        qty: 1,
        rate: Number(rate.rate || 0),
        rate_source: rate.rate_source,
        gst_rate: Number(rate.gst_rate || 0),
        save_as_customer_rate: false
      });
      document.querySelector('#order-item-search').value = '';
      document.querySelector('#order-search-results').classList.add('hidden');
      renderCart();
    } catch (error) {
      notify(error.message, true);
    }
  }

  function renderCart() {
    const container = document.querySelector('#order-cart');
    if (!model.cart.length) {
      container.innerHTML = '<div class="order-empty-cart">Customer select karke product add karein. Rate automatic customer ke fixed ya last bill se aayega.</div>';
      document.querySelector('#order-total').textContent = fmt(0);
      return;
    }
    container.innerHTML = model.cart.map((line, index) => {
      const subtotal = line.qty * line.rate;
      const tax = subtotal * line.gst_rate / 100;
      return `
        <article class="order-cart-line" data-order-line="${index}">
          <div class="order-line-title"><div><strong>${safe(line.name)}</strong><small>${safe(line.size)} <span class="rate-source ${safe(line.rate_source)}">${safe(sourceText(line.rate_source))}</span></small></div><button type="button" data-remove-line="${index}">×</button></div>
          <div class="order-line-inputs">
            <label>Qty<input data-line-qty="${index}" type="number" min="0.01" step="0.01" value="${line.qty}" /></label>
            <label>Rate<input data-line-rate="${index}" type="number" min="0" step="0.01" value="${line.rate}" /></label>
            <strong>${fmt(subtotal + tax)}</strong>
          </div>
          <label class="save-fixed-rate"><input data-line-fixed="${index}" type="checkbox" ${line.save_as_customer_rate ? 'checked' : ''} /> Is rate ko is customer ke liye future fixed rate bana do</label>
        </article>
      `;
    }).join('');
    container.querySelectorAll('[data-remove-line]').forEach(button => button.addEventListener('click', () => {
      model.cart.splice(Number(button.dataset.removeLine), 1);
      renderCart();
    }));
    container.querySelectorAll('[data-line-qty]').forEach(input => input.addEventListener('change', () => {
      model.cart[Number(input.dataset.lineQty)].qty = Math.max(0.01, Number(input.value || 0));
      renderCart();
    }));
    container.querySelectorAll('[data-line-rate]').forEach(input => input.addEventListener('change', () => {
      const line = model.cart[Number(input.dataset.lineRate)];
      line.rate = Math.max(0, Number(input.value || 0));
      line.rate_source = 'manual';
      renderCart();
    }));
    container.querySelectorAll('[data-line-fixed]').forEach(input => input.addEventListener('change', () => {
      model.cart[Number(input.dataset.lineFixed)].save_as_customer_rate = input.checked;
    }));
    const total = model.cart.reduce((sum, line) => {
      const subtotal = line.qty * line.rate;
      return sum + subtotal + subtotal * line.gst_rate / 100;
    }, 0);
    document.querySelector('#order-total').textContent = fmt(total);
  }

  async function saveOrder() {
    const partyId = Number(document.querySelector('#order-party').value);
    if (!partyId) return notify('Customer select karein', true);
    if (!model.cart.length) return notify('Kam se kam ek product add karein', true);
    const button = document.querySelector('#save-order');
    button.disabled = true;
    try {
      const order = await request('/api/orders', {
        method: 'POST',
        body: {
          party_id: partyId,
          order_date: document.querySelector('#order-date').value,
          notes: document.querySelector('#order-notes').value,
          items: model.cart.map(line => ({
            item_id: line.item_id,
            qty: line.qty,
            rate: line.rate,
            save_as_customer_rate: line.save_as_customer_rate
          }))
        }
      });
      notify(`${order.order_no} order save ho gaya`);
      model.cart = [];
      document.querySelector('#order-notes').value = '';
      renderCart();
      await loadOrders();
      switchTab('list');
    } catch (error) {
      notify(error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  async function loadOrders() {
    if (!token()) return;
    const status = document.querySelector('#order-status-filter')?.value || '';
    try {
      model.orders = await request(`/api/orders?limit=200${status ? `&status=${encodeURIComponent(status)}` : ''}`);
      renderOrders();
    } catch (error) {
      notify(error.message, true);
    }
  }

  function renderOrders() {
    const container = document.querySelector('#owner-orders');
    if (!model.orders.length) {
      container.innerHTML = '<div class="order-empty">Abhi koi order nahi hai</div>';
      return;
    }
    container.innerHTML = model.orders.map(order => `
      <article class="owner-order-card">
        <div class="owner-order-top"><div><strong>${safe(order.order_no)}</strong><small>${safe(order.party_name)} · ${safe(order.order_date)} · ${order.source === 'customer' ? 'Customer App' : 'Owner'}</small></div><span class="order-status ${safe(order.status)}">${safe(order.status)}</span></div>
        <div class="owner-order-items">${order.items.map(item => `<div><span>${safe(item.item_name)} ${safe(item.size || '')} × ${item.qty}</span><b>${fmt(item.line_total)}</b></div>`).join('')}</div>
        <div class="owner-order-bottom"><strong>${fmt(order.total)}</strong><div>
          ${!['converted', 'cancelled'].includes(order.status) ? `<select data-status-order="${order.id}"><option value="pending" ${order.status === 'pending' ? 'selected' : ''}>Pending</option><option value="confirmed" ${order.status === 'confirmed' ? 'selected' : ''}>Confirmed</option><option value="processing" ${order.status === 'processing' ? 'selected' : ''}>Processing</option><option value="dispatched" ${order.status === 'dispatched' ? 'selected' : ''}>Dispatched</option><option value="delivered" ${order.status === 'delivered' ? 'selected' : ''}>Delivered</option><option value="cancelled">Cancel</option></select><button data-convert-order="${order.id}" type="button">Bill Banaye</button>` : order.invoice_no ? `<span class="invoice-pill">${safe(order.invoice_no)}</span>` : ''}
        </div></div>
      </article>
    `).join('');
    container.querySelectorAll('[data-status-order]').forEach(select => select.addEventListener('change', () => changeOrderStatus(Number(select.dataset.statusOrder), select.value)));
    container.querySelectorAll('[data-convert-order]').forEach(button => button.addEventListener('click', () => convertOrder(Number(button.dataset.convertOrder))));
  }

  async function changeOrderStatus(orderId, status) {
    try {
      await request(`/api/orders/${orderId}/status`, { method: 'PUT', body: { status } });
      notify('Order status update ho gaya');
      await loadOrders();
    } catch (error) {
      notify(error.message, true);
    }
  }

  async function convertOrder(orderId) {
    if (!confirm('Is order ka credit sale bill banana hai? Stock aur customer khata update ho jayega.')) return;
    try {
      const result = await request(`/api/orders/${orderId}/convert-to-sale`, { method: 'POST' });
      notify(`Bill ${result.sale.invoice_no} ban gaya`);
      await loadOrders();
      if (typeof refreshAll === 'function') refreshAll();
    } catch (error) {
      notify(error.message, true);
    }
  }

  async function loadAccess() {
    if (!token()) return;
    try {
      model.access = await request('/api/customer-access');
      renderAccess();
    } catch (error) {
      notify(error.message, true);
    }
  }

  function fillAccessPhone() {
    const party = model.parties.find(row => row.id === Number(document.querySelector('#access-party').value));
    document.querySelector('#access-phone').value = party?.phone || '';
  }

  async function saveCustomerAccess(event) {
    event.preventDefault();
    const partyId = Number(document.querySelector('#access-party').value);
    if (!partyId) return notify('Customer select karein', true);
    try {
      await request('/api/customer-access', {
        method: 'POST',
        body: {
          party_id: partyId,
          phone: document.querySelector('#access-phone').value,
          pin: document.querySelector('#access-pin').value,
          is_active: true
        }
      });
      document.querySelector('#access-pin').value = '';
      notify('Customer login ready hai');
      await loadAccess();
    } catch (error) {
      notify(error.message, true);
    }
  }

  function renderAccess() {
    const container = document.querySelector('#customer-access-list');
    if (!model.access.length) {
      container.innerHTML = '<div class="order-empty">Abhi kisi customer ka app login nahi bana hai</div>';
      return;
    }
    container.innerHTML = model.access.map(row => `
      <div class="customer-access-row"><div><strong>${safe(row.party_name)}</strong><small>${safe(row.phone)}</small></div><span>${row.is_active ? 'Active' : 'Blocked'}</span></div>
    `).join('');
  }

  async function copyPortalLink() {
    const url = `${location.origin}/customer`;
    try {
      await navigator.clipboard.writeText(url);
      notify('Customer order link copy ho gaya');
    } catch {
      prompt('Ye link customer ko bhejein:', url);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inject);
  else inject();
})();
