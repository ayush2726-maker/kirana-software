(function () {
  'use strict';

  var requests = [];
  var loading = false;

  function one(selector, root) {
    return (root || document).querySelector(selector);
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
    }, 4000);
  }

  async function api(path, options) {
    var config = options || {};
    var response = await fetch(path, {
      method: config.method || 'GET',
      headers: { Accept: 'application/json' },
      credentials: 'include',
      cache: 'no-store'
    });
    var data = response.status === 204 ? null : await response.json().catch(function () { return null; });
    if (response.status === 401) {
      window.location.replace('/owner-login');
      throw new Error('Owner session expired');
    }
    if (!response.ok) {
      throw new Error(data && data.detail ? data.detail : 'Request failed (' + response.status + ')');
    }
    return data;
  }

  function ensurePanel() {
    var page = one('#page-orders');
    if (!page) return null;
    var existing = one('#customer-otp-panel', page);
    if (existing) return existing;

    var infoCard = one('.info-card', page);
    var panel = document.createElement('article');
    panel.id = 'customer-otp-panel';
    panel.className = 'card customer-otp-panel';
    panel.innerHTML =
      '<div class="customer-otp-heading">' +
        '<div><small>CUSTOMER REGISTRATION</small><h2>OTP Requests</h2><p>Send the OTP to the customer on WhatsApp. OTP is valid for 10 minutes.</p></div>' +
        '<button type="button" data-action="refresh-customer-otps">Refresh</button>' +
      '</div>' +
      '<div id="customer-otp-list" class="customer-otp-list"><div class="customer-otp-empty">Loading OTP requests...</div></div>';

    if (infoCard && infoCard.parentNode) infoCard.parentNode.insertBefore(panel, infoCard.nextSibling);
    else page.appendChild(panel);
    return panel;
  }

  function remainingText(expiresAt) {
    var expires = new Date(expiresAt);
    if (Number.isNaN(expires.getTime())) return 'Expires soon';
    var seconds = Math.max(0, Math.floor((expires.getTime() - Date.now()) / 1000));
    var minutes = Math.floor(seconds / 60);
    var rest = seconds % 60;
    return minutes + 'm ' + rest + 's remaining';
  }

  function render() {
    var panel = ensurePanel();
    if (!panel) return;
    var host = one('#customer-otp-list', panel);
    if (!host) return;

    if (loading) {
      host.innerHTML = '<div class="customer-otp-empty">Loading OTP requests...</div>';
      return;
    }
    if (!requests.length) {
      host.innerHTML = '<div class="customer-otp-empty">No pending OTP requests</div>';
      return;
    }

    host.innerHTML = requests.map(function (item) {
      return '<section class="customer-otp-card" data-otp-id="' + Number(item.id) + '">' +
        '<div class="customer-otp-main">' +
          '<div><h3>' + esc(item.party_name || 'Customer') + '</h3><p>' + esc(item.phone || '') + '</p><small>' + esc(remainingText(item.expires_at)) + '</small></div>' +
          '<div class="customer-otp-code"><small>OTP</small><strong>' + esc(item.otp_code || '') + '</strong></div>' +
        '</div>' +
        '<div class="customer-otp-actions">' +
          '<button type="button" class="customer-otp-whatsapp" data-otp-whatsapp="' + Number(item.id) + '">Send OTP on WhatsApp</button>' +
          '<button type="button" class="customer-otp-cancel" data-otp-cancel="' + Number(item.id) + '">Cancel</button>' +
        '</div>' +
      '</section>';
    }).join('');
  }

  async function loadRequests(showErrors) {
    if (loading) return;
    loading = true;
    render();
    try {
      requests = await api('/api/customer/otp-requests');
    } catch (error) {
      requests = [];
      if (showErrors !== false) toast(error.message, true);
    } finally {
      loading = false;
      render();
    }
  }

  function requestById(id) {
    return requests.find(function (item) {
      return Number(item.id) === Number(id);
    }) || null;
  }

  function sendWhatsapp(id) {
    var item = requestById(id);
    if (!item) return;
    if (!item.whatsapp_url) {
      toast('WhatsApp link is not available for this request', true);
      return;
    }
    window.location.href = item.whatsapp_url;
  }

  async function cancelRequest(id) {
    var item = requestById(id);
    if (!item) return;
    if (!window.confirm('Cancel OTP request for ' + (item.party_name || 'this customer') + '?')) return;
    try {
      await api('/api/customer/otp-requests/' + Number(id), { method: 'DELETE' });
      requests = requests.filter(function (row) { return Number(row.id) !== Number(id); });
      render();
      toast('OTP request cancelled');
    } catch (error) {
      toast(error.message, true);
    }
  }

  document.addEventListener('click', function (event) {
    var refresh = event.target.closest('[data-action="refresh-customer-otps"]');
    if (refresh) {
      event.preventDefault();
      loadRequests(true);
      return;
    }

    var whatsapp = event.target.closest('[data-otp-whatsapp]');
    if (whatsapp) {
      event.preventDefault();
      sendWhatsapp(Number(whatsapp.getAttribute('data-otp-whatsapp')));
      return;
    }

    var cancel = event.target.closest('[data-otp-cancel]');
    if (cancel) {
      event.preventDefault();
      cancelRequest(Number(cancel.getAttribute('data-otp-cancel')));
      return;
    }

    var ordersButton = event.target.closest('[data-page="orders"]');
    if (ordersButton) {
      window.setTimeout(function () {
        ensurePanel();
        loadRequests(false);
      }, 120);
    }
  }, true);

  function boot() {
    ensurePanel();
    loadRequests(false);
    window.setInterval(function () {
      var page = one('#page-orders');
      if (page && page.classList.contains('active')) loadRequests(false);
    }, 30000);
    new MutationObserver(function () {
      ensurePanel();
    }).observe(document.body, { childList: true, subtree: true });
  }

  boot();
})();
