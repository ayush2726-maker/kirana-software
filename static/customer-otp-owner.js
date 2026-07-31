(() => {
  const moneyToken = () => localStorage.getItem('ks_token') || '';
  let refreshTimer = null;

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (moneyToken()) headers.Authorization = `Bearer ${moneyToken()}`;
    if (options.body) {
      headers['Content-Type'] = 'application/json';
      options.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
    }
    const response = await fetch(path, { ...options, headers });
    const data = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.detail || `Request failed (${response.status})`);
    return data;
  }

  function safe(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[char]));
  }

  function notify(message, error = false) {
    const toast = document.querySelector('#toast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = `toast show${error ? ' error' : ''}`;
    setTimeout(() => { toast.className = 'toast'; }, 3200);
  }

  function ensurePanel() {
    const accessTab = document.querySelector('#order-tab-access');
    if (!accessTab || document.querySelector('#customer-otp-owner-card')) return false;
    accessTab.insertAdjacentHTML('afterbegin', `
      <article id="customer-otp-owner-card" class="customer-otp-owner-card">
        <div class="customer-otp-owner-head">
          <div><small>FREE WHATSAPP VERIFICATION</small><h3>Pending Registration OTP</h3></div>
          <button id="refresh-customer-otps" type="button">Refresh</button>
        </div>
        <p>Customer request karega. Neeche WhatsApp button se OTP bhejein. OTP 10 minute valid rahega.</p>
        <div id="customer-otp-owner-list" class="customer-otp-owner-list">
          <div class="otp-owner-empty">OTP requests load ho rahi hain…</div>
        </div>
      </article>
    `);
    document.querySelector('#refresh-customer-otps')?.addEventListener('click', loadRequests);
    loadRequests();
    return true;
  }

  async function loadRequests() {
    if (!moneyToken()) return;
    const list = document.querySelector('#customer-otp-owner-list');
    if (!list) return;
    try {
      const rows = await api('/api/customer/otp-requests');
      render(rows);
    } catch (error) {
      list.innerHTML = `<div class="otp-owner-empty error">${safe(error.message)}</div>`;
    }
  }

  function render(rows) {
    const list = document.querySelector('#customer-otp-owner-list');
    if (!list) return;
    if (!rows.length) {
      list.innerHTML = '<div class="otp-owner-empty">Abhi koi pending registration OTP nahi hai</div>';
      return;
    }
    list.innerHTML = rows.map(row => {
      const expires = new Date(row.expires_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
      return `
        <div class="customer-otp-row">
          <div class="customer-otp-info">
            <strong>${safe(row.party_name)}</strong>
            <small>${safe(row.phone)} · Expires ${safe(expires)}</small>
          </div>
          <div class="customer-otp-code">${safe(row.otp_code)}</div>
          <div class="customer-otp-actions">
            <a href="${safe(row.whatsapp_url)}" target="_blank" rel="noopener">WhatsApp par bhejein</a>
            <button data-cancel-customer-otp="${row.id}" type="button">Cancel</button>
          </div>
        </div>
      `;
    }).join('');
    list.querySelectorAll('[data-cancel-customer-otp]').forEach(button => {
      button.addEventListener('click', () => cancelRequest(Number(button.dataset.cancelCustomerOtp)));
    });
  }

  async function cancelRequest(requestId) {
    try {
      await api(`/api/customer/otp-requests/${requestId}`, { method: 'DELETE' });
      notify('OTP request cancel ho gayi');
      await loadRequests();
    } catch (error) {
      notify(error.message, true);
    }
  }

  document.addEventListener('click', event => {
    if (event.target.closest('[data-order-tab="access"]') || event.target.closest('#open-order-center-home') || event.target.closest('#open-order-center-drawer')) {
      setTimeout(() => {
        ensurePanel();
        loadRequests();
      }, 120);
    }
  });

  const observer = new MutationObserver(() => ensurePanel());
  observer.observe(document.documentElement, { childList: true, subtree: true });
  ensurePanel();
  refreshTimer = setInterval(() => {
    const modal = document.querySelector('#order-center-modal:not(.hidden)');
    const accessPanel = document.querySelector('#order-tab-access.active');
    if (modal && accessPanel) loadRequests();
  }, 30000);
  window.addEventListener('beforeunload', () => clearInterval(refreshTimer));
})();
