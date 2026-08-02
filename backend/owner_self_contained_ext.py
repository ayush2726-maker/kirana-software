from __future__ import annotations

import re
from pathlib import PurePosixPath

from fastapi import Request
from fastapi.responses import HTMLResponse

from backend.app import STATIC_DIR, app
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.owner_boot_recovery_ext as boot_recovery
import backend.stable_owner_app_ext as stable_owner


SELF_CONTAINED_VERSION = "116"
_ASSEMBLED_OWNER_PAGE = stable_owner.stable_owner_page

# Match local assets regardless of attribute ordering or extra attributes.
_STYLESHEET_RE = re.compile(
    r'<link\b(?=[^>]*\brel=["\']stylesheet["\'])(?=[^>]*\bhref=["\']/([^"\'?]+)(?:\?[^"\']*)?["\'])[^>]*>',
    re.IGNORECASE,
)
_SCRIPT_RE = re.compile(
    r'<script\b(?=[^>]*\bsrc=["\']/([^"\'?]+)(?:\?[^"\']*)?["\'])[^>]*>\s*</script>',
    re.IGNORECASE,
)

# This runtime is deliberately independent of owner-stable.js. It guarantees
# that navigation and the read-only business data still work even when one of
# the feature bundles throws an error on a particular Android WebView.
OWNER_SAFETY_RUNTIME = r"""
<script id="kirana-owner-safety-runtime">
(function () {
  'use strict';
  if (window.__kiranaOwnerSafetyRuntime) return;
  window.__kiranaOwnerSafetyRuntime = true;
  window.__kiranaOwnerBundleLoaded = true;
  window.__kiranaOwnerBootReady = true;

  var safetyState = { activity: [], items: [], parties: [], dashboard: null };

  function one(selector, root) {
    return (root || document).querySelector(selector);
  }
  function all(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }
  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char];
    });
  }
  function num(value) {
    var parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  function money(value) {
    return '₹' + num(value).toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }
  function setText(selector, value) {
    var node = one(selector);
    if (node) node.textContent = value;
  }
  function toast(message, isError) {
    var node = one('#toast');
    if (!node) return;
    node.textContent = String(message || 'Done');
    node.className = 'toast show' + (isError ? ' error' : '');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(function () { node.className = 'toast'; }, 3500);
  }
  function empty(container, message) {
    if (container) container.innerHTML = '<div class="empty-state">' + esc(message) + '</div>';
  }

  async function requestJson(path) {
    var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timer = setTimeout(function () { if (controller) controller.abort(); }, 9000);
    try {
      var response = await fetch(path, {
        credentials: 'include',
        cache: 'no-store',
        headers: { Accept: 'application/json' },
        signal: controller ? controller.signal : undefined
      });
      if (response.status === 401) {
        location.replace('/owner-login');
        throw new Error('Session expired');
      }
      var data = await response.json().catch(function () { return null; });
      if (!response.ok) throw new Error(data && data.detail ? data.detail : 'Request failed (' + response.status + ')');
      return data;
    } finally {
      clearTimeout(timer);
    }
  }

  function activityTitle(row) {
    return row.title || row.party_name || row.ref || row.invoice_no || 'Transaction';
  }
  function activityRef(row) {
    return row.ref || row.invoice_no || row.kind || '';
  }
  function activityDate(row) {
    return row.entry_date || row.invoice_date || row.created_at || '';
  }
  function activityAmount(row) {
    return row.amount != null ? row.amount : row.total;
  }
  function activityCard(row) {
    var kind = String(row.kind || 'transaction').toLowerCase();
    return '<article class="transaction-card"><div class="row-top"><div><h3>' +
      esc(activityTitle(row)) + '</h3><small>' + esc(activityRef(row)) + ' · ' +
      esc(activityDate(row)) + '</small></div><strong>' + money(activityAmount(row)) +
      '</strong></div><span class="status-pill ' + esc(kind) + '">' +
      esc(kind.replace(/_/g, ' ').toUpperCase()) + '</span></article>';
  }

  function renderActivity() {
    var container = one('#activity-list');
    if (!container) return;
    var input = one('#activity-search');
    var query = String(input && input.value || '').trim().toLowerCase();
    var rows = safetyState.activity.filter(function (row) {
      return !query || (activityTitle(row) + ' ' + activityRef(row)).toLowerCase().indexOf(query) >= 0;
    }).slice(0, 60);
    if (!rows.length) return empty(container, 'No transactions found');
    container.innerHTML = rows.map(activityCard).join('');
  }

  function renderTransactions() {
    var container = one('#transactions-list');
    if (!container) return;
    var input = one('#transaction-search');
    var query = String(input && input.value || '').trim().toLowerCase();
    var rows = safetyState.activity.filter(function (row) {
      return !query || (activityTitle(row) + ' ' + activityRef(row)).toLowerCase().indexOf(query) >= 0;
    });
    if (!rows.length) return empty(container, 'No matching transactions');
    container.innerHTML = rows.map(activityCard).join('');
  }

  function renderItems() {
    var container = one('#items-list');
    if (!container) return;
    var input = one('#item-search');
    var query = String(input && input.value || '').trim().toLowerCase();
    var rows = safetyState.items.filter(function (item) {
      return !query || [item.name, item.size, item.sku, item.category].join(' ').toLowerCase().indexOf(query) >= 0;
    });
    if (!rows.length) return empty(container, 'No items found');
    container.innerHTML = rows.map(function (item) {
      return '<article class="item-card"><div class="row-top"><div><h3>' + esc(item.name) +
        '</h3><small>' + esc(item.size || item.unit || '') + ' · ' + esc(item.sku || '') +
        '</small></div><strong>' + money(item.sale_price) + '</strong></div>' +
        '<span class="status-pill">Stock ' + esc(item.stock) + ' ' + esc(item.unit || '') +
        '</span><div class="row-actions"><button data-action="edit-item" data-id="' +
        Number(item.id) + '">Edit Item</button></div></article>';
    }).join('');
  }

  function renderParties() {
    var container = one('#parties-list');
    if (!container) return;
    var input = one('#party-search');
    var query = String(input && input.value || '').trim().toLowerCase();
    var rows = safetyState.parties.filter(function (party) {
      return !query || [party.name, party.phone, party.type].join(' ').toLowerCase().indexOf(query) >= 0;
    });
    if (!rows.length) return empty(container, 'No parties found');
    container.innerHTML = rows.map(function (party) {
      return '<article class="party-card"><div class="row-top"><div><h3>' + esc(party.name) +
        '</h3><small>' + esc(party.phone || party.type || '') + '</small></div><strong>' +
        money(party.balance) + '</strong></div><span class="status-pill">' +
        esc(String(party.type || 'customer').toUpperCase()) + '</span><div class="row-actions">' +
        '<button data-action="edit-party" data-id="' + Number(party.id) + '">Edit Party</button></div></article>';
    }).join('');

    var saleParty = one('#sale-party');
    if (saleParty && saleParty.options.length <= 1) {
      saleParty.innerHTML = '<option value="">Cash / Walk-in Customer</option>' +
        safetyState.parties.filter(function (party) {
          return party.type === 'customer' || party.type === 'both';
        }).map(function (party) {
          return '<option value="' + Number(party.id) + '">' + esc(party.name) + '</option>';
        }).join('');
    }
  }

  function renderDashboard() {
    var data = safetyState.dashboard || {};
    setText('#dash-receivable', money(data.receivable));
    setText('#dash-payable', money(data.payable));
    setText('#dash-sales', money(data.sales_month));
    setText('#dash-purchases', money(data.purchases_month));
    setText('#dash-cash', money(data.cash_balance));
    setText('#dash-stock', money(data.stock_value));
    var recent = one('#dashboard-activity');
    var rows = (data.activity || []).slice(0, 8);
    if (!rows.length) empty(recent, 'No recent activity');
    else recent.innerHTML = rows.map(function (row) {
      return '<div class="compact-row"><div><b>' + esc(activityTitle(row)) + '</b><small>' +
        esc(activityRef(row)) + '</small></div><strong>' + money(activityAmount(row)) + '</strong></div>';
    }).join('');
  }

  function showPage(pageName) {
    var page = one('#page-' + pageName);
    if (!page) return false;
    all('.page').forEach(function (node) { node.classList.toggle('active', node === page); });
    all('.bottom-nav [data-page]').forEach(function (button) {
      button.classList.toggle('active', button.getAttribute('data-page') === pageName);
    });
    try { history.replaceState(null, '', '/?page=' + encodeURIComponent(pageName) + '&build=116'); } catch (ignore) {}
    window.scrollTo(0, 0);
    if (pageName === 'home') renderActivity();
    if (pageName === 'transactions') renderTransactions();
    if (pageName === 'items') renderItems();
    if (pageName === 'parties') renderParties();
    if (pageName === 'dashboard') renderDashboard();
    return true;
  }

  async function loadSafetyData() {
    var results = await Promise.allSettled([
      requestJson('/api/me'),
      requestJson('/api/items?limit=2000'),
      requestJson('/api/parties'),
      requestJson('/api/activity?limit=150'),
      requestJson('/api/dashboard')
    ]);
    if (results[0].status === 'fulfilled') {
      var me = results[0].value || {};
      var business = me.business || {};
      setText('#business-name', business.name || 'Kirana Software');
      setText('#business-subtitle', business.phone || 'Billing, Inventory & Accounts');
      setText('#profile-button', String(business.owner_name || business.name || 'A').charAt(0).toUpperCase());
      var form = one('#business-form');
      if (form) {
        ['name', 'owner_name', 'phone', 'gstin', 'address', 'invoice_prefix'].forEach(function (key) {
          if (form.elements[key]) form.elements[key].value = business[key] == null ? '' : business[key];
        });
      }
    }
    if (results[1].status === 'fulfilled') safetyState.items = results[1].value || [];
    if (results[2].status === 'fulfilled') safetyState.parties = results[2].value || [];
    if (results[3].status === 'fulfilled') safetyState.activity = results[3].value || [];
    if (results[4].status === 'fulfilled') safetyState.dashboard = results[4].value || {};
    renderActivity();
    renderTransactions();
    renderItems();
    renderParties();
    renderDashboard();
    var failed = results.filter(function (result) { return result.status === 'rejected'; });
    if (failed.length === results.length) toast('Server data could not load. Tap Dashboard to retry.', true);
  }

  function start() {
    var loading = one('#app-loading');
    var app = one('#app');
    if (loading) loading.classList.add('hidden');
    if (app) app.classList.remove('hidden');
    var date = one('#sale-date');
    if (date && !date.value) date.value = new Date().toISOString().slice(0, 10);
    var link = one('#customer-link');
    if (link && !link.value) link.value = location.origin + '/customer';

    document.addEventListener('click', function (event) {
      var button = event.target.closest && event.target.closest('[data-page]');
      if (!button) return;
      var pageName = button.getAttribute('data-page');
      if (showPage(pageName)) event.preventDefault();
    }, true);

    var activitySearch = one('#activity-search');
    if (activitySearch) activitySearch.addEventListener('input', renderActivity);
    var transactionSearch = one('#transaction-search');
    if (transactionSearch) transactionSearch.addEventListener('input', renderTransactions);
    var itemSearch = one('#item-search');
    if (itemSearch) itemSearch.addEventListener('input', renderItems);
    var partySearch = one('#party-search');
    if (partySearch) partySearch.addEventListener('input', renderParties);

    var requested = new URLSearchParams(location.search).get('page');
    showPage(one('#page-' + requested) ? requested : 'home');
    loadSafetyData().catch(function (error) { toast(error.message || 'Could not load data', true); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
</script>
"""


