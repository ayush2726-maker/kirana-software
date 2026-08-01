from __future__ import annotations

from fastapi.responses import HTMLResponse

import backend.owner_session_ext as owner_session


ORIGINAL_DASHBOARD_PAGE = owner_session._dashboard_page

INLINE_NAVIGATION = r"""
<style id="ks-inline-navigation-style">
  .hidden{display:none!important;pointer-events:none!important}
  dialog:not([open]){display:none!important;pointer-events:none!important}
  #drawer-backdrop.hidden{display:none!important;pointer-events:none!important}
  #app-shell, #app-shell *{touch-action:manipulation}
  .page{display:none}
  .page.active{display:block}
</style>
<script id="ks-inline-navigation-script">
(() => {
  if (window.__ksInlineNavigationInstalled) return;
  window.__ksInlineNavigationInstalled = true;

  const one = (selector, root = document) => root.querySelector(selector);
  const all = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const safeText = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[ch]);
  const money = value => `₹${Number(value || 0).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`;

  const closeDrawer = () => {
    one('#side-drawer')?.classList.remove('open');
    one('#drawer-backdrop')?.classList.add('hidden');
  };

  async function getJson(path) {
    const response = await fetch(path, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
      cache: 'no-store'
    });
    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    return response.json();
  }

  async function loadDashboardFallback() {
    try {
      const data = await getJson('/api/dashboard');
      const values = {
        '#dash-receivable': money(data.receivable),
        '#dash-payable': money(data.payable),
        '#dash-month-sale': money(data.sales_month),
        '#dash-purchases': money(data.purchases_month),
        '#dash-expenses': money(data.expenses_month),
        '#dash-bank': money(data.bank_balance),
        '#dash-cash': money(data.cash_balance),
        '#dash-stock-value': money(data.stock_value),
        '#dash-item-count': String(data.item_count || 0),
        '#dash-open-count': String(data.open_documents?.count || 0),
        '#dash-open-amount': money(data.open_documents?.amount)
      };
      Object.entries(values).forEach(([selector, value]) => {
        const node = one(selector);
        if (node) node.textContent = value;
      });
    } catch (error) {
      console.error('Safe dashboard load failed', error);
    }
  }

  async function loadItemsFallback() {
    const container = one('#items-cards');
    if (!container || container.dataset.safeLoaded === '1' || container.children.length) return;
    try {
      const items = await getJson('/api/items');
      container.innerHTML = items.slice(0, 250).map(item => `
        <article class="card" style="padding:16px;margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:center">
            <div><b>${safeText(item.name)}</b><small style="display:block;color:#687785;margin-top:4px">${safeText(item.size || '')} ${safeText(item.unit || '')}</small></div>
            <strong>${money(item.sale_price)}</strong>
          </div>
        </article>`).join('') || '<div class="card" style="padding:24px;text-align:center">No items found</div>';
      container.dataset.safeLoaded = '1';
    } catch (error) {
      console.error('Safe item load failed', error);
    }
  }

  async function loadPartiesFallback() {
    const container = one('#parties-cards');
    if (!container || container.dataset.safeLoaded === '1' || container.children.length) return;
    try {
      const parties = await getJson('/api/parties');
      container.innerHTML = parties.slice(0, 250).map(party => `
        <article class="card" style="padding:16px;margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:center">
            <div><b>${safeText(party.name)}</b><small style="display:block;color:#687785;margin-top:4px">${safeText(party.phone || party.party_type || '')}</small></div>
            <strong>${money(party.balance)}</strong>
          </div>
        </article>`).join('') || '<div class="card" style="padding:24px;text-align:center">No parties found</div>';
      container.dataset.safeLoaded = '1';
    } catch (error) {
      console.error('Safe party load failed', error);
    }
  }

  async function loadSaleBasics() {
    try {
      const [parties, items] = await Promise.all([
        getJson('/api/parties'),
        getJson('/api/items')
      ]);
      const partySelect = one('#sale-party');
      if (partySelect && partySelect.options.length <= 1) {
        partySelect.innerHTML = '<option value="">Cash / Walk-in Customer</option>' + parties
          .filter(party => party.party_type !== 'supplier')
          .map(party => `<option value="${Number(party.id)}">${safeText(party.name)}</option>`)
          .join('');
      }
      window.__ksFallbackItems = items;
      window.__ksFallbackParties = parties;
    } catch (error) {
      console.error('Safe sale data load failed', error);
    }
  }

  function activatePage(page) {
    const target = one(`#page-${CSS.escape(page)}`);
    if (!target) return false;

    all('.page').forEach(node => node.classList.toggle('active', node === target));
    all('.bottom-nav button').forEach(node => node.classList.toggle('active', node.dataset.go === page));
    document.body.classList.toggle('sale-focus', page === 'sale');
    document.body.classList.toggle('purchase-focus', page === 'purchase');
    document.body.classList.toggle('return-focus', page === 'return');
    document.body.classList.toggle('billing-focus', ['sale', 'purchase', 'return'].includes(page));
    closeDrawer();
    window.scrollTo(0, 0);

    try {
      history.replaceState(null, '', `/?session=1&page=${encodeURIComponent(page)}&v=076`);
    } catch (_) {}

    if (page === 'dashboard') loadDashboardFallback();
    if (page === 'items') loadItemsFallback();
    if (page === 'parties') loadPartiesFallback();
    if (page === 'sale') loadSaleBasics();
    return true;
  }

  window.__ksActivatePage = activatePage;

  document.addEventListener('click', event => {
    const go = event.target.closest?.('[data-go]');
    if (go && activatePage(go.dataset.go || '')) {
      event.preventDefault();
      return;
    }

    if (event.target.closest?.('#desktop-menu-btn, #profile-btn')) {
      event.preventDefault();
      one('#side-drawer')?.classList.add('open');
      one('#drawer-backdrop')?.classList.remove('hidden');
      return;
    }

    if (event.target.closest?.('#drawer-backdrop')) {
      event.preventDefault();
      closeDrawer();
      return;
    }

    if (event.target.closest?.('#open-txn-launcher, #open-txn-launcher-2, [data-menu-launch]')) {
      const dialog = one('#txn-launcher');
      if (dialog?.showModal) {
        event.preventDefault();
        dialog.showModal();
      }
      return;
    }

    const close = event.target.closest?.('.close-modal');
    if (close) {
      const dialog = close.closest('dialog');
      if (dialog?.close) {
        event.preventDefault();
        dialog.close();
      }
    }
  }, true);

  // Server already authenticated this page. Keep it visible even if the large
  // legacy dashboard bundle fails before completing startup.
  one('#auth-screen')?.classList.add('hidden');
  one('#app-shell')?.classList.remove('hidden');

  const requested = new URLSearchParams(location.search).get('page');
  if (requested && one(`#page-${CSS.escape(requested)}`)) activatePage(requested);
})();
</script>
"""


def patched_dashboard_page(token: str) -> HTMLResponse:
    response = ORIGINAL_DASHBOARD_PAGE(token)
    page = bytes(response.body).decode("utf-8", errors="replace")
    if "ks-inline-navigation-script" not in page:
        page = page.replace("</body>", INLINE_NAVIGATION + "</body>", 1)

    headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in {"content-length", "set-cookie"}
    }
    headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    headers["X-Kirana-Inline-Navigation"] = "076"

    patched = HTMLResponse(page, status_code=response.status_code, headers=headers)
    owner_session._set_session_cookie(patched, token)
    return patched


owner_session._dashboard_page = patched_dashboard_page
