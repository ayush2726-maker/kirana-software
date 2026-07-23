(() => {
  'use strict';

  const CATEGORY_META = {
    general: { title: 'General', icon: '⚙', subtitle: 'Language, currency, security and godown' },
    transaction: { title: 'Transaction', icon: '₹', subtitle: 'Sale, purchase, barcode and round-off' },
    print: { title: 'Invoice Print', icon: '▣', subtitle: 'A4, thermal, header, totals and footer' },
    tax: { title: 'Taxes & GST', icon: '%', subtitle: 'GST, HSN/SAC, CESS, TCS and TDS' },
    users: { title: 'User Management', icon: '👥', subtitle: 'Owner, manager, cashier and viewer' },
    messaging: { title: 'Transaction SMS', icon: '💬', subtitle: 'Invoice message and sharing preferences' },
    reminders: { title: 'Reminders', icon: '🔔', subtitle: 'Payment and service reminders' },
    party: { title: 'Party', icon: '◉', subtitle: 'GSTIN, grouping and shipping address' },
    item: { title: 'Item', icon: '◇', subtitle: 'Barcode, stock, units, category and tax' },
  };

  const FIELD_META = {
    general: [
      ['language', 'App Language', 'select', ['English', 'Hindi']],
      ['currency', 'Business Currency', 'select', ['INR', 'USD', 'AED']],
      ['decimal_places', 'Decimal Places', 'number'],
      ['date_format', 'Date Format', 'select', ['dd/MM/yyyy', 'MM/dd/yyyy', 'yyyy-MM-dd']],
      ['warn_unsaved', 'Show warning for unsaved changes', 'toggle'],
      ['theme', 'Kirana Theme', 'select', ['Modern', 'Compact', 'Classic']],
      ['passcode_lock', 'Passcode / Fingerprint lock', 'toggle'],
      ['multifirm', 'Multi-firm Settings', 'toggle'],
      ['godown_management', 'Godown management & stock transfer', 'toggle'],
    ],
    transaction: [
      ['invoice_header', 'Invoice # / Number', 'toggle'],
      ['cash_sale_default', 'Cash Sale by default', 'toggle'],
      ['party_details', 'Party details in invoice', 'toggle'],
      ['transaction_time', 'Add Time on transactions', 'toggle'],
      ['print_time', 'Print Time on invoice', 'toggle'],
      ['inclusive_tax', 'Inclusive / Exclusive tax on rate', 'toggle'],
      ['display_purchase_price', 'Display Purchase Price', 'toggle'],
      ['last_sale_prices', 'Show last 5 sale prices', 'toggle'],
      ['free_quantity', 'Free item quantity', 'toggle'],
      ['barcode_scanning', 'Barcode scanning in items', 'toggle'],
      ['item_discount', 'Transaction-wise item discount', 'toggle'],
      ['round_off', 'Round off transaction amount', 'toggle'],
      ['round_nearest', 'Round-off nearest value', 'select', ['1', '5', '10']],
      ['link_payments', 'Link payments to invoices', 'toggle'],
      ['payment_terms', 'Due dates and payment terms', 'toggle'],
      ['terms_conditions', 'Terms & Conditions', 'toggle'],
      ['profit_while_sale', 'Show profit while making sale', 'toggle'],
      ['reverse_charge', 'Reverse Charge', 'toggle'],
      ['state_of_supply', 'State of Supply', 'toggle'],
      ['eway_bill', 'E-Way Bill No.', 'toggle'],
    ],
    print: [
      ['mode', 'Default Print Type', 'select', ['regular', 'thermal']],
      ['regular_size', 'Regular Page Size', 'select', ['A4', 'A5']],
      ['thermal_size', 'Thermal Paper Size', 'select', ['80mm', '58mm']],
      ['orientation', 'Orientation', 'select', ['portrait', 'landscape']],
      ['text_size', 'Print Text Size', 'select', ['small', 'medium', 'large']],
      ['repeat_header', 'Repeat header on all pages', 'toggle'],
      ['company_name', 'Print Company Name', 'toggle'],
      ['company_logo', 'Company Logo', 'toggle'],
      ['address', 'Address', 'toggle'],
      ['email', 'Email', 'toggle'],
      ['phone', 'Phone number', 'toggle'],
      ['gstin', 'GSTIN on Sale', 'toggle'],
      ['total_quantity', 'Total Item Quantity', 'toggle'],
      ['decimals', 'Amount with Decimal', 'toggle'],
      ['received_amount', 'Received amount', 'toggle'],
      ['balance_amount', 'Balance amount', 'toggle'],
      ['party_balance', 'Print Current Balance of Party', 'toggle'],
      ['tax_details', 'Tax details', 'toggle'],
      ['amount_grouping', 'Amount Grouping', 'toggle'],
      ['amount_words', 'Amount in words', 'toggle'],
      ['terms_conditions', 'Terms & Conditions', 'toggle'],
      ['received_by', 'Print Received by details', 'toggle'],
      ['delivered_by', 'Print Delivered by details', 'toggle'],
      ['signature', 'Print Signature Text', 'toggle'],
      ['payment_mode', 'Payment mode', 'toggle'],
      ['page_numbers', 'Print Page Numbers', 'toggle'],
    ],
    tax: [
      ['gst', 'GST', 'toggle'],
      ['hsn_sac', 'HSN/SAC Code', 'toggle'],
      ['cess', 'Additional CESS', 'toggle'],
      ['reverse_charge', 'Reverse Charge', 'toggle'],
      ['state_of_supply', 'State of Supply', 'toggle'],
      ['eway_bill', 'E-Way Bill No.', 'toggle'],
      ['composite_scheme', 'Composite Scheme', 'toggle'],
      ['tcs', 'Enable TCS', 'toggle'],
      ['tds', 'Enable TDS', 'toggle'],
    ],
    party: [
      ['gstin', 'GSTIN Number', 'toggle'],
      ['grouping', 'Party Grouping', 'toggle'],
      ['additional_fields', 'Party Additional Fields', 'toggle'],
      ['shipping_address', 'Party Shipping Address', 'toggle'],
    ],
    item: [
      ['enabled', 'Enable Item', 'toggle'],
      ['item_type', 'Item Type', 'select', ['Products and Services', 'Products', 'Services']],
      ['barcode_scanning', 'Barcode scanning for items', 'toggle'],
      ['scanner_type', 'Barcode scanner type', 'select', ['camera', 'usb']],
      ['stock_maintenance', 'Stock maintenance', 'toggle'],
      ['manufacturing', 'Manufacturing', 'toggle'],
      ['units', 'Item Units', 'toggle'],
      ['default_unit', 'Default Unit', 'toggle'],
      ['category', 'Item Category', 'toggle'],
      ['party_wise_rate', 'Party-wise item rate', 'toggle'],
      ['wholesale_price', 'Wholesale Price', 'toggle'],
      ['quantity_decimals', 'Quantity decimal places', 'number'],
      ['item_tax', 'Item-wise tax', 'toggle'],
      ['tax_on_mrp', 'Calculate Tax based on MRP', 'toggle'],
      ['item_discount', 'Item-wise discount', 'toggle'],
      ['update_sale_price', 'Update Sale Price from Transaction', 'toggle'],
      ['description', 'Description', 'toggle'],
      ['hsn_sac', 'HSN/SAC Code', 'toggle'],
      ['cess', 'Additional CESS', 'toggle'],
    ],
    messaging: [
      ['send_to_party', 'Send to party', 'toggle'],
      ['copy_to_self', 'Send SMS Copy to Self', 'toggle'],
      ['transaction_update', 'Send Transaction Update message', 'toggle'],
      ['show_balance', "Show Party's Current Balance", 'toggle'],
      ['show_web_invoice', 'Show web invoice link', 'toggle'],
      ['auto_share', 'Automatically share invoices', 'toggle'],
      ['sale', 'Sale', 'toggle'],
      ['purchase', 'Purchase', 'toggle'],
      ['sale_return', 'Sale Return', 'toggle'],
      ['purchase_return', 'Purchase Return', 'toggle'],
      ['estimate', 'Estimate', 'toggle'],
      ['proforma', 'Proforma Invoice', 'toggle'],
      ['payment_in', 'Payment-In', 'toggle'],
      ['payment_out', 'Payment-Out', 'toggle'],
      ['sale_order', 'Sale Order', 'toggle'],
      ['purchase_order', 'Purchase Order', 'toggle'],
      ['delivery_challan', 'Delivery Challan', 'toggle'],
      ['cancelled_invoice', 'Cancelled Invoice', 'toggle'],
      ['template', 'Customize message', 'textarea'],
    ],
  };

  let settings = null;
  let dialog = null;
  let activeCategory = '';

  const token = () => localStorage.getItem('ks_token') || '';
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));

  async function request(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (token()) headers.Authorization = `Bearer ${token()}`;
    if (options.body && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      options.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
    }
    const response = await fetch(path, { ...options, headers });
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.detail || `Request failed (${response.status})`);
    return data;
  }

  function notify(message, isError = false) {
    if (typeof toast === 'function') return toast(message, isError);
    alert(message);
  }

  function renderSettingsHome() {
    const page = document.querySelector('#page-settings');
    if (!page || document.querySelector('#advanced-settings-home')) return;

    const home = document.createElement('div');
    home.id = 'advanced-settings-home';
    home.innerHTML = `
      <div class="page-heading advanced-settings-heading">
        <div><h1>Advanced Settings</h1><p>Billing, print, GST, users and reminders</p></div>
      </div>
      <article class="card vy-settings-menu">
        ${Object.entries(CATEGORY_META).map(([key, meta]) => `
          <button type="button" data-advanced-setting="${key}">
            <span class="vy-setting-icon">${meta.icon}</span>
            <span><b>${escapeHtml(meta.title)}</b><small>${escapeHtml(meta.subtitle)}</small></span>
            <i>›</i>
          </button>
        `).join('')}
      </article>
      <div class="settings-section-label">Business & Data</div>
    `;
    page.prepend(home);

    dialog = document.createElement('dialog');
    dialog.id = 'advanced-settings-dialog';
    dialog.className = 'advanced-settings-dialog';
    dialog.innerHTML = '<div id="advanced-settings-dialog-body"></div>';
    document.body.appendChild(dialog);
  }

  async function loadSettings(force = false) {
    if (settings && !force) return settings;
    try {
      const response = await request('/api/settings/advanced');
      settings = response.settings || {};
      localStorage.setItem('ks_advanced_settings', JSON.stringify(settings));
      applySettings();
      return settings;
    } catch (error) {
      try { settings = JSON.parse(localStorage.getItem('ks_advanced_settings') || '{}'); } catch { settings = {}; }
      if (force) notify(error.message, true);
      applySettings();
      return settings;
    }
  }

  async function saveSettings() {
    const response = await request('/api/settings/advanced', { method: 'PUT', body: { settings } });
    settings = response.settings || settings;
    localStorage.setItem('ks_advanced_settings', JSON.stringify(settings));
    applySettings();
    notify('Settings saved');
  }

  function fieldHtml(category, field) {
    const [key, label, type, options] = field;
    const value = settings?.[category]?.[key];
    if (type === 'toggle') {
      return `<label class="vy-setting-row"><span><b>${escapeHtml(label)}</b></span><input type="checkbox" data-setting-key="${key}" ${value ? 'checked' : ''}><i class="vy-switch"></i></label>`;
    }
    if (type === 'select') {
      return `<label class="vy-setting-row"><span><b>${escapeHtml(label)}</b></span><select data-setting-key="${key}">${options.map(option => `<option value="${escapeHtml(option)}" ${String(value) === String(option) ? 'selected' : ''}>${escapeHtml(option)}</option>`).join('')}</select></label>`;
    }
    if (type === 'number') {
      return `<label class="vy-setting-row"><span><b>${escapeHtml(label)}</b></span><input class="vy-number" type="number" min="0" max="6" data-setting-key="${key}" value="${Number(value ?? 0)}"></label>`;
    }
    return `<label class="vy-setting-textarea"><b>${escapeHtml(label)}</b><textarea data-setting-key="${key}" rows="4">${escapeHtml(value || '')}</textarea></label>`;
  }

  async function openCategory(category) {
    activeCategory = category;
    await loadSettings();
    if (category === 'users') return openUsers();
    if (category === 'reminders') return openReminders();
    const meta = CATEGORY_META[category];
    const fields = FIELD_META[category] || [];
    const body = document.querySelector('#advanced-settings-dialog-body');
    body.innerHTML = `
      <header class="vy-detail-header">
        <button type="button" data-settings-close>‹</button>
        <div><h2>${escapeHtml(meta.title)}</h2><small>${escapeHtml(meta.subtitle)}</small></div>
        <button type="button" class="vy-save-button" data-settings-save>Save</button>
      </header>
      <div class="vy-detail-list">${fields.map(field => fieldHtml(category, field)).join('')}</div>
      ${category === 'messaging' ? '<p class="vy-settings-note">Message preferences save ho jayengi. Automatic SMS bhejne ke liye baad mein SMS provider/API connect karna hoga; WhatsApp/Web Share app se share kiya ja sakega.</p>' : ''}
    `;
    dialog.showModal();
  }

  async function openUsers() {
    const body = document.querySelector('#advanced-settings-dialog-body');
    body.innerHTML = `
      <header class="vy-detail-header"><button type="button" data-settings-close>‹</button><div><h2>User Management</h2><small>Alag login aur role permissions</small></div></header>
      <form id="managed-user-form" class="vy-user-form">
        <label>Username<input name="username" minlength="3" required></label>
        <label>PIN / Password<input name="password" type="password" minlength="4" required></label>
        <label>Role<select name="role"><option value="cashier">Cashier</option><option value="manager">Manager</option><option value="viewer">Viewer</option></select></label>
        <button class="btn primary" type="submit">Add User</button>
      </form>
      <div id="managed-users-list" class="vy-managed-list"><p>Loading…</p></div>
    `;
    dialog.showModal();
    await loadUsers();
  }

  async function loadUsers() {
    const list = document.querySelector('#managed-users-list');
    if (!list) return;
    try {
      const users = await request('/api/settings/users');
      list.innerHTML = users.map(user => `
        <div class="vy-managed-row">
          <span><b>${escapeHtml(user.username)}</b><small>${escapeHtml(user.role)}</small></span>
          ${user.role === 'owner' ? '<em>Owner</em>' : `<button type="button" data-delete-user="${user.id}">Delete</button>`}
        </div>
      `).join('') || '<p>No users</p>';
    } catch (error) {
      list.innerHTML = `<p>${escapeHtml(error.message)}</p>`;
    }
  }

  async function openReminders() {
    const body = document.querySelector('#advanced-settings-dialog-body');
    body.innerHTML = `
      <header class="vy-detail-header"><button type="button" data-settings-close>‹</button><div><h2>Reminders</h2><small>Payment and service follow-up</small></div></header>
      <div class="vy-reminder-tabs"><button class="active" type="button">Payment Reminders</button><button type="button">Service Reminders</button></div>
      <form id="reminder-form" class="vy-user-form">
        <label>Type<select name="reminder_type"><option value="payment">Payment</option><option value="service">Service</option></select></label>
        <label>Title<input name="title" required placeholder="Payment follow-up"></label>
        <label>Due date<input name="due_date" type="date" required></label>
        <label class="full">Message<textarea name="message" rows="2" placeholder="Reminder message"></textarea></label>
        <button class="btn primary" type="submit">Add Reminder</button>
      </form>
      <div id="reminders-list" class="vy-managed-list"><p>Loading…</p></div>
    `;
    const due = body.querySelector('[name="due_date"]');
    due.value = new Date().toISOString().slice(0, 10);
    dialog.showModal();
    await loadReminders();
  }

  async function loadReminders() {
    const list = document.querySelector('#reminders-list');
    if (!list) return;
    try {
      const reminders = await request('/api/settings/reminders');
      list.innerHTML = reminders.map(row => `
        <div class="vy-managed-row">
          <span><b>${escapeHtml(row.title)}</b><small>${escapeHtml(row.reminder_type)} · ${escapeHtml(row.due_date)}${row.party_name ? ` · ${escapeHtml(row.party_name)}` : ''}</small></span>
          <button type="button" data-delete-reminder="${row.id}">Delete</button>
        </div>
      `).join('') || '<p>Abhi koi reminder nahi hai.</p>';
    } catch (error) {
      list.innerHTML = `<p>${escapeHtml(error.message)}</p>`;
    }
  }

  function applySettings() {
    if (!settings) return;
    const general = settings.general || {};
    const item = settings.item || {};
    const party = settings.party || {};
    const transaction = settings.transaction || {};
    const print = settings.print || {};

    document.documentElement.dataset.kiranaTheme = String(general.theme || 'Modern').toLowerCase();

    const toggleField = (selector, show) => {
      const field = document.querySelector(selector);
      const label = field?.closest('label');
      if (label) label.classList.toggle('settings-field-hidden', show === false);
    };
    toggleField('#item-form [name="barcode"]', item.barcode_scanning);
    toggleField('#item-form [name="category"]', item.category);
    toggleField('#item-form [name="unit"]', item.units);
    toggleField('#item-form [name="hsn"]', item.hsn_sac);
    toggleField('#item-form [name="gst_rate"]', item.item_tax);
    toggleField('#party-form [name="gstin"]', party.gstin);

    const printSelect = document.querySelector('#invoice-print-size');
    if (printSelect) {
      printSelect.value = print.mode === 'thermal'
        ? (print.thermal_size === '58mm' ? 'print-58mm' : 'print-80mm')
        : 'print-a4';
    }

    if (transaction.cash_sale_default) {
      const cash = document.querySelector('#sale-cash-toggle');
      if (cash && !cash.classList.contains('active')) cash.click();
    }

    window.onbeforeunload = general.warn_unsaved ? () => {
      try {
        const hasCart = (state?.saleCart?.length || state?.purchaseCart?.length || state?.returnCart?.length);
        return hasCart ? 'Unsaved bill changes' : undefined;
      } catch { return undefined; }
    } : null;
  }

  document.addEventListener('click', async event => {
    const categoryButton = event.target.closest('[data-advanced-setting]');
    if (categoryButton) {
      await openCategory(categoryButton.dataset.advancedSetting);
      return;
    }
    if (event.target.closest('[data-settings-close]')) {
      dialog?.close();
      return;
    }
    if (event.target.closest('[data-settings-save]')) {
      const body = document.querySelector('#advanced-settings-dialog-body');
      body.querySelectorAll('[data-setting-key]').forEach(input => {
        const key = input.dataset.settingKey;
        let value = input.type === 'checkbox' ? input.checked : input.value;
        if (input.type === 'number') value = Number(value || 0);
        settings[activeCategory][key] = value;
      });
      await saveSettings().catch(error => notify(error.message, true));
      return;
    }
    const deleteUser = event.target.closest('[data-delete-user]');
    if (deleteUser) {
      if (!confirm('Is user ko delete karna hai?')) return;
      await request(`/api/settings/users/${deleteUser.dataset.deleteUser}`, { method: 'DELETE' }).then(loadUsers).catch(error => notify(error.message, true));
      return;
    }
    const deleteReminder = event.target.closest('[data-delete-reminder]');
    if (deleteReminder) {
      await request(`/api/settings/reminders/${deleteReminder.dataset.deleteReminder}`, { method: 'DELETE' }).then(loadReminders).catch(error => notify(error.message, true));
    }
  });

  document.addEventListener('submit', async event => {
    if (event.target.id === 'managed-user-form') {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(event.target));
      await request('/api/settings/users', { method: 'POST', body: data })
        .then(() => { event.target.reset(); notify('User added'); return loadUsers(); })
        .catch(error => notify(error.message, true));
    }
    if (event.target.id === 'reminder-form') {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(event.target));
      await request('/api/settings/reminders', { method: 'POST', body: data })
        .then(() => { event.target.reset(); event.target.elements.due_date.value = new Date().toISOString().slice(0, 10); notify('Reminder added'); return loadReminders(); })
        .catch(error => notify(error.message, true));
    }
  });

  const init = () => {
    renderSettingsHome();
    loadSettings();
    const settingsPageObserver = new MutationObserver(() => {
      if (document.querySelector('#page-settings.active')) loadSettings();
    });
    const page = document.querySelector('#page-settings');
    if (page) settingsPageObserver.observe(page, { attributes: true, attributeFilter: ['class'] });
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(init, 50));
  else setTimeout(init, 50);
})();
