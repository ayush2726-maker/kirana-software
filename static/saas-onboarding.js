(() => {
  let saasInfo = null;

  function token() {
    return localStorage.getItem('ks_token') || '';
  }

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

  function toast(message, error = false) {
    const box = document.querySelector('#toast');
    if (!box) return;
    box.textContent = message;
    box.className = `toast show${error ? ' error' : ''}`;
    setTimeout(() => { box.className = 'toast'; }, 3500);
  }

  function injectSignup() {
    const loginBox = document.querySelector('#login-box');
    const authCard = document.querySelector('.auth-card');
    if (!loginBox || !authCard || document.querySelector('#saas-signup-box')) return;
    loginBox.insertAdjacentHTML('beforeend', `
      <div class="saas-login-divider"><span>ya</span></div>
      <button id="open-saas-signup" class="saas-open-signup" type="button">Apni Dukaan Ka Account Banayein</button>
      <small class="saas-trial-copy">30 din free trial · Alag customer order link · Koi card nahi</small>
    `);
    authCard.insertAdjacentHTML('beforeend', `
      <div id="saas-signup-box" class="hidden">
        <button id="back-saas-login" class="saas-back-login" type="button">← Login par wapas</button>
        <span class="eyebrow">NEW BUSINESS</span>
        <h2>Apna billing software shuru karein</h2>
        <form id="saas-signup-form" class="form-grid one">
          <label>Dukaan / Firm ka naam<input name="business_name" required minlength="2" /></label>
          <label>Owner name<input name="owner_name" /></label>
          <label>Mobile number<input name="phone" inputmode="tel" required /></label>
          <label>Address<textarea name="address" rows="2"></textarea></label>
          <label>GSTIN<input name="gstin" /></label>
          <label>Login username<input name="username" required minlength="3" autocomplete="username" /></label>
          <label>PIN / Password<input name="password" type="password" required minlength="4" autocomplete="new-password" /></label>
          <button class="btn primary wide" type="submit">30 Din Free Trial Start Karein</button>
        </form>
      </div>
    `);
    document.querySelector('#open-saas-signup')?.addEventListener('click', () => showSignup(true));
    document.querySelector('#back-saas-login')?.addEventListener('click', () => showSignup(false));
    document.querySelector('#saas-signup-form')?.addEventListener('submit', submitSignup);
  }

  function showSignup(open) {
    document.querySelector('#login-box')?.classList.toggle('hidden', open);
    document.querySelector('#setup-box')?.classList.add('hidden');
    document.querySelector('#saas-signup-box')?.classList.toggle('hidden', !open);
  }

  async function submitSignup(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = form.querySelector('button[type="submit"]');
    const data = Object.fromEntries(new FormData(form).entries());
    submit.disabled = true;
    try {
      const result = await api('/api/saas/register-business', { method: 'POST', body: data });
      localStorage.setItem('ks_token', result.token);
      localStorage.setItem('ks_new_shop_slug', result.slug);
      toast('Business account ready hai. Login kiya ja raha hai.');
      setTimeout(() => location.reload(), 450);
    } catch (error) {
      toast(error.message, true);
    } finally {
      submit.disabled = false;
    }
  }

  async function loadSaasInfo() {
    if (!token()) return;
    try {
      saasInfo = await api('/api/saas/me');
      injectPlanCard();
      patchCustomerLink();
    } catch (_) {
      // Existing app remains usable even if subscription metadata is unavailable.
    }
  }

  function fullCustomerUrl() {
    if (!saasInfo) return `${location.origin}/customer`;
    return `${location.origin}${saasInfo.customer_order_path}`;
  }

  function injectPlanCard() {
    const settings = document.querySelector('#page-settings');
    if (!settings || !saasInfo || document.querySelector('#saas-plan-card')) return;
    const status = String(saasInfo.subscription_status || '').toUpperCase();
    const days = saasInfo.days_left == null ? '' : `${saasInfo.days_left} din baaki`;
    settings.insertAdjacentHTML('afterbegin', `
      <article id="saas-plan-card" class="card saas-plan-card">
        <div class="saas-plan-head">
          <div><small>BUSINESS SOFTWARE PLAN</small><h2>${escapeHtml(saasInfo.business_name)}</h2></div>
          <span class="saas-status ${escapeHtml(saasInfo.subscription_status)}">${escapeHtml(status)}</span>
        </div>
        <div class="saas-plan-grid">
          <div><small>Plan</small><strong>${escapeHtml(saasInfo.plan)}</strong></div>
          <div><small>Validity</small><strong>${escapeHtml(days || 'Active')}</strong></div>
        </div>
        <label class="saas-shop-link"><small>Customer Order Link</small><div><input id="saas-shop-link-input" readonly value="${escapeHtml(fullCustomerUrl())}" /><button id="copy-saas-shop-link" type="button">Copy</button></div></label>
      </article>
    `);
    document.querySelector('#copy-saas-shop-link')?.addEventListener('click', copyCustomerLink);
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[char]));
  }

  async function copyCustomerLink(event) {
    event?.preventDefault();
    event?.stopImmediatePropagation();
    const url = fullCustomerUrl();
    try {
      await navigator.clipboard.writeText(url);
      toast('Unique customer order link copy ho gaya');
    } catch (_) {
      prompt('Customer ko ye link bhejein:', url);
    }
  }

  function patchCustomerLink() {
    if (!saasInfo) return;
    const text = document.querySelector('#customer-portal-url');
    if (text) text.textContent = fullCustomerUrl();
    const input = document.querySelector('#saas-shop-link-input');
    if (input) input.value = fullCustomerUrl();
  }

  document.addEventListener('click', event => {
    const copyButton = event.target.closest('#copy-customer-link');
    if (copyButton && saasInfo) copyCustomerLink(event);
    if (event.target.closest('[data-go="settings"]')) setTimeout(injectPlanCard, 100);
    if (event.target.closest('#open-order-center-home') || event.target.closest('#open-order-center-drawer') || event.target.closest('[data-order-tab="access"]')) {
      setTimeout(patchCustomerLink, 140);
    }
  }, true);

  const observer = new MutationObserver(() => {
    injectSignup();
    injectPlanCard();
    patchCustomerLink();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
  injectSignup();
  loadSaasInfo();
})();
