from __future__ import annotations

import html
from typing import Any

from fastapi import Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from backend.app import STATIC_DIR, app, current_user, db
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner
import backend.transaction_share_print_ext as print_ext


VERSION = "131"
LAUNCHER_FILE = STATIC_DIR / "owner-print-center-launcher.js"
LAUNCHER_URL = f"/owner-print-center-launcher.js?v={VERSION}"

if LAUNCHER_URL not in native_owner.OPTIONAL_JS_URLS:
    native_owner.OPTIONAL_JS_URLS.append(LAUNCHER_URL)
if LAUNCHER_FILE not in final_owner.JS_FILES:
    final_owner.JS_FILES.append(LAUNCHER_FILE)

native_owner.BUILD = VERSION
final_owner.BUILD = VERSION
stable_owner.VERSION = VERSION


_previous_stable_owner_page = stable_owner.stable_owner_page


def stable_owner_page_with_print_center(token: str) -> HTMLResponse:
    original = _previous_stable_owner_page(token)
    page = original.body.decode("utf-8")
    if LAUNCHER_URL not in page:
        page = page.replace("</body>", f'<script src="{LAUNCHER_URL}"></script></body>', 1)
    headers = {
        key: value
        for key, value in original.headers.items()
        if key.lower() not in {"content-length", "content-type", "set-cookie"}
    }
    response = HTMLResponse(page, status_code=original.status_code, headers=headers)
    cookie = original.headers.get("set-cookie")
    if cookie:
        response.headers.append("set-cookie", cookie)
    return response


stable_owner.stable_owner_page = stable_owner_page_with_print_center


_UNION_SQL = """
SELECT id, ref, title, entry_date, amount, due, kind, status, created_at
FROM (
    SELECT id, invoice_no AS ref,
           COALESCE(NULLIF(party_name,''),'Cash / Walk-in Customer') AS title,
           invoice_date AS entry_date, total AS amount, due,
           'sale' AS kind,
           CASE WHEN due>0 THEN 'unpaid' ELSE 'completed' END AS status,
           created_at, business_id
    FROM sales
    UNION ALL
    SELECT id, invoice_no AS ref,
           COALESCE(NULLIF(party_name,''),'Cash Purchase') AS title,
           invoice_date AS entry_date, total AS amount, due,
           'purchase' AS kind,
           CASE WHEN due>0 THEN 'unpaid' ELSE 'completed' END AS status,
           created_at, business_id
    FROM purchases
    UNION ALL
    SELECT id, title AS ref,
           COALESCE(NULLIF(party_name,''),title) AS title,
           entry_date, amount, 0 AS due, entry_type AS kind,
           status, created_at, business_id
    FROM business_entries
    UNION ALL
    SELECT id, doc_no AS ref,
           COALESCE(NULLIF(party_name,''),kind) AS title,
           doc_date AS entry_date, amount, 0 AS due, kind,
           status, created_at, business_id
    FROM documents
    UNION ALL
    SELECT id, return_no AS ref,
           COALESCE(NULLIF(party_name,''),'Return') AS title,
           return_date AS entry_date, total AS amount, due, kind,
           'completed' AS status, created_at, business_id
    FROM returns
) transaction_rows
WHERE business_id=?
"""


def _filtered_sql(
    business_id: int,
    date_from: str,
    date_to: str,
    kind: str,
    search: str,
) -> tuple[str, list[Any]]:
    sql = _UNION_SQL
    params: list[Any] = [business_id]

    if date_from:
        sql += " AND entry_date>=?"
        params.append(date_from[:10])
    if date_to:
        sql += " AND entry_date<=?"
        params.append(date_to[:10])
    if kind and kind != "all":
        sql += " AND kind=?"
        params.append(kind)
    if search:
        sql += " AND (LOWER(COALESCE(title,'')) LIKE ? OR LOWER(COALESCE(ref,'')) LIKE ? OR LOWER(COALESCE(kind,'')) LIKE ?)"
        pattern = f"%{search.lower()}%"
        params.extend([pattern, pattern, pattern])
    return sql, params