def _safe_static_path(asset_name: str):
    clean = PurePosixPath(asset_name)
    if clean.is_absolute() or ".." in clean.parts or len(clean.parts) != 1:
        return None
    path = STATIC_DIR / clean.name
    if not path.is_file():
        return None
    return path


def _patched_owner_script() -> str:
    script = boot_recovery.patched_owner_script()
    script = script.replace(
        "  async function boot() {\n    bindEvents();\n    try {",
        "  async function boot() {\n    try {\n      bindEvents();\n      var earlyApp = one('#app');\n      var earlyLoading = one('#app-loading');\n      if (earlyApp) earlyApp.classList.remove('hidden');\n      if (earlyLoading) earlyLoading.classList.add('hidden');",
        1,
    )
    script = script.replace(
        "      one('#app-loading').innerHTML = '<div class=\"loading-logo\">K</div><strong>App could not start</strong><span>' + escapeHtml(error.message) + '</span><button id=\"retry-boot\" class=\"primary-small\">Retry</button>';\n      one('#retry-boot').addEventListener('click', function () { window.location.reload(); });",
        "      console.error('Owner boot failed', error);\n      var loadingNode = one('#app-loading');\n      var appNode = one('#app');\n      if (appNode) appNode.classList.remove('hidden');\n      if (loadingNode) loadingNode.classList.add('hidden');\n      toast(error && error.message ? error.message : 'Some data could not be loaded', true);",
        1,
    )
    return script


