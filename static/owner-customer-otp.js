(function () {
  'use strict';

  if (window.__kiranaCustomerOtpModuleLoaded) return;
  window.__kiranaCustomerOtpModuleLoaded = true;

  var requests = [];
  var loading = false;
  var initialized = false;
  var seenIds = new Set();
  var seenStorageKey = 'ks_seen_customer_otp_ids';
  var pollTimer = null;
  var lastRenderSignature = '';

  function one(selector, root) {
    return (root || document).querySelector(selector);
  }

  function all(selector, root) {
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

  function toast(message, isError) {
    var node = one('#toast') || one('#txn-toast');
    if (!node) {
      console[isError ? 'error' : 'log'](message);
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
    var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timeout = window.setTimeout(function () {
      if (controller) controller.abort();
    }, 8000);

    try {
      var response = await fetch(path, {
        method: config.method || 'GET',
        headers: { Accept: 'application/json' },
        credentials: 'include',
        cache: 'no-store',
        signal: controller ? controller.signal : undefined
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
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function loadSeenIds() {
    try {
      var values = JSON.parse(localStorage.getItem(seenStorageKey) || '[]');
      seenIds = new Set(Array.isArray(values) ? values.map(Number) : []);
    } catch (error) {
      seenIds = new Set();
    }
  }

  function saveSeenIds() {
    try {
      var values = Array.from(seenIds).slice(-300);
      localStorage.setItem(seenStorageKey, JSON.stringify(values));
    } catch (error) {
      console.error(error);
    }
  }

  function ensureBadge() {
    all('[data-page="orders"]').forEach(function (button) {
      var badge = one('.customer-otp-badge', button);
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'customer-otp-badge hidden';
        badge.setAttribute('aria-label', 'Pending OTP requests');
        button.appendChild(badge);
      }
      var nextText = String(requests.length);
      if (badge.textContent !== nextText) badge.textContent = nextText;
      var shouldHide = requests.length === 0;
      if (badge.classList.contains('hidden') !== shouldHide) {
        badge.classList.toggle('hidden', shouldHide);
      }
    });
  }

  function alertsSupported() {
    return typeof window.Notification !== 'undefined';
  }

  function alertButtonLabel() {
    if (!alertsSupported()) return 'In-App Alerts Active';
    if (Notification.permission === 'granted') return 'Phone Alerts Active';
    if (Notification.permission === 'denied') return 'Phone Alerts Blocked';
    return 'Enable Phone Alerts';
  }

  function updateAlertButton() {
    var button = one('[data-action="enable-customer-otp-alerts"]');
    if (!button) return;
    var label = alertButtonLabel();
    if (button.textContent !== label) button.textContent = label;
    button.disabled = alertsSupported() && Notification.permission === 'denied';
  }

  function ensurePanel() {
    var page = one('#page-orders');
    if (!page) return null;
    var existing = one('#customer-otp-panel', page);
    if (existing) {
      updateAlertButton();
      return existing;
    }

    var infoCard = one('.info-card', page);
    var panel = document.createElement('article');
    panel.id = 'customer-otp-panel';
    panel.className = 'card customer-otp-panel';
    panel.innerHTML =
      '<div class="customer-otp-heading">' +
        '<div><small>CUSTOMER REGISTRATION</small><h2>OTP Requests</h2><p>Send the OTP to the customer on WhatsApp. OTP is valid for 10 minutes.</p></div>' +
        '<div class="customer-otp-heading-actions">' +
          '<button type="button" data-action="enable-customer-otp-alerts">' + esc(alertButtonLabel()) + '</button>' +
          '<button type="button" data-action="refresh-customer-otps">Refresh</button>' +
        '</div>' +
      '</div>' +
      '<div id="customer-otp-list" class="customer-otp-list"><div class="customer-otp-empty">Loading OTP requests...</div></div>';

    if (infoCard && infoCard.parentNode) infoCard.parentNode.insertBefore(panel, infoCard.nextSibling);
    else page.appendChild(panel);
    updateAlertButton();
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

  function render(force) {
    var panel = ensurePanel();
    ensureBadge();
    if (!panel) return;
    var host = one('#customer-otp-list', panel);
    if (!host) return;

    var signature = JSON.stringify(requests.map(function (item) {
      return [item.id, item.status, item.expires_at, item.otp_code];
    }));
    if (!force && initialized && signature === lastRenderSignature) return;
    lastRenderSignature = signature;

    if (loading && !initialized) {
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

  function systemNotification(item) {
    var title = 'New Customer OTP Request';
    var body = (item.party_name || 'Customer') + ' · ' + (item.phone || '') + ' · OTP ' + (item.otp_code || '');

    try {
      if (window.KiranaNative && typeof window.KiranaNative.notifyOtp === 'function') {
        window.KiranaNative.notifyOtp(title, body);
        return;
      }
    } catch (error) {
      console.error(error);
    }

    if (alertsSupported() && Notification.permission === 'granted') {
      try {
        var notification = new Notification(title, {
          body: body,
          tag: 'customer-otp-' + Number(item.id),
          requireInteraction: true
        });
        notification.onclick = function () {
          window.focus();
          var orders = one('[data-page="orders"]');
          if (orders) orders.click();
          notification.close();
        };
      } catch (error) {
        console.error(error);
      }
    }
  }

  function announceNewRequests(nextRequests) {
    if (!initialized) {
      nextRequests.forEach(function (item) { seenIds.add(Number(item.id)); });
      saveSeenIds();
      return;
    }

    var fresh = nextRequests.filter(function (item) {
      return !seenIds.has(Number(item.id));
    });
    if (!fresh.length) return;

    fresh.forEach(function (item) {
      seenIds.add(Number(item.id));
      systemNotification(item);
    });
    saveSeenIds();

    var newest = fresh[0];
    toast('New OTP request: ' + (newest.party_name || 'Customer') + ' (' + (newest.phone || '') + ')');
    if (navigator.vibrate) navigator.vibrate([250, 120, 250]);
  }

  async function loadRequests(showErrors) {
    if (loading || document.hidden) return;
    loading = true;
    if (!initialized) render(true);
    try {
      var next = await api('/api/customer/otp-requests');
      next = Array.isArray(next) ? next : [];
      announceNewRequests(next);
      requests = next;
    } catch (error) {
      if (showErrors !== false && error.name !== 'AbortError') toast(error.message, true);
    } finally {
      loading = false;
      initialized = true;
      render(false);
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
      lastRenderSignature = '';
      render(true);
      toast('OTP request cancelled');
    } catch (error) {
      toast(error.message, true);
    }
  }

  async function enableAlerts() {
    if (!alertsSupported()) {
      toast('In-app OTP alerts are active.');
      return;
    }
    if (Notification.permission === 'denied') {
      toast('Phone notifications are blocked. Enable notifications for Kirana Software in phone settings.', true);
      return;
    }
    try {
      var permission = await Notification.requestPermission();
      updateAlertButton();
      toast(permission === 'granted' ? 'Phone OTP alerts enabled' : 'In-app alerts will continue');
    } catch (error) {
      toast('In-app OTP alerts are active');
    }
  }

  document.addEventListener('click', function (event) {
    var alerts = event.target.closest('[data-action="enable-customer-otp-alerts"]');
    if (alerts) {
      event.preventDefault();
      enableAlerts();
      return;
    }

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
        render(true);
        loadRequests(false);
      }, 120);
    }
  }, true);

  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) loadRequests(false);
  });

  window.addEventListener('pagehide', function () {
    if (pollTimer) window.clearInterval(pollTimer);
    pollTimer = null;
  }, { once: true });

  function boot() {
    loadSeenIds();
    ensurePanel();
    ensureBadge();
    loadRequests(false);
    pollTimer = window.setInterval(function () {
      loadRequests(false);
    }, 20000);
  }

  boot();
})();
