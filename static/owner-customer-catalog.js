(function () {
  'use strict';

  var state = {
    open: false,
    loading: false,
    saving: false,
    dirty: false,
    parties: [],
    products: [],
    partyId: '',
    search: ''
  };

  function q(selector, root) {
    return (root || document).querySelector(selector);
  }

  function qa(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (character) {
      return ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      })[character];
    });
  }

  function numberOrNull(value) {
    var text = String(value == null ? '' : value).trim();
    if (!text) return null;
    var parsed = Number(text);
    return Number.isFinite(parsed) && parsed >= 0 ? Math.round(parsed * 100) / 100 : null;
  }

  function money(value) {
    return '₹' + Number(value || 0).toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
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
      throw new Error('Session expired');
    }
    if (!response.ok) {
      var detail = data && data.detail;
      if (Array.isArray(detail)) {
        detail = detail.map(function (row) { return row.msg || String(row); }).join(', ');
      }
      throw new Error(detail || 'Request failed (' + response.status + ')');
    }
    return data;
  }

  function notify(message, isError) {
    var node = q('#toast') || q('#txn-toast');
    if (!node) {
      window.alert(message);
      return;
    }
    node.textContent = String(message || 'Done');
    node.className = (node.id === 'txn-toast' ? 'txn-toast' : 'toast') + ' show' + (isError ? ' error' : '');
    window.clearTimeout(notify.timer);
    notify.timer = window.setTimeout(function () {
      node.className = node.id === 'txn-toast' ? 'txn-toast' : 'toast';
    }, 3500);
  }

  function injectMenuButtons() {
    var menu = q('#page-menu .menu-list');
    if (menu && !q('[data-catalog-action="open"]', menu)) {
      var button = document.createElement('button');
      button.type = 'button';
      button.setAttribute('data-catalog-action', 'open');
      button.innerHTML = '<span>🛍️</span><div><b>Customer Catalog</b><small>Choose products and customer rates</small></div><i>›</i>';
      var ordersButton = q('[data-page="orders"]', menu);
      if (ordersButton) menu.insertBefore(button, ordersButton);
      else menu.appendChild(button);
    }

    var settings = q('#page-settings .menu-list');
    if (settings && !q('[data-catalog-action="open"]', settings)) {
      var settingsButton = document.createElement('button');
      settingsButton.type = 'button';
      settingsButton.setAttribute('data-catalog-action', 'open');
      settingsButton.innerHTML = '<span>🛍️</span><div><b>Customer Catalog</b><small>Show/hide products and set rates</small></div><i>›</i>';
      settings.insertBefore(settingsButton, settings.firstChild);
    }
  }

  function injectScreen() {
    if (q('#customer-catalog-manager')) return;
    var screen = document.createElement('section');
    screen.id = 'customer-catalog-manager';
    screen.className = 'customer-catalog-manager hidden';
    screen.setAttribute('aria-hidden', 'true');
    screen.innerHTML =
      '<header class="catalog-manager-header">' +
        '<button type="button" class="catalog-manager-back" data-catalog-action="close" aria-label="Back">‹</button>' +
        '<div class="catalog-manager-title"><small>CUSTOMER APP</small><h1>Customer Catalog</h1></div>' +
        '<button type="button" class="catalog-manager-save" data-catalog-action="save">Save</button>' +
      '</header>' +
      '<div class="catalog-manager-controls">' +
        '<label>Rate for customer<select id="catalog-party"><option value="">All Customers — Default Rate</option></select></label>' +
        '<label>Search Products<input id="catalog-search" type="search" autocomplete="off" placeholder="Search product, size or category"></label>' +
        '<div class="catalog-manager-tools">' +
          '<button type="button" data-catalog-action="show-filtered">Show Listed</button>' +
          '<button type="button" data-catalog-action="hide-filtered">Hide Listed</button>' +
        '</div>' +
        '<div class="catalog-manager-summary"><span id="catalog-visible-summary">0 products visible</span><span id="catalog-mode-summary">Default customer rates</span></div>' +
      '</div>' +
      '<div id="catalog-manager-list" class="catalog-manager-list"><div class="catalog-manager-empty">Loading products...</div></div>';
    document.body.appendChild(screen);
  }

  async function loadParties() {
    if (state.parties.length) return;
    var rows = await api('/api/parties');
    state.parties = (rows || []).filter(function (party) {
      return party.type === 'customer' || party.type === 'both';
    }).sort(function (a, b) {
      return String(a.name || '').localeCompare(String(b.name || ''), undefined, { sensitivity: 'base' });
    });
    var select = q('#catalog-party');
    if (select) {
      select.innerHTML = '<option value="">All Customers — Default Rate</option>' + state.parties.map(function (party) {
        return '<option value="' + Number(party.id) + '">' + esc(party.name) + (party.phone ? ' · ' + esc(party.phone) : '') + '</option>';
      }).join('');
      select.value = state.partyId;
    }
  }

  function filteredProducts() {
    var term = String(state.search || '').trim().toLowerCase();
    if (!term) return state.products;
    return state.products.filter(function (product) {
      return [product.name, product.size, product.unit, product.category]
        .join(' ')
        .toLowerCase()
        .indexOf(term) >= 0;
    });
  }

  function productCard(product) {
    var customerMode = Boolean(state.partyId);
    var defaultValue = product.default_rate == null ? '' : Number(product.default_rate).toFixed(2);
    var customerValue = product.customer_rate == null ? '' : Number(product.customer_rate).toFixed(2);
    var rateLabel = product.rate_source === 'customer'
      ? 'Customer-specific rate'
      : product.rate_source === 'catalog'
        ? 'Default customer rate'
        : 'Normal item rate';
    return '<article class="catalog-product-card ' + (product.is_visible ? '' : 'is-hidden') + '" data-catalog-key="' + esc(product.catalog_key) + '">' +
      '<div class="catalog-product-head">' +
        '<div class="catalog-product-name"><b>' + esc(product.name) + '</b><small>' + esc([product.size, product.unit, product.category].filter(Boolean).join(' · ')) + '</small></div>' +
        '<label class="catalog-visibility-toggle"><input type="checkbox" data-catalog-field="visible" ' + (product.is_visible ? 'checked' : '') + '> Show</label>' +
      '</div>' +
      '<div class="catalog-rate-grid ' + (customerMode ? '' : 'one') + '">' +
        '<label>Default Customer Rate<input type="number" inputmode="decimal" min="0" step="0.01" data-catalog-field="default-rate" placeholder="Use normal rate" value="' + defaultValue + '"></label>' +
        (customerMode ? '<label>Selected Customer Rate<input type="number" inputmode="decimal" min="0" step="0.01" data-catalog-field="customer-rate" placeholder="No special rate" value="' + customerValue + '"></label>' : '') +
      '</div>' +
      '<div class="catalog-product-foot"><span>Normal ' + money(product.sale_price) + '</span><span>' + esc(rateLabel) + ': ' + money(product.effective_rate) + '</span></div>' +
      '</article>';
  }

  function renderProducts() {
    var list = q('#catalog-manager-list');
    if (!list) return;
    var products = filteredProducts();
    list.innerHTML = products.length
      ? products.map(productCard).join('')
      : '<div class="catalog-manager-empty">No matching products found.</div>';
    updateSummary();
  }

  function updateSummary() {
    var summary = q('#catalog-visible-summary');
    var mode = q('#catalog-mode-summary');
    if (summary) {
      summary.textContent = state.products.filter(function (product) { return product.is_visible; }).length + ' of ' + state.products.length + ' products visible';
    }
    if (mode) {
      var selected = state.parties.find(function (party) { return String(party.id) === String(state.partyId); });
      mode.textContent = selected ? 'Special rates: ' + selected.name : 'Default rates for all customers';
    }
    var save = q('[data-catalog-action="save"]');
    if (save) {
      save.disabled = state.loading || state.saving;
      save.textContent = state.saving ? 'Saving...' : state.dirty ? 'Save *' : 'Save';
    }
  }

  async function loadProducts() {
    state.loading = true;
    state.dirty = false;
    updateSummary();
    var list = q('#catalog-manager-list');
    if (list) list.innerHTML = '<div class="catalog-manager-empty">Loading products...</div>';
    try {
      var suffix = state.partyId ? '?party_id=' + encodeURIComponent(state.partyId) : '';
      var data = await api('/api/customer-catalog-manager' + suffix);
      state.products = data.products || [];
      renderProducts();
    } catch (error) {
      if (list) list.innerHTML = '<div class="catalog-manager-empty">' + esc(error.message) + '</div>';
      notify(error.message, true);
    } finally {
      state.loading = false;
      updateSummary();
    }
  }

  async function openManager() {
    injectScreen();
    state.open = true;
    var screen = q('#customer-catalog-manager');
    screen.classList.remove('hidden');
    screen.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    try {
      await loadParties();
      await loadProducts();
    } catch (error) {
      notify(error.message, true);
    }
  }

  function closeManager(force) {
    if (!state.open) return false;
    if (!force && state.dirty && !window.confirm('Discard unsaved customer catalog changes?')) return true;
    state.open = false;
    state.dirty = false;
    var screen = q('#customer-catalog-manager');
    if (screen) {
      screen.classList.add('hidden');
      screen.setAttribute('aria-hidden', 'true');
    }
    document.body.style.overflow = '';
    return true;
  }

  function productFromCard(card) {
    if (!card) return null;
    var key = card.getAttribute('data-catalog-key');
    return state.products.find(function (product) { return product.catalog_key === key; }) || null;
  }

  async function saveChanges() {
    if (state.loading || state.saving || !state.products.length) return;
    state.saving = true;
    updateSummary();
    try {
      await api('/api/customer-catalog-manager', {
        method: 'POST',
        body: {
          party_id: state.partyId ? Number(state.partyId) : null,
          items: state.products.map(function (product) {
            return {
              catalog_key: product.catalog_key,
              item_id: Number(product.item_id),
              is_visible: Boolean(product.is_visible),
              default_rate: product.default_rate == null ? null : Number(product.default_rate),
              customer_rate: state.partyId && product.customer_rate != null ? Number(product.customer_rate) : null
            };
          })
        }
      });
      state.dirty = false;
      notify('Customer catalog saved');
      await loadProducts();
    } catch (error) {
      notify(error.message, true);
    } finally {
      state.saving = false;
      updateSummary();
    }
  }

  function setFilteredVisibility(isVisible) {
    filteredProducts().forEach(function (product) {
      product.is_visible = isVisible;
    });
    state.dirty = true;
    renderProducts();
  }

  document.addEventListener('click', function (event) {
    var actionNode = event.target.closest('[data-catalog-action]');
    if (!actionNode) return;
    var action = actionNode.getAttribute('data-catalog-action');
    if (action === 'open') {
      event.preventDefault();
      openManager();
    } else if (action === 'close') {
      event.preventDefault();
      closeManager(false);
    } else if (action === 'save') {
      event.preventDefault();
      saveChanges();
    } else if (action === 'show-filtered') {
      event.preventDefault();
      setFilteredVisibility(true);
    } else if (action === 'hide-filtered') {
      event.preventDefault();
      setFilteredVisibility(false);
    }
  });

  document.addEventListener('input', function (event) {
    if (!state.open) return;
    if (event.target.id === 'catalog-search') {
      state.search = event.target.value || '';
      renderProducts();
      return;
    }
    var field = event.target.getAttribute('data-catalog-field');
    if (!field) return;
    var product = productFromCard(event.target.closest('[data-catalog-key]'));
    if (!product) return;
    if (field === 'visible') {
      product.is_visible = Boolean(event.target.checked);
      var card = event.target.closest('.catalog-product-card');
      if (card) card.classList.toggle('is-hidden', !product.is_visible);
    } else if (field === 'default-rate') {
      product.default_rate = numberOrNull(event.target.value);
    } else if (field === 'customer-rate') {
      product.customer_rate = numberOrNull(event.target.value);
    }
    state.dirty = true;
    updateSummary();
  }, true);

  document.addEventListener('change', function (event) {
    if (event.target.id !== 'catalog-party') return;
    if (state.dirty && !window.confirm('Discard unsaved changes and switch customer?')) {
      event.target.value = state.partyId;
      return;
    }
    state.partyId = event.target.value || '';
    state.search = '';
    var search = q('#catalog-search');
    if (search) search.value = '';
    loadProducts();
  });

  function boot() {
    injectMenuButtons();
    injectScreen();
    new MutationObserver(injectMenuButtons).observe(document.body, { childList: true, subtree: true });
  }

  window.KiranaCustomerCatalog = {
    open: openManager,
    close: closeManager,
    handleBack: function () {
      return closeManager(false);
    },
    isOpen: function () {
      return state.open;
    }
  };

  boot();
})();
