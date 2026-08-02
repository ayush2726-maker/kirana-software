(() => {
  'use strict';

  const loginForm = document.querySelector('#customer-login-form');
  const registerBox = document.querySelector('#customer-register-box');
  const requestForm = document.querySelector('#customer-otp-request-form');
  const verifyForm = document.querySelector('#customer-otp-verify-form');
  const loginButton = document.querySelector('#customer-show-login');
  const registerButton = document.querySelector('#customer-show-register');
  const requestAgain = document.querySelector('#customer-request-again');
  const copy = document.querySelector('#customer-auth-copy');
  const params = new URLSearchParams(location.search);
  const shopSlug = String(params.get('shop') || '').trim();
  let requestedPhone = '';
  let requestMode = 'register';

  if (!loginForm || !registerBox || !requestForm || !verifyForm || !loginButton || !registerButton) return;

  function showMessage(message, error = false) {
    const box = document.querySelector('#customer-toast');
    if (!box) {
      window.alert(message);
      return;
    }
    box.textContent = String(message || 'Done');
    box.className = `customer-toast show${error ? ' error' : ''}`;
    window.clearTimeout(showMessage.timer);
    showMessage.timer = window.setTimeout(() => {
      box.className = 'customer-toast';
    }, 5000);
  }

  function setBusy(form, busy, busyLabel) {
    const button = form.querySelector('button[type="submit"]');
    if (!button) return;
    if (!button.dataset.originalLabel) button.dataset.originalLabel = button.textContent;
    button.disabled = busy;
    button.textContent = busy ? busyLabel : button.dataset.originalLabel;
  }

  function showMode(mode) {
    const registering = mode === 'register';
    loginForm.classList.toggle('hidden', registering);
    registerBox.classList.toggle('hidden', !registering);
    loginButton.classList.toggle('active', !registering);
    registerButton.classList.toggle('active', registering);
    copy.textContent = registering
      ? 'Use your saved mobile number to register or reset your PIN with WhatsApp OTP.'
      : 'Enter your registered mobile number and PIN.';
    if (registering && !shopSlug) {
      showMessage('Open the complete customer link shared by the shop.', true);
    }
  }

  function showRequestStep() {
    verifyForm.classList.add('hidden');
    requestForm.classList.remove('hidden');
    const phoneInput = requestForm.querySelector('input[name="phone"]');
    if (phoneInput && requestedPhone) phoneInput.value = requestedPhone;
  }

  function showVerifyStep() {
    requestForm.classList.add('hidden');
    verifyForm.classList.remove('hidden');
    const heading = verifyForm.querySelector('.customer-register-step-message');
    if (heading) {
      heading.textContent = requestMode === 'reset'
        ? 'Enter the OTP to set a new PIN.'
        : 'Enter the OTP to create your account and PIN.';
    }
    verifyForm.querySelector('input[name="otp"]')?.focus();
  }

  loginButton.addEventListener('click', () => showMode('login'));
  registerButton.addEventListener('click', () => showMode('register'));
  requestAgain?.addEventListener('click', () => {
    verifyForm.reset();
    showRequestStep();
  });

  requestForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (!shopSlug) {
      showMessage('The shop customer link is incomplete.', true);
      return;
    }

    const form = new FormData(requestForm);
    requestedPhone = String(form.get('phone') || '').replace(/\D+/g, '').slice(-10);
    if (requestedPhone.length !== 10) {
      showMessage('Enter a valid 10 digit mobile number.', true);
      return;
    }

    setBusy(requestForm, true, 'Sending Request...');
    try {
      const response = await fetch('/api/customer/register/request-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        cache: 'no-store',
        body: JSON.stringify({ phone: requestedPhone, shop_slug: shopSlug })
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || `OTP request failed (${response.status})`);
      requestMode = data?.mode === 'reset' ? 'reset' : 'register';
      showVerifyStep();
      showMessage(data?.message || 'OTP request sent to the shop.');
    } catch (error) {
      showMessage(error?.message || 'OTP request could not be sent.', true);
    } finally {
      setBusy(requestForm, false, '');
    }
  });

  verifyForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (!requestedPhone) {
      showRequestStep();
      showMessage('Request an OTP with your mobile number first.', true);
      return;
    }

    const form = new FormData(verifyForm);
    const otp = String(form.get('otp') || '').replace(/\D+/g, '').slice(0, 6);
    const pin = String(form.get('pin') || '');
    const confirmPin = String(form.get('confirm_pin') || '');
    if (otp.length !== 6) {
      showMessage('Enter the 6 digit OTP.', true);
      return;
    }
    if (pin.length < 4) {
      showMessage('PIN must contain at least 4 digits.', true);
      return;
    }
    if (pin !== confirmPin) {
      showMessage('PIN and Confirm PIN do not match.', true);
      return;
    }

    setBusy(verifyForm, true, 'Verifying...');
    try {
      const response = await fetch('/api/customer/register/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        cache: 'no-store',
        body: JSON.stringify({
          phone: requestedPhone,
          shop_slug: shopSlug,
          otp,
          pin,
          confirm_pin: confirmPin
        })
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || `Verification failed (${response.status})`);
      if (!data?.token) throw new Error('Account was verified but login session was not created. Please try again.');

      localStorage.setItem('ks_customer_token', data.token);
      localStorage.setItem('ks_customer_shop', data.shop_slug || shopSlug);
      const message = data.pin_reset
        ? 'PIN reset successful. Opening your account...'
        : 'Registration successful. Opening your account...';
      showMessage(message);
      verifyForm.reset();
      window.setTimeout(() => {
        location.replace(`/customer?shop=${encodeURIComponent(data.shop_slug || shopSlug)}`);
      }, 500);
    } catch (error) {
      showMessage(error?.message || 'OTP verification failed.', true);
    } finally {
      setBusy(verifyForm, false, '');
    }
  });

  async function loadShopName() {
    if (!shopSlug) return;
    try {
      const response = await fetch(`/api/saas/business/${encodeURIComponent(shopSlug)}`, { cache: 'no-store' });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || 'Shop link is invalid.');
      const title = document.querySelector('.customer-auth-card h1');
      if (title) title.textContent = data.business_name;
      document.title = `${data.business_name} - Customer Order`;
    } catch (error) {
      showMessage(error?.message || 'Shop details could not be loaded.', true);
    }
  }

  const verifyHelp = document.createElement('p');
  verifyHelp.className = 'customer-register-step-message';
  verifyHelp.textContent = 'Enter the OTP sent by the shop on WhatsApp.';
  verifyForm.prepend(verifyHelp);

  registerButton.textContent = 'Register / Reset PIN';
  showRequestStep();
  showMode(params.get('register') === '1' ? 'register' : 'login');
  loadShopName();
})();