@app.get("/api/print-center-transactions")
def print_center_transactions(
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    kind: str = Query(default="all"),
    search: str = Query(default=""),
    sort: str = Query(default="newest"),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=500000),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    clean_kind = str(kind or "all").strip().lower()
    clean_search = str(search or "").strip()[:120]
    base_sql, params = _filtered_sql(
        int(user["business_id"]),
        str(date_from or "").strip(),
        str(date_to or "").strip(),
        clean_kind,
        clean_search,
    )

    order_by = {
        "oldest": "entry_date ASC, created_at ASC, id ASC",
        "amount_high": "amount DESC, entry_date DESC, id DESC",
        "amount_low": "amount ASC, entry_date DESC, id DESC",
    }.get(str(sort or "").strip().lower(), "entry_date DESC, created_at DESC, id DESC")

    with db() as conn:
        total_row = conn.execute(
            f"SELECT COUNT(*) AS count FROM ({base_sql}) filtered_rows",
            params,
        ).fetchone()
        rows = conn.execute(
            f"{base_sql} ORDER BY {order_by} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()

    return {
        "rows": [dict(row) for row in rows],
        "total": int(total_row["count"] if total_row else 0),
        "offset": offset,
        "limit": limit,
    }


def _owner_session(request: Request):
    return _session_row(request.cookies.get(COOKIE_NAME))


def _business_name(session: Any) -> str:
    with db() as conn:
        row = conn.execute(
            "SELECT name FROM businesses WHERE id=?",
            (int(session["business_id"]),),
        ).fetchone()
    return str(row["name"] if row and row["name"] else "Kirana Software")


def _print_center_page(business_name: str) -> str:
    safe_business = html.escape(business_name)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" />
<meta name="theme-color" content="#087fbf" />
<title>Print Center - {safe_business}</title>
<style>
*{{box-sizing:border-box}}
:root{{--blue:#0b82c2;--ink:#263545;--muted:#74818d;--line:#d5e2e9;--bg:#eef8fe;--green:#138a52;--red:#cc3454}}
html,body{{margin:0;min-height:100%;font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;background:var(--bg);color:var(--ink)}}
body{{padding-bottom:110px}}
.header{{position:sticky;top:0;z-index:20;background:#fff;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:14px;padding:calc(12px + env(safe-area-inset-top)) 16px 12px}}
.icon-btn{{width:48px;height:48px;border:0;border-radius:50%;background:#e9f4fa;color:#096997;font-size:25px;font-weight:900}}
.header div{{min-width:0;flex:1}} .header small{{display:block;color:#0a6c9a;font-weight:900;letter-spacing:1.4px}} .header h1{{font-size:25px;margin:2px 0 0}} .header .printer{{font-size:26px}}
.wrap{{max-width:980px;margin:0 auto;padding:16px}}
.card{{background:#fff;border:1px solid var(--line);border-radius:20px;box-shadow:0 8px 24px rgba(32,77,104,.08)}}
.filters{{padding:16px;display:grid;gap:12px}}
.search{{display:flex;align-items:center;gap:10px;border:2px solid var(--line);border-radius:15px;padding:0 14px;background:#fff}}
.search span{{font-size:24px;color:var(--blue)}} .search input{{border:0;outline:0;width:100%;min-height:54px;font-size:17px;background:transparent}}
.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}}
label{{display:grid;gap:6px;color:#53616d;font-size:13px;font-weight:850}} input,select{{min-width:0;min-height:48px;border:2px solid var(--line);border-radius:13px;background:#fff;padding:9px 11px;font-size:15px;color:var(--ink);outline:none}}
input:focus,select:focus{{border-color:var(--blue)}}
.actions{{display:flex;gap:9px;flex-wrap:wrap}} button{{font:inherit;touch-action:manipulation}}
.primary,.secondary{{min-height:47px;border-radius:13px;padding:10px 16px;font-weight:900}}
.primary{{border:0;background:var(--blue);color:#fff}} .secondary{{border:2px solid #b8d6e6;background:#fff;color:#086996}}
.summary{{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:16px 2px 10px}} .summary strong{{font-size:18px}} .summary span{{color:var(--muted)}}
.list{{display:grid;gap:11px}}
.txn{{background:#fff;border:1px solid var(--line);border-radius:18px;padding:14px;display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center;box-shadow:0 6px 18px rgba(31,75,101,.07);cursor:pointer}}
.txn.selected{{outline:3px solid rgba(11,130,194,.22);border-color:#7dc2e7}}
.txn input[type=checkbox]{{width:23px;height:23px;min-height:0;accent-color:var(--blue)}}
.txn-main{{min-width:0}} .txn-top{{display:flex;gap:8px;align-items:flex-start;justify-content:space-between}} .txn h3{{margin:0;font-size:17px;line-height:1.25;overflow-wrap:anywhere}} .amount{{font-size:17px;font-weight:950;white-space:nowrap}}
.meta{{margin-top:5px;color:var(--muted);font-size:13px;display:flex;gap:6px;flex-wrap:wrap}}
.badge{{display:inline-flex;margin-top:8px;padding:5px 9px;border-radius:999px;background:#e8f7ef;color:var(--green);font-size:11px;font-weight:900;text-transform:uppercase}} .badge.purchase{{background:#fff3d9;color:#926000}} .badge.payment_in{{background:#e8f7ef;color:#087b48}} .badge.payment_out{{background:#fff0f1;color:#a6293d}}
.print-one{{width:45px;height:45px;border:1px solid #c7dae5;background:#f7fbfd;border-radius:13px;font-size:21px;color:#086b9d}}
.empty{{padding:48px 20px;text-align:center;color:var(--muted)}}
.load-more{{display:block;margin:16px auto 0}}
.bulk{{position:fixed;z-index:30;left:12px;right:12px;bottom:calc(12px + env(safe-area-inset-bottom));max-width:760px;margin:auto;background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:0 14px 38px rgba(25,65,91,.25);padding:11px;display:flex;align-items:center;gap:9px}}
.bulk strong{{margin-right:auto;white-space:nowrap}} .bulk .primary{{min-width:130px}}
.toast{{position:fixed;left:50%;bottom:125px;transform:translateX(-50%);z-index:40;max-width:88vw;background:#243545;color:#fff;border-radius:12px;padding:11px 15px;font-weight:800;display:none}} .toast.show{{display:block}}
@media(max-width:720px){{.grid{{grid-template-columns:1fr 1fr}}.txn{{grid-template-columns:auto 1fr auto;padding:12px}}.txn-top{{display:block}}.amount{{display:block;margin-top:4px}}}}
@media(max-width:420px){{.grid{{grid-template-columns:1fr}}.actions .primary,.actions .secondary{{flex:1}}.bulk{{flex-wrap:wrap}}.bulk strong{{width:100%}}}}
</style>
</head>
<body>
<header class="header">
  <button id="back" class="icon-btn" aria-label="Back">‹</button>
  <div><small>TRANSACTIONS</small><h1>Print Center</h1></div>
  <button id="select-all-top" class="icon-btn printer" aria-label="Select visible bills">✓</button>
</header>
<main class="wrap">
  <section class="card filters">
    <label class="search"><span>⌕</span><input id="search" type="search" placeholder="Search party, invoice or transaction" autocomplete="off" /></label>
    <div class="grid">
      <label>From Date<input id="from-date" type="date" /></label>
      <label>To Date<input id="to-date" type="date" /></label>
      <label>Transaction Type<select id="kind">
        <option value="all">All Transactions</option><option value="sale">Sales</option><option value="purchase">Purchases</option>
        <option value="payment_in">Payment-In</option><option value="payment_out">Payment-Out</option>
        <option value="sale_return">Sale Return</option><option value="purchase_return">Purchase Return</option>
        <option value="expense">Expenses</option><option value="delivery_challan">Delivery Challan</option>
        <option value="estimate">Estimate / Quotation</option><option value="proforma">Proforma Invoice</option>
        <option value="sale_order">Sale Order</option><option value="purchase_order">Purchase Order</option>
      </select></label>
      <label>Sort By<select id="sort"><option value="newest">Newest First</option><option value="oldest">Oldest First</option><option value="amount_high">Amount High to Low</option><option value="amount_low">Amount Low to High</option></select></label>
    </div>
    <div class="actions"><button id="apply" class="primary">Apply Filters</button><button id="clear-filters" class="secondary">Clear Filters</button><button id="select-visible" class="secondary">Select Visible</button></div>
  </section>
  <div class="summary"><strong id="result-title">Transactions</strong><span id="result-count">Loading...</span></div>
  <section id="list" class="list"></section>
  <button id="load-more" class="secondary load-more" hidden>Load More</button>
</main>
<div class="bulk"><strong><span id="selected-count">0</span> selected</strong><button id="clear-selection" class="secondary">Clear</button><button id="bulk-print" class="primary">🖨 Bulk Print</button></div>
<div id="toast" class="toast"></div>
<script>
(function(){{
  'use strict';
  var state={{rows:[],selected:new Set(),offset:0,total:0,loading:false,limit:200}};
  function q(id){{return document.getElementById(id)}}
  function esc(v){{return String(v==null?'':v).replace(/[&<>\"']/g,function(c){{return({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}})[c]}})}}
  function money(v){{var n=Number(v||0);return '₹'+(Number.isFinite(n)?n:0).toLocaleString('en-IN',{{minimumFractionDigits:2,maximumFractionDigits:2}})}}
  function date(v){{var s=String(v||'');if(!s)return '-';var p=s.slice(0,10).split('-');return p.length===3?p[2]+'/'+p[1]+'/'+p[0]:s}}
  function label(k){{return({{sale:'Sale',purchase:'Purchase',payment_in:'Payment-In',payment_out:'Payment-Out',sale_return:'Sale Return',purchase_return:'Purchase Return',expense:'Expense',delivery_challan:'Delivery Challan',estimate:'Estimate',proforma:'Proforma Invoice',sale_order:'Sale Order',purchase_order:'Purchase Order'}})[k]||String(k||'Transaction').replace(/_/g,' ')}}
  function key(r){{return String(r.kind)+':'+Number(r.id)}}
  function toast(msg){{var n=q('toast');n.textContent=String(msg||'Done');n.classList.add('show');clearTimeout(toast.t);toast.t=setTimeout(function(){{n.classList.remove('show')}},2800)}}
  function params(){{var p=new URLSearchParams();p.set('offset',String(state.offset));p.set('limit',String(state.limit));p.set('kind',q('kind').value);p.set('sort',q('sort').value);var f=q('from-date').value,t=q('to-date').value,s=q('search').value.trim();if(f)p.set('date_from',f);if(t)p.set('date_to',t);if(s)p.set('search',s);return p}}
  async function load(reset){{if(state.loading)return;if(reset){{state.offset=0;state.rows=[];q('list').innerHTML='';}}state.loading=true;q('result-count').textContent='Loading...';try{{var res=await fetch('/api/print-center-transactions?'+params().toString(),{{credentials:'include',headers:{{Accept:'application/json'}},cache:'no-store'}});var data=await res.json().catch(function(){{return null}});if(res.status===401){{location.replace('/owner-login');return}}if(!res.ok)throw new Error(data&&data.detail?data.detail:'Transactions could not load');state.total=Number(data.total||0);var rows=Array.isArray(data.rows)?data.rows:[];state.rows=state.rows.concat(rows);state.offset=state.rows.length;render(rows,reset);q('result-count').textContent=state.rows.length+' of '+state.total;q('load-more').hidden=state.rows.length>=state.total||!rows.length;}catch(e){{toast(e.message);if(reset)q('list').innerHTML='<div class="card empty">'+esc(e.message)+'</div>'}}finally{{state.loading=false}}}}
  function render(rows,reset){{if(reset&&rows.length===0){{q('list').innerHTML='<div class="card empty">No transactions found for these filters.</div>';updateSelected();return}}var frag=document.createDocumentFragment();rows.forEach(function(r){{var k=key(r),card=document.createElement('article');card.className='txn'+(state.selected.has(k)?' selected':'');card.dataset.key=k;card.innerHTML='<input class="select" type="checkbox" '+(state.selected.has(k)?'checked':'')+' aria-label="Select transaction"><div class="txn-main"><div class="txn-top"><h3>'+esc(r.title||'Transaction')+'</h3><strong class="amount">'+money(r.amount)+'</strong></div><div class="meta"><span>'+esc(r.ref||'-')+'</span><span>·</span><span>'+date(r.entry_date)+'</span></div><span class="badge '+esc(r.kind)+'">'+esc(label(r.kind))+'</span></div><button class="print-one" aria-label="Print bill">🖨</button>';card.addEventListener('click',function(e){{if(e.target.closest('.select'))return toggle(k,e.target.checked,card);if(e.target.closest('.print-one')){{e.preventDefault();e.stopPropagation();return printItems([k])}}printItems([k])}});frag.appendChild(card)}});q('list').appendChild(frag);updateSelected()}}
  function toggle(k,on,card){{if(on)state.selected.add(k);else state.selected.delete(k);if(card)card.classList.toggle('selected',on);updateSelected()}}
  function updateSelected(){{q('selected-count').textContent=String(state.selected.size);q('bulk-print').disabled=state.selected.size===0;q('bulk-print').style.opacity=state.selected.size===0?'.55':'1'}}
  function printItems(items){{if(!items.length)return toast('Select at least one transaction');if(items.length>100)return toast('Maximum 100 bills can be printed together');location.assign('/owner/print-center/print?items='+encodeURIComponent(items.join(',')))}}
  function selectVisible(){{state.rows.forEach(function(r){{state.selected.add(key(r))}});Array.prototype.forEach.call(document.querySelectorAll('.txn'),function(card){{card.classList.add('selected');var input=card.querySelector('.select');if(input)input.checked=true}});updateSelected()}}
  q('back').addEventListener('click',function(){{location.assign('/')}});q('apply').addEventListener('click',function(){{load(true)}});q('clear-filters').addEventListener('click',function(){{q('search').value='';q('from-date').value='';q('to-date').value='';q('kind').value='all';q('sort').value='newest';load(true)}});q('search').addEventListener('keydown',function(e){{if(e.key==='Enter')load(true)}});q('load-more').addEventListener('click',function(){{load(false)}});q('select-visible').addEventListener('click',selectVisible);q('select-all-top').addEventListener('click',selectVisible);q('clear-selection').addEventListener('click',function(){{state.selected.clear();Array.prototype.forEach.call(document.querySelectorAll('.txn'),function(card){{card.classList.remove('selected');var input=card.querySelector('.select');if(input)input.checked=false}});updateSelected()}});q('bulk-print').addEventListener('click',function(){{printItems(Array.from(state.selected))}});updateSelected();load(true);
}})();
</script>
</body></html>"""


@app.get("/owner/print-center", response_class=HTMLResponse)
def owner_print_center(request: Request):
    session = _owner_session(request)
    if not session:
        return RedirectResponse("/owner-login", status_code=303)
    return HTMLResponse(
        _print_center_page(_business_name(session)),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Kirana-Print-Center": VERSION,
        },
    )


@app.get("/owner/print-center/print", response_class=HTMLResponse)
def owner_print_center_print(
    request: Request,
    items: str = Query(default=""),
    autoprint: bool = Query(default=False),
):
    session = _owner_session(request)
    if not session:
        return RedirectResponse("/owner-login", status_code=303)

    selections: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for raw in str(items or "").split(","):
        if ":" not in raw:
            continue
        kind_text, id_text = raw.split(":", 1)
        try:
            kind = print_ext._clean_kind(kind_text)
            transaction_id = int(id_text)
        except Exception:
            continue
        key = (kind, transaction_id)
        if transaction_id > 0 and key not in seen:
            seen.add(key)
            selections.append(key)
        if len(selections) >= 100:
            break

    if not selections:
        return HTMLResponse("Select at least one transaction to print", status_code=400)

    blocks: list[str] = []
    with db() as conn:
        for kind, transaction_id in selections:
            try:
                detail = print_ext._load_detail(
                    conn,
                    int(session["business_id"]),
                    kind,
                    transaction_id,
                )
            except Exception:
                continue
            blocks.append(print_ext._transaction_block(detail))

    if not blocks:
        return HTMLResponse("Selected transaction details were not found", status_code=404)

    return HTMLResponse(
        print_ext._page_html(
            f"Print {len(blocks)} Transaction{'s' if len(blocks) != 1 else ''}",
            "".join(blocks),
            auto_print=autoprint,
            back_href="/owner/print-center",
        ),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "X-Kirana-Print-Center": VERSION,
        },
    )


@app.middleware("http")
async def serve_print_center_launcher(request: Request, call_next):
    if request.method == "GET" and request.url.path.rstrip("/") == "/owner-print-center-launcher.js":
        return Response(
            LAUNCHER_FILE.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "X-Kirana-Print-Center": VERSION,
            },
        )
    return await call_next(request)


_ROUTE_PATHS = {
    "/api/print-center-transactions",
    "/owner/print-center",
    "/owner/print-center/print",
}
_routes = [
    route
    for route in list(app.router.routes)
    if getattr(route, "path", None) in _ROUTE_PATHS
]
for route in _routes:
    app.router.routes.remove(route)
_fallback_index = next(
    (
        index
        for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _routes
