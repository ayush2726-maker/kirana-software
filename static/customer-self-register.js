(() => {
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

  if (!loginForm || !registerBox || !requestForm || !verifyForm || !loginButton || !registerButton) return;

  function showMessage(message, error = false) {
    const box = document.querySelector('#customer-toast');
    if (!box) {
      alert(message);
      return;
    }
    box.textContent = message;
    box.className = `customer-toast show${error ? ' error' : ''}`;
    setTimeout(() => { box.className = 'customer-toast'; }, 4000);
  }

  function showMode(mode) {
    const registering = mode === 'register';
    loginForm.classList.toggle('hidden', registering);
    registerBox.classList.toggle('hidden', !registering);
    loginButton.classList.toggle('active', !registering);
    registerButton.classList.toggle('active', registering);
    copy.textContent = registering
      ? 'Database wale mobile number se WhatsApp OTP lekar register karein.'
      : 'Apna registered mobile number aur PIN daalein.';
    if (registering && !shopSlug) {
      showMessage('Registration ke liye dukaan ka complete customer link use karein', true);
    }
  }

  function showRequestStep() {
    verifyForm.classList.add('hidden');
    requestForm.classList.remove('hidden');
  }

  function showVerifyStep() {
    requestForm.classList.add('hidden');
    verifyForm.classList.remove('hidden');
    verifyForm.querySelector('input[name="otp"]')?.focus();
  }

  loginButton.addEventListener('click', () => showMode('login'));
  registerButton.addEventListener('click', () => showMode('register'));
  requestAgain?.addEventListener('click', () => {
    requestedPhone = '';
    verifyForm.reset();
    showRequestStep();
  });

  requestForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (!shopSlug) {
      showMessage('Dukaan ka customer link galat hai', true);
      return;
    }
    const submit = requestForm.querySelector('button[type="submit"]');
    const form = new FormData(requestForm);
    requestedPhone = String(form.get('phone') || '').trim();
    submit.disabled = true;
    try {
      const response = await fetch('/api/customer/register/request-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: requestedPhone, shop_slug: shopSlug })
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || `OTP request failed (${response.status})`);
      showVerifyStep();
      showMessage(data?.message || 'OTP request dukaan ko mil gayi');
    } catch (error) {
      showMessage(error.message, true);
    } finally {
      submit.disabled = false;
    }
  });

  verifyForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (!requestedPhone) {
      showRequestStep();
      showMessage('Pehle mobile number se OTP request karein', true);
      return;
    }
    const submit = verifyForm.querySelector('button[type="submit"]');
    const form = new FormData(verifyForm);
    const pin = String(form.get('pin') || '');
    const confirmPin = String(form.get('confirm_pin') || '');
    if (pin !== confirmPin) {
      showMessage('PIN aur Confirm PIN match nahi kar rahe', true);
      return;
    }
    submit.disabled = true;
    try {
      const response = await fetch('/api/customer/register/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone: requestedPhone,
          shop_slug: shopSlug,
          otp: form.get('otp'),
          pin,
          confirm_pin: confirmPin
        })
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || `Verification failed (${response.status})`);
      localStorage.setItem('ks_customer_token', data.token);
      showMessage('OTP verify ho gaya. Account ready hai.');
      setTimeout(() => location.reload(), 500);
    } catch (error) {
      showMessage(error.message, true);
    } finally {
      submit.disabled = false;
    }
  });

  async function loadShopName() {
    if (!shopSlug) return;
    try {
      const response = await fetch(`/api/saas/business/${encodeURIComponent(shopSlug)}`);
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || 'Shop link galat hai');
      const title = document.querySelector('.customer-auth-card h1');
      if (title) title.textContent = data.business_name;
      document.title = `${data.business_name} - Customer Order`;
    } catch (error) {
      showMessage(error.message, true);
    }
  }

  showRequestStep();
  showMode(params.get('register') === '1' ? 'register' : 'login');
  loadShopName();
})();
