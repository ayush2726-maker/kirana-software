(function () {
  'use strict';

  var shareInfo = null;

  function one(selector, root) {
    return (root || document).querySelector(selector);
  }

  async function api(path) {
    var response = await fetch(path, {
      headers: { Accept: 'application/json' },
      credentials: 'include',
      cache: 'no-store'
    });
    var data = await response.json().catch(function () { return null; });
    if (response.status === 401) {
      window.location.replace('/owner-login');
      throw new Error('Owner session expired');
    }
    if (!response.ok || !data) {
      throw new Error(data && data.detail ? data.detail : 'Customer share details could not be loaded');
    }
    return data;
  }

  function toast(message, isError) {
    var node = one('#toast') || one('#txn-toast');
    if (!node) {
      window.alert(message);
      return;
    }
    node.textContent = String(message || 'Done');
    node.className = (node.id === 'txn-toast' ? 'txn-toast' : 'toast') + ' show' + (isError ? ' error' : '');
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(function () {
      node.className = node.id === 'txn-toast' ? 'txn-toast' : 'toast';
    }, 3500);
  }

  function absoluteCustomerLink(path) {
    if (/^https?:\/\//i.test(String(path || ''))) return String(path);
    return window.location.origin + (String(path || '').charAt(0) === '/' ? String(path) : '/' + String(path || 'customer'));
  }

  function buildMessage(info, link) {
    var shop = String(info.business_name || 'our shop').trim();
    return [
      'Namaste 🙏',
      '',
      shop + ' se ghar baithe order karein.',
      '',
      'Neeche diye gaye link par apne registered mobile number se Login ya Register karein, products select karein aur apna order place karein. Aapke liye lagu rates app mein automatically dikh jayenge.',
      '',
      'Order Link:',
      link,
      '',
      '— ' + shop
    ].join('\n');
  }

  function ensureShareButton() {
    var input = one('#customer-link');
    if (!input) return;
    var card = input.closest('.info-card');
    if (!card || one('[data-action="share-customer-whatsapp"]', card)) return;

    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'customer-whatsapp-share';
    button.setAttribute('data-action', 'share-customer-whatsapp');
    button.innerHTML = '<span aria-hidden="true">☏</span><b>Share on WhatsApp</b>';
    card.appendChild(button);
  }

  async function loadShareInfo() {
    ensureShareButton();
    try {
      shareInfo = await api('/api/customer/share-info');
      var link = absoluteCustomerLink(shareInfo.customer_order_path || '/customer');
      var input = one('#customer-link');
      if (input) input.value = link;
    } catch (error) {
      console.error(error);
      toast(error.message, true);
    }
  }

  function shareOnWhatsApp() {
    if (!shareInfo) {
      loadShareInfo().then(function () {
        if (shareInfo) shareOnWhatsApp();
      });
      return;
    }
    var link = absoluteCustomerLink(shareInfo.customer_order_path || '/customer');
    var message = buildMessage(shareInfo, link);
    window.location.href = 'https://wa.me/?text=' + encodeURIComponent(message);
  }

  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-action="share-customer-whatsapp"]');
    if (!button) return;
    event.preventDefault();
    shareOnWhatsApp();
  }, true);

  function boot() {
    ensureShareButton();
    loadShareInfo();
    new MutationObserver(ensureShareButton).observe(document.body, { childList: true, subtree: true });
  }

  boot();
})();
