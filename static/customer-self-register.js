(() => {
  const loginForm = document.querySelector('#customer-login-form');
  const registerForm = document.querySelector('#customer-register-form');
  const loginButton = document.querySelector('#customer-show-login');
  const registerButton = document.querySelector('#customer-show-register');
  const copy = document.querySelector('#customer-auth-copy');

  if (!loginForm || !registerForm || !loginButton || !registerButton) return;

  function showMode(mode) {
    const registering = mode === 'register';
    loginForm.classList.toggle('hidden', registering);
    registerForm.classList.toggle('hidden', !registering);
    loginButton.classList.toggle('active', !registering);
    registerButton.classList.toggle('active', registering);
    copy.textContent = registering
      ? 'Database mein saved mobile number se apna account register karein.'
      : 'Apna registered mobile number aur PIN daalein.';
  }

  function showMessage(message, error = false) {
    const box = document.querySelector('#customer-toast');
    if (!box) {
      alert(message);
      return;
    }
    box.textContent = message;
    box.className = `customer-toast show${error ? ' error' : ''}`;
    setTimeout(() => { box.className = 'customer-toast'; }, 3500);
  }

  loginButton.addEventListener('click', () => showMode('login'));
  registerButton.addEventListener('click', () => showMode('register'));

  registerForm.addEventListener('submit', async event => {
    event.preventDefault();
    const submit = registerForm.querySelector('button[type="submit"]');
    const form = new FormData(registerForm);
    const pin = String(form.get('pin') || '');
    const confirmPin = String(form.get('confirm_pin') || '');
    if (pin !== confirmPin) {
      showMessage('PIN aur Confirm PIN match nahi kar rahe', true);
      return;
    }

    submit.disabled = true;
    try {
      const response = await fetch('/api/customer/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone: form.get('phone'),
          pin,
          confirm_pin: confirmPin
        })
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || `Registration failed (${response.status})`);
      localStorage.setItem('ks_customer_token', data.token);
      showMessage('Registration ho gaya. Login kiya ja raha hai.');
      setTimeout(() => location.reload(), 500);
    } catch (error) {
      showMessage(error.message, true);
    } finally {
      submit.disabled = false;
    }
  });

  const params = new URLSearchParams(location.search);
  showMode(params.get('register') === '1' ? 'register' : 'login');
})();
