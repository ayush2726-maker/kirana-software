(() => {
  'use strict';

  const shopSlug = String(new URLSearchParams(location.search).get('shop') || '').trim();
  const storageSuffix = shopSlug || 'unknown-shop';
  const tokenKey = `ks_customer_token:${storageSuffix}`;
  const shopKey = `ks_customer_shop:${storageSuffix}`;

  function loadStoredToken() {
    const scoped = localStorage.getItem(tokenKey) || '';
    if (scoped) return scoped;

    // One-time migration from the old global storage keys. Only migrate when
    // the saved shop matches this exact customer link.
    const legacyShop = localStorage.getItem('ks_customer_shop') || '';
    const legacyToken = localStorage.getItem('ks_customer_token') || '';
    if (legacyToken && legacyShop && legacyShop === shopSlug) {
      localStorage.setItem(tokenKey, legacyToken);
      localStorage.setItem(shopKey, shopSlug);
      localStorage.removeItem('ks_customer_token');
      localStorage.removeItem('ks_customer_shop');
      return legacyToken;
    }
    return '';
  }

  const state = {
    token: loadStoredToken(),
    me: null,
    products: [],
    orders: [],
    cart: [],
    productQty: {}
  };

  const fmt = value => `₹${Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const safe = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  const sourceText = source => ({
    fixed: 'Aapka Special Rate',
    recent_15_days: 'Last 15 Days Bill Rate',
    catalog: 'Default Customer Rate',
    last_bill: 'Aapke Last Bill Ka Rate',
    default: 'Current Rate'
  }[source] || 'Rate');
  const roundQty = value => Math.round(Math.max(0, Number(value || 0)) * 1000) / 1000;
  const fmtQty = value => Number(roundQty(value).toFixed(3)).toString();

  function saveSession(token, resolvedShop) {
    const slug = String(resolvedShop || shopSlug).trim();
    state.token = String(token || '');
    if (!state.token) return;
    localStorage.setItem(tokenKey, state.token);
    localStorage.setItem(shopKey, slug || shopSlug);
  }

  function clearSession() {
    localStorage.removeItem(tokenKey);
    localStorage.removeItem(shopKey);
    // Remove old global keys only when they belong to this shop.
    if ((localStorage.getItem('ks_customer_shop') || '') === shopSlug) {
      localStorage.removeItem('ks_customer_token');
      localStorage.removeItem('ks_customer_shop');
    }
  }

  function ensureQtyStyles() {
    if (document.querySelector('link[data-customer-product-qty]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/customer-product-qty.css?v=063';
    link.dataset.customerProductQty = '1';
    document.head.appendChild(link);
  }

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    const requestToken = state.token;
    if (requestToken && path !== '/api/customer/login') headers.Authorization = `Bearer ${requestToken}`;
    if (options.body) {
      headers['Content-Type'] = 'application/json';
      options.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
    }
    const response = await fetch(path, { ...options, headers, cache: 'no-store' });
    const data = await response.json().catch(() => null);
    if (response.status === 401 && path !== '/api/customer/login') {
      const staleResponse = Boolean(requestToken && requestToken !== state.token);
      if (!staleResponse) logout(false);
      const authError = new Error('Login expired. Please sign in again.');
      authError.code = staleResponse ? 'STALE_AUTH' : 'AUTH_EXPIRED';
      throw authError;
    }
    if (!response.ok) throw new Error(data?.detail || 'Request failed');
    return data;
  }

  function toast(message, error = false) {
    const box = document.querySelector('#customer-toast');
    box.textContent = message;
    box.className = `customer-toast show${error ? ' error' : ''}`;
    setTimeout(() => { box.className = 'customer-toast'; }, 3000);
  }

  async function boot() {
    ensureQtyStyles();
    bind();
    renderCart();
    if (!shopSlug) {
      showLogin();
      toast('Please open the exact customer link shared by the shop.', true);
      return;
    }
    if (!state.token) return showLogin();
    try {
      await enterApp();
    } catch (error) {
      if (error && error.code !== 'STALE_AUTH') toast(error.message, true);
    }
  }

  function bind() {
    document.querySelector('#customer-login-form').addEventListener('submit', login);
    document.querySelector('#customer-logout').addEventListener('click', () => logout(true));
    document.querySelector('#customer-search').addEventListener('input', renderProducts);
    document.querySelector('#customer-place-order').addEventListener('click', placeOrder);
    document.querySelectorAll('[data-customer-tab]').forEach(button => button.addEventListener('click', () => switchTab(button.dataset.customerTab)));
  }

  function showLogin() {
    document.querySelector('#customer-login').classList.remove('hidden');
    document.querySelector('#customer-app').classList.add('hidden');
  }

  async function login(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const button = formElement.querySelector('button[type="submit"]');
    const previousLabel = button ? button.textContent : 'Login';
    if (button) {
      button.disabled = true;
      button.textContent = 'Signing in...';
    }

    // Clear only this shop's old session. Other shop sessions remain saved.
    state.token = '';
    clearSession();

    try {
      const result = await api('/api/customer/login', {
        method: 'POST',
        body: { phone: form.get('phone'), pin: form.get('pin'), shop_slug: shopSlug }
      });
      if (!result || !result.token) throw new Error('Login could not be completed. Please try again.');
      saveSession(result.token, result.shop_slug || shopSlug);
      await enterApp();
      const pinInput = formElement.querySelector('[name="pin"]');
      if (pinInput) pinInput.value = '';
      toast('Login successful');
    } catch (error) {
      if (!error || error.code !== 'STALE_AUTH') toast(error.message || 'Login failed', true);
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = previousLabel;
      }
    }
  }

  async function enterApp() {
    state.me = await api('/api/customer/me');
    document.querySelector('#customer-login').classList.add('hidden');
    document.querySelector('#customer-app').classList.remove('hidden');
    document.querySelector('#customer-business').textContent = state.me.business_name;
    document.querySelector('#customer-name').textContent = `${state.me.party_name} · Balance ${fmt(state.me.balance)}`;
    await Promise.all([loadProducts(), loadOrders()]);
    switchTab('shop');
  }

  async function logout(callApi) {
    const tokenToLogout = state.token;
    if (callApi && tokenToLogout) api('/api/customer/logout', { method: 'POST' }).catch(() => {});
    state.token = '';
    state.me = null;
    state.cart = [];
    state.productQty = {};
    clearSession();
    showLogin();
  }

  async function loadProducts() {
    state.products = await api('/api/customer/catalog');
    renderProducts();
  }

  function renderProducts() {
    const query = document.querySelector('#customer-search').value.trim().toLowerCase();
    const rows = state.products.filter(product => `${product.name} ${product.size || ''} ${product.category || ''}`.toLowerCase().includes(query));
    const container = document.querySelector('#customer-products');
    if (!rows.length) {
      container.innerHTML = '<div class="customer-empty">Product nahi mila</div>';
      return;
    }
    container.innerHTML = rows.map(product => {
      const qty = state.productQty[product.id] || 1;
      return `
        <article class="customer-product-card">
          <div class="customer-product-main">
            <div><strong>${safe(product.name)}</strong><small class="customer-product-unit">${safe(product.size || product.unit || '')}</small></div>
            <div class="customer-rate"><strong>${fmt(product.rate)}</strong><small>${safe(sourceText(product.rate_source))}</small></div>
          </div>
          <div class="customer-product-actions">
            <div class="customer-product-qty" aria-label="Quantity">
              <button type="button" data-product-minus="${product.id}" aria-label="Quantity kam karein">−</button>
              <input data-product-qty="${product.id}" type="number" min="0.01" step="0.01" value="${fmtQty(qty)}" inputmode="decimal" aria-label="Quantity" />
              <button type="button" data-product-plus="${product.id}" aria-label="Quantity badhayein">+</button>
            </div>
            <button class="customer-product-add" type="button" data-customer-add="${product.id}">Cart me Add</button>
          </div>
        </article>
      `;
    }).join('');

    container.querySelectorAll('[data-product-qty]').forEach(input => {
      input.addEventListener('input', () => {
        const itemId = Number(input.dataset.productQty);
        const qty = roundQty(input.value);
        if (qty > 0) state.productQty[itemId] = qty;
      });
      input.addEventListener('change', () => {
        const itemId = Number(input.dataset.productQty);
        const qty = Math.max(0.01, roundQty(input.value));
        state.productQty[itemId] = qty;
        input.value = fmtQty(qty);
      });
    });
    container.querySelectorAll('[data-product-minus]').forEach(button => button.addEventListener('click', () => {
      const itemId = Number(button.dataset.productMinus);
      const current = state.productQty[itemId] || 1;
      state.productQty[itemId] = Math.max(0.01, roundQty(current - 1));
      const input = container.querySelector(`[data-product-qty="${itemId}"]`);
      if (input) input.value = fmtQty(state.productQty[itemId]);
    }));
    container.querySelectorAll('[data-product-plus]').forEach(button => button.addEventListener('click', () => {
      const itemId = Number(button.dataset.productPlus);
      state.productQty[itemId] = roundQty((state.productQty[itemId] || 1) + 1);
      const input = container.querySelector(`[data-product-qty="${itemId}"]`);
      if (input) input.value = fmtQty(state.productQty[itemId]);
    }));
    container.querySelectorAll('[data-customer-add]').forEach(button => button.addEventListener('click', () => addToCart(Number(button.dataset.customerAdd))));
  }

  function addToCart(itemId) {
    const product = state.products.find(row => row.id === itemId);
    if (!product) return;
    const input = document.querySelector(`[data-product-qty="${itemId}"]`);
    const qty = Math.max(0.01, roundQty(input?.value || state.productQty[itemId] || 1));
    if (!Number.isFinite(qty) || qty <= 0) return toast('Sahi quantity daalein', true);
    const existing = state.cart.find(row => row.item_id === itemId);
    if (existing) existing.qty = roundQty(existing.qty + qty);
    else state.cart.push({ item_id: itemId, name: product.name, size: product.size || product.unit || '', qty, rate: Number(product.rate || 0), gst_rate: Number(product.gst_rate || 0), rate_source: product.rate_source });
    state.productQty[itemId] = 1;
    if (input) input.value = '1';
    renderCart();
    toast(`${product.name} × ${fmtQty(qty)} cart me add ho gaya`);
  }

  function renderCart() {
    const container = document.querySelector('#customer-cart');
    if (!state.cart.length) {
      container.innerHTML = '<div class="customer-empty">Cart khali hai</div>';
      document.querySelector('#customer-total').textContent = fmt(0);
      document.querySelector('#customer-cart-count').textContent = '0';
      return;
    }
    container.innerHTML = state.cart.map((line, index) => {
      const subtotal = line.qty * line.rate;
      const total = subtotal + subtotal * line.gst_rate / 100;
      return `
        <article class="customer-cart-line">
          <div><strong>${safe(line.name)}</strong><small>${safe(line.size)} · ${fmt(line.rate)}</small></div>
          <div class="customer-qty"><button data-cart-minus="${index}" type="button">−</button><span>${fmtQty(line.qty)}</span><button data-cart-plus="${index}" type="button">+</button></div>
          <b>${fmt(total)}</b>
          <button class="customer-remove" data-cart-remove="${index}" type="button">×</button>
        </article>
      `;
    }).join('');
    container.querySelectorAll('[data-cart-minus]').forEach(button => button.addEventListener('click', () => {
      const row = state.cart[Number(button.dataset.cartMinus)];
      row.qty = roundQty(row.qty - 1);
      if (row.qty <= 0) state.cart.splice(Number(button.dataset.cartMinus), 1);
      renderCart();
    }));
    container.querySelectorAll('[data-cart-plus]').forEach(button => button.addEventListener('click', () => {
      state.cart[Number(button.dataset.cartPlus)].qty = roundQty(state.cart[Number(button.dataset.cartPlus)].qty + 1);
      renderCart();
    }));
    container.querySelectorAll('[data-cart-remove]').forEach(button => button.addEventListener('click', () => {
      state.cart.splice(Number(button.dataset.cartRemove), 1);
      renderCart();
    }));
    const total = state.cart.reduce((sum, line) => {
      const subtotal = line.qty * line.rate;
      return sum + subtotal + subtotal * line.gst_rate / 100;
    }, 0);
    document.querySelector('#customer-total').textContent = fmt(total);
    document.querySelector('#customer-cart-count').textContent = fmtQty(state.cart.reduce((sum, line) => sum + line.qty, 0));
  }

  async function placeOrder() {
    if (!state.cart.length) return toast('Cart me product add karein', true);
    const button = document.querySelector('#customer-place-order');
    button.disabled = true;
    try {
      const order = await api('/api/customer/orders', {
        method: 'POST',
        body: {
          notes: document.querySelector('#customer-order-note').value,
          items: state.cart.map(line => ({ item_id: line.item_id, qty: line.qty }))
        }
      });
      state.cart = [];
      document.querySelector('#customer-order-note').value = '';
      renderCart();
      await loadOrders();
      switchTab('orders');
      toast(`${order.order_no} order place ho gaya`);
    } catch (error) {
      toast(error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  async function loadOrders() {
    state.orders = await api('/api/customer/orders');
    renderOrders();
  }

  function renderOrders() {
    const container = document.querySelector('#customer-orders');
    if (!state.orders.length) {
      container.innerHTML = '<div class="customer-empty">Abhi koi order nahi hai</div>';
      return;
    }
    container.innerHTML = state.orders.map(order => `
      <article class="customer-order-card">
        <div class="customer-order-head"><div><strong>${safe(order.order_no)}</strong><small>${safe(order.order_date)}</small></div><span class="status-${safe(order.status)}">${safe(order.status)}</span></div>
        <div class="customer-order-items">${order.items.map(item => `<div><span>${safe(item.item_name)} ${safe(item.size || '')} × ${fmtQty(item.qty)}</span><b>${fmt(item.line_total)}</b></div>`).join('')}</div>
        <div class="customer-order-total"><span>${order.invoice_no ? `Bill ${safe(order.invoice_no)}` : 'Total'}</span><strong>${fmt(order.total)}</strong></div>
      </article>
    `).join('');
  }

  function switchTab(tab) {
    document.querySelectorAll('[data-customer-tab]').forEach(button => button.classList.toggle('active', button.dataset.customerTab === tab));
    document.querySelectorAll('.customer-tab').forEach(panel => panel.classList.toggle('active', panel.id === `customer-tab-${tab}`));
    if (tab === 'orders') loadOrders().catch(error => toast(error.message, true));
  }

  boot();
})();
