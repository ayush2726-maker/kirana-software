(() => {
  const state = { products: [], query: '', loading: false };
  const token = () => localStorage.getItem('ks_token') || '';
  const safe = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  const money = value => `₹${Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (token()) headers.Authorization = `Bearer ${token()}`;
    if (options.body) {
      headers['Content-Type'] = 'application/json';
      options.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
    }
    const response = await fetch(path, { ...options, headers });
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.detail || `Request failed (${response.status})`);
    return data;
  }

  function notify(message, error = false) {
    const box = document.querySelector('#toast');
    if (box) {
      box.textContent = message;
      box.className = `toast show${error ? ' error' : ''}`;
      setTimeout(() => { box.className = 'toast'; }, 3400);
      return;
    }
    alert(message);
  }

  function inject() {
    if (document.querySelector('#customer-catalog-modal')) return;

    const drawer = document.querySelector('.drawer-nav');
    if (drawer) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'open-customer-catalog-drawer';
      button.innerHTML = '<span class="catalog-menu-icon">👁️</span>App Products';
      const settings = drawer.querySelector('[data-go="settings"]');
      drawer.insertBefore(button, settings || null);
    }

    const quickLinks = document.querySelector('#page-home .quick-links');
    if (quickLinks) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'open-customer-catalog-home';
      button.innerHTML = '<span class="quick-icon blue">👁️</span><b>App Products</b>';
      quickLinks.appendChild(button);
    }

    document.body.insertAdjacentHTML('beforeend', `
      <div id="customer-catalog-modal" class="catalog-modal hidden" aria-hidden="true">
        <div class="catalog-sheet">
          <header class="catalog-head">
            <div><small>CUSTOMER APP</small><h2>Products Show / Hide</h2></div>
            <button id="close-customer-catalog" type="button" aria-label="Close">×</button>
          </header>
          <div class="catalog-toolbar">
            <input id="customer-catalog-search" type="search" placeholder="Product ya size search karein" />
            <div class="catalog-summary"><strong id="catalog-visible-count">0</strong><span>products customer ko dikh rahe hain</span></div>
            <div class="catalog-bulk-actions">
              <button id="catalog-show-all" type="button">Sab Show</button>
              <button id="catalog-hide-all" class="danger" type="button">Sab Hide</button>
            </div>
          </div>
          <div id="customer-catalog-list" class="catalog-list">
            <div class="catalog-empty">Products load ho rahe hain…</div>
          </div>
          <footer class="catalog-foot">Sirf ON kiye hue products customer app mein dikhेंगे. Hidden product ka order API se bhi block rahega.</footer>
        </div>
      </div>
    `);

    document.querySelector('#open-customer-catalog-drawer')?.addEventListener('click', openManager);
    document.querySelector('#open-customer-catalog-home')?.addEventListener('click', openManager);
    document.querySelector('#close-customer-catalog')?.addEventListener('click', closeManager);
    document.querySelector('#customer-catalog-modal')?.addEventListener('click', event => {
      if (event.target.id === 'customer-catalog-modal') closeManager();
    });
    document.querySelector('#customer-catalog-search')?.addEventListener('input', event => {
      state.query = event.target.value.trim().toLowerCase();
      render();
    });
    document.querySelector('#catalog-show-all')?.addEventListener('click', () => bulk('show_all'));
    document.querySelector('#catalog-hide-all')?.addEventListener('click', () => bulk('hide_all'));
  }

  async function openManager() {
    const modal = document.querySelector('#customer-catalog-modal');
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('catalog-open');
    await load();
  }

  function closeManager() {
    const modal = document.querySelector('#customer-catalog-modal');
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('catalog-open');
  }

  async function load() {
    if (state.loading || !token()) return;
    state.loading = true;
    const list = document.querySelector('#customer-catalog-list');
    if (list) list.innerHTML = '<div class="catalog-empty">Products load ho rahe hain…</div>';
    try {
      const data = await api('/api/customer-catalog/manage');
      state.products = Array.isArray(data.products) ? data.products : [];
      render();
    } catch (error) {
      notify(error.message, true);
      if (list) list.innerHTML = `<div class="catalog-empty error">${safe(error.message)}</div>`;
    } finally {
      state.loading = false;
    }
  }

  function render() {
    const list = document.querySelector('#customer-catalog-list');
    const visible = state.products.filter(product => product.is_visible).length;
    const count = document.querySelector('#catalog-visible-count');
    if (count) count.textContent = String(visible);

    const rows = state.products.filter(product => {
      const text = `${product.name || ''} ${product.size || ''} ${product.unit || ''} ${product.category || ''}`.toLowerCase();
      return !state.query || text.includes(state.query);
    });

    if (!rows.length) {
      list.innerHTML = '<div class="catalog-empty">Product nahi mila</div>';
      return;
    }

    list.innerHTML = rows.map(product => `
      <article class="catalog-product-row ${product.is_visible ? 'is-visible' : ''}">
        <div class="catalog-product-info">
          <strong>${safe(product.name)}</strong>
          <small>${safe([product.size, product.unit].filter(Boolean).join(' · ') || 'No size')} ${Number(product.member_count || 1) > 1 ? `· ${Number(product.member_count)} duplicate rows grouped` : ''}</small>
          <span>${money(product.sale_price)}</span>
        </div>
        <button class="catalog-toggle ${product.is_visible ? 'on' : ''}" type="button" data-catalog-key="${encodeURIComponent(product.catalog_key)}" aria-pressed="${product.is_visible ? 'true' : 'false'}">
          <i></i><b>${product.is_visible ? 'SHOW' : 'HIDE'}</b>
        </button>
      </article>
    `).join('');

    list.querySelectorAll('[data-catalog-key]').forEach(button => button.addEventListener('click', () => {
      const key = decodeURIComponent(button.dataset.catalogKey || '');
      const product = state.products.find(row => row.catalog_key === key);
      if (product) toggleProduct(product, button);
    }));
  }

  async function toggleProduct(product, button) {
    const next = !product.is_visible;
    button.disabled = true;
    try {
      await api('/api/customer-catalog/visibility', {
        method: 'PUT',
        body: { catalog_key: product.catalog_key, is_visible: next }
      });
      product.is_visible = next;
      render();
      notify(`${product.name} customer app mein ${next ? 'show' : 'hide'} ho gaya`);
    } catch (error) {
      notify(error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  async function bulk(action) {
    const message = action === 'show_all'
      ? 'Saare products customer app mein show karne hain?'
      : 'Saare products customer app se hide karne hain?';
    if (!confirm(message)) return;
    const buttons = document.querySelectorAll('#catalog-show-all, #catalog-hide-all');
    buttons.forEach(button => { button.disabled = true; });
    try {
      await api('/api/customer-catalog/visibility/bulk', { method: 'POST', body: { action } });
      const visible = action === 'show_all';
      state.products.forEach(product => { product.is_visible = visible; });
      render();
      notify(visible ? 'Saare products show ho gaye' : 'Saare products hide ho gaye');
    } catch (error) {
      notify(error.message, true);
    } finally {
      buttons.forEach(button => { button.disabled = false; });
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inject);
  else inject();
})();