def _inline_owner_assets(html: str) -> str:
    def replace_css(match: re.Match[str]) -> str:
        path = _safe_static_path(match.group(1))
        if path is None:
            return match.group(0)
        css = path.read_text(encoding="utf-8")
        return f'<style data-kirana-inline="{path.name}">\n{css}\n</style>'

    def replace_js(match: re.Match[str]) -> str:
        path = _safe_static_path(match.group(1))
        if path is None:
            return match.group(0)
        script = _patched_owner_script() if path.name == "owner-stable.js" else path.read_text(encoding="utf-8")
        script = script.replace("</script", "<\\/script")
        return f'<script data-kirana-inline="{path.name}">\n{script}\n</script>'

    html = html.replace(
        '<div id="app-loading" class="app-loading">',
        '<div id="app-loading" class="app-loading hidden">',
        1,
    )
    html = html.replace(
        '<div id="app" class="app hidden">',
        '<div id="app" class="app">',
        1,
    )
    html = _STYLESHEET_RE.sub(replace_css, html)
    html = _SCRIPT_RE.sub(replace_js, html)
    html = html.replace(
        "</head>",
        (
            '<meta name="kirana-owner-build" content="116" />'
            '<script>'
            'window.__kiranaSelfContainedBuild="116";'
            'window.__kiranaOwnerBundleLoaded=true;'
            'window.__kiranaOwnerBootReady=true;'
            'document.addEventListener("DOMContentLoaded",function(){'
            'var loading=document.getElementById("app-loading");'
            'var app=document.getElementById("app");'
            'if(app)app.classList.remove("hidden");'
            'if(loading)loading.classList.add("hidden");'
            '});'
            '</script>'
            '</head>'
        ),
        1,
    )
    html = html.replace("</body>", OWNER_SAFETY_RUNTIME + "</body>", 1)
    return html


def _copy_headers(original) -> dict[str, str]:
    return {
        key: value
        for key, value in original.headers.items()
        if key.lower() not in {"content-length", "content-type", "set-cookie", "content-encoding"}
    }


@app.middleware("http")
async def serve_self_contained_owner_page(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if request.method == "GET" and path == "/":
        handoff = request.query_params.get("handoff")
        cookie = request.cookies.get(COOKIE_NAME)
        session = _session_row(handoff) or _session_row(cookie)
        if session:
            original = _ASSEMBLED_OWNER_PAGE(str(session["token"]))
            html = _inline_owner_assets(original.body.decode("utf-8"))
            headers = _copy_headers(original)
            headers.update(
                {
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                    "Expires": "0",
                    "X-Kirana-Self-Contained": SELF_CONTAINED_VERSION,
                }
            )
            response = HTMLResponse(html, status_code=original.status_code, headers=headers)
            cookie_header = original.headers.get("set-cookie")
            if cookie_header:
                response.headers.append("set-cookie", cookie_header)
            return response
    return await call_next(request)
