(() => {
  let customerUrl = `${location.origin}/customer`;

  function token() {
    return localStorage.getItem('ks_token') || '';
  }

  function notify(message, error = false) {
    const box = document.querySelector('#toast');
    if (box) {
      box.textContent = message;
      box.className = `toast show${error ? ' error' : ''}`;
      setTimeout(() => { box.className = 'toast'; }, 3200);
      return;
    }
    if (error) alert(message);
  }

  function paintLink() {
    const target = document.querySelector('#customer-portal-url');
    if (target) target.textContent = customerUrl;
  }

  async function loadCustomerLink() {
    if (!token()) return customerUrl;
    try {
      const response = await fetch('/api/saas/me', {
        headers: { Authorization: `Bearer ${token()}` }
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || 'Customer link load nahi hua');
      const path = data.customer_order_path || (data.slug ? `/customer?shop=${encodeURIComponent(data.slug)}` : '/customer');
      customerUrl = `${location.origin}${path}`;
      paintLink();
    } catch (error) {
      console.warn('Customer link fix:', error);
    }
    return customerUrl;
  }

  document.addEventListener('click', event => {
    const openButton = event.target.closest('#open-order-center-drawer, #open-order-center-home, [data-order-tab="access"]');
    if (openButton) setTimeout(loadCustomerLink, 50);
  }, true);

  document.addEventListener('click', async event => {
    const button = event.target.closest('#copy-customer-link');
    if (!button) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    await loadCustomerLink();
    try {
      await navigator.clipboard.writeText(customerUrl);
      notify('Sahi customer order link copy ho gaya');
    } catch {
      prompt('Ye link customer ko bhejein:', customerUrl);
    }
  }, true);

  const observer = new MutationObserver(() => paintLink());
  observer.observe(document.documentElement, { childList: true, subtree: true });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadCustomerLink);
  } else {
    loadCustomerLink();
  }
})();
