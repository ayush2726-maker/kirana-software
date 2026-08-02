from __future__ import annotations

from fastapi import Request
from fastapi.responses import Response

from backend.app import STATIC_DIR, app
import backend.customer_self_register_ext as customer_register


CUSTOMER_ORDER_JS = STATIC_DIR / "customer-order.js"
CUSTOMER_LOGIN_VERSION = "110"


_original_registration_html = customer_register.customer_registration_html


def customer_registration_html_v110() -> str:
    html = _original_registration_html()
    for old_version in ("060", "061", "062", "109"):
        html = html.replace(
            f"/customer-order.js?v={old_version}",
            f"/customer-order.js?v={CUSTOMER_LOGIN_VERSION}",
        )
    return html


customer_register.customer_registration_html = customer_registration_html_v110


def patched_customer_order_script() -> str:
    script = CUSTOMER_ORDER_JS.read_text(encoding="utf-8")

    script = script.replace(
        "  const sourceText = source => ({ fixed: 'Aapka Fixed Rate', last_bill: 'Aapke Last Bill Ka Rate', default: 'Current Rate' }[source] || 'Rate');",
        "  const sourceText = source => ({ fixed: 'Aapka Special Rate', recent_15_days: 'Last 15 Days Bill Rate', catalog: 'Default Customer Rate', last_bill: 'Aapke Last Bill Ka Rate', default: 'Current Rate' }[source] || 'Rate');",
        1,
    )

    old_api = """  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (state.token) headers.Authorization = `Bearer ${state.token}`;
    if (options.body) {
      headers['Content-Type'] = 'application/json';
      options.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
    }
    const response = await fetch(path, { ...options, headers });
    const data = await response.json().catch(() => null);
    if (response.status === 401 && path !== '/api/customer/login') {
      logout(false);
      throw new Error('Login expired. Dobara login karein.');
    }
    if (!response.ok) throw new Error(data?.detail || 'Request failed');
    return data;
  }
"""
    new_api = """  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    const requestToken = state.token;
    if (requestToken && path !== '/api/customer/login') headers.Authorization = `Bearer ${requestToken}`;
    if (options.body) {
      headers['Content-Type'] = 'application/json';
      options.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
    }
    const response = await fetch(path, { ...options, headers, cache: 'no-store' });
    const data = await response.json().catch(() => null);
    if (response.status === 401 && path !== '/api/customer/login') {
      const staleResponse = Boolean(requestToken && requestToken !== state.token);
      if (!staleResponse) logout(false);
      const authError = new Error('Login expired. Please sign in again.');
      authError.code = staleResponse ? 'STALE_AUTH' : 'AUTH_EXPIRED';
      throw authError;
    }
    if (!response.ok) throw new Error(data?.detail || 'Request failed');
    return data;
  }
"""
    if old_api not in script:
        raise RuntimeError("Customer API patch target not found")
    script = script.replace(old_api, new_api, 1)

    script = script.replace(
        "    } catch (error) {\n      toast(error.message, true);\n    }\n  }\n\n  function bind()",
        "    } catch (error) {\n      if (error && error.code !== 'STALE_AUTH') toast(error.message, true);\n    }\n  }\n\n  function bind()",
        1,
    )

    old_login = """  async function login(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const result = await api('/api/customer/login', {
        method: 'POST',
        body: { phone: form.get('phone'), pin: form.get('pin'), shop_slug: shopSlug }
      });
      state.token = result.token;
      localStorage.setItem('ks_customer_token', state.token);
      localStorage.setItem('ks_customer_shop', result.shop_slug || shopSlug);
      await enterApp();
    } catch (error) {
      toast(error.message, true);
    }
  }
"""
    new_login = """  async function login(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const button = formElement.querySelector('button[type="submit"]');
    const previousLabel = button ? button.textContent : 'Login';
    if (button) {
      button.disabled = true;
      button.textContent = 'Signing in...';
    }

    // Remove only the old local session before requesting a fresh token.
    // A delayed response from the old session is ignored by api() above.
    state.token = '';
    localStorage.removeItem('ks_customer_token');
    localStorage.removeItem('ks_customer_shop');

    try {
      const result = await api('/api/customer/login', {
        method: 'POST',
        body: { phone: form.get('phone'), pin: form.get('pin'), shop_slug: shopSlug }
      });
      if (!result || !result.token) throw new Error('Login could not be completed. Please try again.');
      state.token = result.token;
      localStorage.setItem('ks_customer_token', state.token);
      localStorage.setItem('ks_customer_shop', result.shop_slug || shopSlug);
      await enterApp();
      const pinInput = formElement.querySelector('[name="pin"]');
      if (pinInput) pinInput.value = '';
      toast('Login successful');
    } catch (error) {
      if (!error || error.code !== 'STALE_AUTH') toast(error.message || 'Login failed', true);
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = previousLabel;
      }
    }
  }
"""
    if old_login not in script:
        raise RuntimeError("Customer login patch target not found")
    script = script.replace(old_login, new_login, 1)

    return script


@app.middleware("http")
async def serve_race_safe_customer_login(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if request.method == "GET" and path == "/customer-order.js":
        return Response(
            patched_customer_order_script(),
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return await call_next(request)
