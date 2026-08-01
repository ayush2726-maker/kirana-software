(() => {
  'use strict';

  const ready = callback => {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback, { once: true });
    } else {
      callback();
    }
  };

  function ensureMessageBox(form) {
    let box = document.querySelector('#owner-login-message');
    if (!box) {
      box = document.createElement('div');
      box.id = 'owner-login-message';
      box.setAttribute('role', 'status');
      box.setAttribute('aria-live', 'polite');
      box.style.cssText = [
        'display:none',
        'margin:0 0 14px',
        'padding:12px 14px',
        'border-radius:12px',
        'font-size:14px',
        'font-weight:700',
        'line-height:1.4'
      ].join(';');
      form.parentElement?.insertBefore(box, form);
    }
    return box;
  }

  function showMessage(form, message, type = 'error') {
    const box = ensureMessageBox(form);
    box.textContent = message;
    box.style.display = 'block';
    box.style.background = type === 'success' ? '#e8f8ef' : type === 'info' ? '#e8f4fc' : '#fff0ef';
    box.style.color = type === 'success' ? '#157347' : type === 'info' ? '#075f91' : '#b42318';
    box.style.border = `1px solid ${type === 'success' ? '#b7e4c7' : type === 'info' ? '#b6dcf2' : '#ffc9c5'}`;
  }

  async function submitLogin(event) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    const form = event.currentTarget;
    const usernameInput = form.elements.username;
    const passwordInput = form.elements.password;
    const button = form.querySelector('button[type="submit"]');
    const username = String(usernameInput?.value || '').trim();
    const password = String(passwordInput?.value || '');

    if (!username) {
      showMessage(form, 'Enter your username.');
      usernameInput?.focus();
      return;
    }
    if (!password) {
      showMessage(form, 'Enter your PIN or password.');
      passwordInput?.focus();
      return;
    }

    const oldLabel = button?.textContent || 'Login';
    if (button) {
      button.disabled = true;
      button.textContent = 'Signing in...';
    }
    showMessage(form, 'Checking your login details...', 'info');

    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        cache: 'no-store',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ username, password })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.token) {
        throw new Error(data.detail || `Login failed (${response.status})`);
      }

      localStorage.setItem('ks_token', data.token);
      showMessage(form, 'Login successful. Opening your business dashboard...', 'success');
      window.setTimeout(() => {
        window.location.replace(`/?login=success&v=068&t=${Date.now()}`);
      }, 350);
    } catch (error) {
      const message = String(error?.message || 'Login failed. Please try again.');
      showMessage(
        form,
        message === 'Wrong username or password'
          ? 'The username or PIN is incorrect.'
          : message
      );
      if (button) {
        button.disabled = false;
        button.textContent = oldLabel;
      }
      passwordInput?.focus();
      passwordInput?.select?.();
    }
  }

  ready(() => {
    const auth = document.querySelector('#auth-screen');
    const form = document.querySelector('#login-form');
    const loginBox = document.querySelector('#login-box');
    if (!form) return;

    auth?.style.setProperty('pointer-events', 'auto', 'important');
    loginBox?.style.setProperty('pointer-events', 'auto', 'important');
    form.style.setProperty('pointer-events', 'auto', 'important');
    form.querySelectorAll('input,button').forEach(element => {
      element.style.setProperty('pointer-events', 'auto', 'important');
      element.style.setProperty('touch-action', 'manipulation', 'important');
    });

    const username = form.elements.username;
    const password = form.elements.password;
    if (username) username.setAttribute('autocomplete', 'username');
    if (password) {
      password.setAttribute('autocomplete', 'current-password');
      password.setAttribute('inputmode', 'numeric');
    }

    form.addEventListener('submit', submitLogin, true);

    const query = new URLSearchParams(window.location.search);
    if (query.get('login') === 'success') {
      const token = localStorage.getItem('ks_token');
      if (token) {
        fetch('/api/me', {
          cache: 'no-store',
          headers: { Authorization: `Bearer ${token}` }
        }).then(response => {
          if (!response.ok) throw new Error('Session validation failed');
          return response.json();
        }).then(() => {
          window.setTimeout(() => {
            const shell = document.querySelector('#app-shell');
            if (shell?.classList.contains('hidden')) {
              showMessage(form, 'Login is valid, but the dashboard script did not start. Reload this page once.', 'info');
            }
          }, 5000);
        }).catch(() => {
          localStorage.removeItem('ks_token');
        });
      }
    }
  });
})();
