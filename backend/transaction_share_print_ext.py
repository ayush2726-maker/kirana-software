from __future__ import annotations

import html
import secrets
from datetime import datetime
from typing import Any
from urllib.parse import quote

from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from backend.app import app, current_user, db, now_iso
import backend.transaction_detail_ext as transaction_detail


ALLOWED_KINDS = {
    "sale",
    "purchase",
    "sale_return",
    "purchase_return",
    "payment_in",
    "payment_out",
    "expense",
    "transfer",
    "delivery_challan",
    "estimate",
    "proforma",
    "sale_order",
    "purchase_order",
    "sale_asset",
    "purchase_asset",
}


def ensure_transaction_share_schema() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transaction_share_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                transaction_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                UNIQUE(business_id, kind, transaction_id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_transaction_share_token ON transaction_share_links(token)"
        )


@app.on_event("startup")
def startup_transaction_share_print() -> None:
    ensure_transaction_share_schema()


def _clean_kind(kind: str) -> str:
    value = str(kind or "").strip().lower()
    if not value or value not in ALLOWED_KINDS:
        raise HTTPException(status_code=400, detail="Unsupported transaction type")
    return value


def _party_id(conn: Any, business_id: int, kind: str, transaction_id: int) -> int | None:
    table_column = {
        "sale": ("sales", "id"),
        "purchase": ("purchases", "id"),
        "sale_return": ("returns", "id"),
        "purchase_return": ("returns", "id"),
    }
    if kind in table_column:
        table, id_column = table_column[kind]
        query = f"SELECT party_id FROM {table} WHERE {id_column}=? AND business_id=?"
        params: tuple[Any, ...] = (transaction_id, business_id)
        if table == "returns":
            query += " AND kind=?"
            params = (transaction_id, business_id, kind)
        row = conn.execute(query, params).fetchone()
        return int(row["party_id"]) if row and row["party_id"] else None

    row = conn.execute(
        "SELECT party_id FROM business_entries WHERE id=? AND business_id=? AND entry_type=?",
        (transaction_id, business_id, kind),
    ).fetchone()
    if row:
        return int(row["party_id"]) if row["party_id"] else None

    row = conn.execute(
        "SELECT party_id FROM documents WHERE id=? AND business_id=? AND kind=?",
        (transaction_id, business_id, kind),
    ).fetchone()
    return int(row["party_id"]) if row and row["party_id"] else None


def _load_detail(conn: Any, business_id: int, kind: str, transaction_id: int) -> dict[str, Any]:
    detail = transaction_detail._bill_detail(conn, business_id, kind, transaction_id)
    if detail is None:
        detail = transaction_detail._entry_detail(conn, business_id, kind, transaction_id)
    if detail is None:
        detail = transaction_detail._document_detail(conn, business_id, kind, transaction_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Transaction details were not found")

    business_row = conn.execute(
        "SELECT id,name,owner_name,phone,gstin,address,invoice_prefix FROM businesses WHERE id=?",
        (business_id,),
    ).fetchone()
    business = dict(business_row) if business_row else {"id": business_id, "name": "Kirana Software"}

    party: dict[str, Any] = {}
    party_id = _party_id(conn, business_id, kind, transaction_id)
    if party_id:
        party_row = conn.execute(
            "SELECT id,name,type,phone,gstin,address,balance FROM parties WHERE id=? AND business_id=?",
            (party_id, business_id),
        ).fetchone()
        if party_row:
            party = dict(party_row)

    enriched = dict(detail)
    enriched["business"] = business
    enriched["party"] = party
    enriched["party_id"] = party_id
    return enriched


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"₹{amount:,.2f}"


def _label(kind: str) -> str:
    labels = {
        "sale": "Sale Invoice",
        "purchase": "Purchase Bill",
        "sale_return": "Sale Return",
        "purchase_return": "Purchase Return",
        "payment_in": "Payment-In Receipt",
        "payment_out": "Payment-Out Receipt",
        "expense": "Expense",
        "transfer": "Account Transfer",
        "delivery_challan": "Delivery Challan",
        "estimate": "Estimate / Quotation",
        "proforma": "Proforma Invoice",
        "sale_order": "Sale Order",
        "purchase_order": "Purchase Order",
        "sale_asset": "Sale Asset",
        "purchase_asset": "Purchase Asset",
    }
    return labels.get(kind, kind.replace("_", " ").title())


def _format_date(value: Any) -> str:
    text = str(value or "").strip()
    try:
        return datetime.fromisoformat(text[:10]).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return text


def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


def _transaction_block(detail: dict[str, Any], *, public_view: bool = False) -> str:
    business = detail.get("business") or {}
    party = detail.get("party") or {}
    kind = str(detail.get("kind") or "transaction")
    items = detail.get("items") or []
    title = _label(kind)
    number = detail.get("number") or detail.get("reference") or ""
    party_name = detail.get("party_name") or party.get("name") or detail.get("title") or ""

    rows = ""
    if items:
        rows = "".join(
            "<tr>"
            f"<td>{index}</td>"
            f"<td><b>{_esc(item.get('item_name'))}</b><small>{_esc(item.get('size'))}</small></td>"
            f"<td class='num'>{_esc(item.get('qty'))}</td>"
            f"<td class='num'>{_money(item.get('rate'))}</td>"
            f"<td class='num'>{_money(item.get('line_total'))}</td>"
            "</tr>"
            for index, item in enumerate(items, 1)
        )
        item_section = (
            "<table class='items'><thead><tr><th>#</th><th>Item</th><th class='num'>Qty</th>"
            "<th class='num'>Rate</th><th class='num'>Amount</th></tr></thead><tbody>"
            + rows
            + "</tbody></table>"
        )
    else:
        account = detail.get("account_name") or ""
        to_account = detail.get("to_account_name") or ""
        account_line = ""
        if account or to_account:
            account_line = f"<p><b>Account:</b> {_esc(account)}"
            if to_account:
                account_line += f" → {_esc(to_account)}"
            account_line += "</p>"
        item_section = (
            "<section class='entry-detail'>"
            f"<p><b>Transaction:</b> {_esc(title)}</p>"
            f"{account_line}"
            f"<p><b>Payment Mode:</b> {_esc(detail.get('payment_mode') or '-')}</p>"
            f"<p><b>Notes:</b> {_esc(detail.get('notes') or '-')}</p>"
            "</section>"
        )

    return (
        "<article class='bill-page'>"
        "<header class='bill-head'>"
        f"<div><h1>{_esc(business.get('name') or 'Kirana Software')}</h1>"
        f"<p>{_esc(business.get('address'))}</p>"
        f"<p>{_esc(business.get('phone'))}"
        + (f" · GSTIN {_esc(business.get('gstin'))}" if business.get("gstin") else "")
        + "</p></div>"
        f"<div class='bill-type'><b>{_esc(title)}</b><span>{_esc(number)}</span></div>"
        "</header>"
        "<section class='party-date'>"
        f"<div><small>Party</small><b>{_esc(party_name or 'Cash / Walk-in')}</b>"
        f"<span>{_esc(party.get('phone'))}</span><span>{_esc(party.get('address'))}</span></div>"
        f"<div><small>Date</small><b>{_esc(_format_date(detail.get('date')))}</b>"
        f"<span>Status: {_esc(str(detail.get('status') or '').replace('_', ' ').title())}</span></div>"
        "</section>"
        f"{item_section}"
        "<section class='totals'>"
        f"<div><span>Subtotal</span><b>{_money(detail.get('subtotal', detail.get('total')))}</b></div>"
        f"<div><span>Discount</span><b>{_money(detail.get('discount'))}</b></div>"
        f"<div><span>Tax</span><b>{_money(detail.get('tax'))}</b></div>"
        f"<div class='grand'><span>Total</span><b>{_money(detail.get('total'))}</b></div>"
        f"<div><span>Paid</span><b>{_money(detail.get('paid'))}</b></div>"
        f"<div><span>Balance</span><b>{_money(detail.get('due'))}</b></div>"
        "</section>"
        + (f"<p class='notes'><b>Notes:</b> {_esc(detail.get('notes'))}</p>" if detail.get("notes") else "")
        + ("<footer>Shared securely from Kirana Software</footer>" if public_view else "<footer>Computer generated document</footer>")
        + "</article>"
    )


def _page_html(title: str, body: str, *, auto_print: bool = False, back_href: str = "/") -> str:
    auto_script = "window.addEventListener('load',function(){setTimeout(function(){window.print();},300);});" if auto_print else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{_esc(title)}</title>
<style>
:root{{--ink:#243445;--muted:#6f7c88;--line:#d8e2e8;--blue:#0b82c2;--bg:#edf7fd}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font-family:Arial,sans-serif}}
.toolbar{{position:sticky;top:0;z-index:5;display:flex;gap:10px;justify-content:center;padding:12px;background:#fff;border-bottom:1px solid var(--line)}}
.toolbar button,.toolbar a{{border:0;border-radius:10px;padding:11px 18px;font-weight:800;text-decoration:none;cursor:pointer}}
.toolbar button{{background:var(--blue);color:#fff}} .toolbar a{{background:#eef2f5;color:var(--ink)}}
.print-wrap{{max-width:900px;margin:18px auto;padding:0 12px}}
.bill-page{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:28px;margin:0 auto 20px;box-shadow:0 8px 28px rgba(20,60,90,.12);page-break-after:always}}
.bill-page:last-child{{page-break-after:auto}} .bill-head{{display:flex;justify-content:space-between;gap:20px;border-bottom:2px solid var(--ink);padding-bottom:14px}}
.bill-head h1{{margin:0 0 5px;font-size:25px}} .bill-head p{{margin:3px 0;color:var(--muted)}}
.bill-type{{text-align:right;display:grid;align-content:start;gap:6px}} .bill-type b{{font-size:20px}} .bill-type span{{font-weight:700;color:var(--blue)}}
.party-date{{display:grid;grid-template-columns:1fr auto;gap:20px;padding:16px 0}} .party-date div{{display:grid;gap:4px}} .party-date small{{color:var(--muted)}}
.items{{width:100%;border-collapse:collapse}} .items th,.items td{{padding:10px 7px;border-bottom:1px solid var(--line);text-align:left}} .items small{{display:block;color:var(--muted);margin-top:3px}}
.num{{text-align:right!important}} .entry-detail{{border:1px solid var(--line);border-radius:10px;padding:14px}} .entry-detail p{{margin:7px 0}}
.totals{{width:min(370px,100%);margin:18px 0 0 auto;display:grid;gap:7px}} .totals div{{display:flex;justify-content:space-between;gap:25px}} .totals .grand{{font-size:19px;border-top:2px solid var(--ink);padding-top:9px}}
.notes{{border-top:1px solid var(--line);padding-top:12px}} footer{{text-align:center;color:var(--muted);margin-top:24px;font-size:12px}}
@media(max-width:600px){{.bill-page{{padding:17px}}.bill-head{{display:grid}}.bill-type{{text-align:left}}.party-date{{grid-template-columns:1fr}}.items{{font-size:12px}}}}
@media print{{@page{{size:A4;margin:10mm}} body{{background:#fff}} .toolbar{{display:none!important}} .print-wrap{{max-width:none;margin:0;padding:0}} .bill-page{{border:0;border-radius:0;box-shadow:none;margin:0;padding:0;min-height:270mm}}}}
</style>
</head>
<body>
<nav class="toolbar"><a href="{_esc(back_href)}">← Back</a><button onclick="window.print()">Print / Save PDF</button></nav>
<main class="print-wrap">{body}</main>
<script>{auto_script}</script>
</body></html>"""


@app.post("/api/transaction-share/{kind}/{transaction_id}")
def create_transaction_share_link(
    kind: str,
    transaction_id: int,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    clean_kind = _clean_kind(kind)
    if transaction_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid transaction")
    ensure_transaction_share_schema()
    business_id = int(user["business_id"])

    with db() as conn:
        detail = _load_detail(conn, business_id, clean_kind, transaction_id)
        row = conn.execute(
            "SELECT token FROM transaction_share_links WHERE business_id=? AND kind=? AND transaction_id=?",
            (business_id, clean_kind, transaction_id),
        ).fetchone()
        if row:
            token = str(row["token"])
        else:
            token = secrets.token_urlsafe(20)
            try:
                conn.execute(
                    """
                    INSERT INTO transaction_share_links(business_id,kind,transaction_id,token,created_at)
                    VALUES(?,?,?,?,?)
                    """,
                    (business_id, clean_kind, transaction_id, token, now_iso()),
                )
            except Exception:
                row = conn.execute(
                    "SELECT token FROM transaction_share_links WHERE business_id=? AND kind=? AND transaction_id=?",
                    (business_id, clean_kind, transaction_id),
                ).fetchone()
                if not row:
                    raise
                token = str(row["token"])

    base_url = str(request.base_url).rstrip("/")
    share_url = f"{base_url}/shared-transaction/{token}"
    business_name = (detail.get("business") or {}).get("name") or "Kirana Software"
    party = detail.get("party") or {}
    message = (
        f"Namaste 🙏\n\n{business_name} se aapki {_label(clean_kind)} details:\n"
        f"Party: {detail.get('party_name') or detail.get('title') or '-'}\n"
        f"Bill No.: {detail.get('number') or '-'}\n"
        f"Date: {_format_date(detail.get('date'))}\n"
        f"Total: {_money(detail.get('total'))}\n"
        f"Paid: {_money(detail.get('paid'))}\n"
        f"Balance: {_money(detail.get('due'))}\n\n"
        f"Bill dekhne ya print karne ke liye:\n{share_url}"
    )
    digits = "".join(character for character in str(party.get("phone") or "") if character.isdigit())
    if len(digits) == 10:
        digits = "91" + digits
    whatsapp_url = f"https://wa.me/{digits}?text={quote(message)}" if digits else f"https://wa.me/?text={quote(message)}"
    return {"url": share_url, "whatsapp_url": whatsapp_url, "message": message}


@app.get("/shared-transaction/{token}", response_class=HTMLResponse)
def public_shared_transaction(token: str) -> HTMLResponse:
    ensure_transaction_share_schema()
    with db() as conn:
        row = conn.execute(
            "SELECT business_id,kind,transaction_id FROM transaction_share_links WHERE token=?",
            (str(token or ""),),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Shared bill was not found")
        detail = _load_detail(conn, int(row["business_id"]), str(row["kind"]), int(row["transaction_id"]))
    block = _transaction_block(detail, public_view=True)
    return HTMLResponse(
        _page_html(f"{_label(str(detail.get('kind')))} {detail.get('number') or ''}", block, back_href="javascript:history.back()"),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/owner/bulk-print", response_class=HTMLResponse)
def owner_bulk_print(
    items: str = Query(default=""),
    autoprint: bool = Query(default=False),
    user: dict[str, Any] = Depends(current_user),
) -> HTMLResponse:
    selections: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for raw in str(items or "").split(","):
        if ":" not in raw:
            continue
        kind_text, id_text = raw.split(":", 1)
        try:
            kind = _clean_kind(kind_text)
            transaction_id = int(id_text)
        except (HTTPException, TypeError, ValueError):
            continue
        key = (kind, transaction_id)
        if transaction_id > 0 and key not in seen:
            seen.add(key)
            selections.append(key)
        if len(selections) >= 100:
            break

    if not selections:
        raise HTTPException(status_code=400, detail="Select at least one transaction to print")

    blocks: list[str] = []
    with db() as conn:
        for kind, transaction_id in selections:
            try:
                detail = _load_detail(conn, int(user["business_id"]), kind, transaction_id)
            except HTTPException:
                continue
            blocks.append(_transaction_block(detail))

    if not blocks:
        raise HTTPException(status_code=404, detail="Selected transaction details were not found")
    return HTMLResponse(
        _page_html(f"Bulk Print - {len(blocks)} Transactions", "".join(blocks), auto_print=autoprint, back_href="/"),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


_ROUTE_PATHS = {
    "/api/transaction-share/{kind}/{transaction_id}",
    "/shared-transaction/{token}",
    "/owner/bulk-print",
}
_new_routes = [route for route in list(app.router.routes) if getattr(route, "path", None) in _ROUTE_PATHS]
for route in _new_routes:
    app.router.routes.remove(route)
_fallback_index = next(
    (
        index
        for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _new_routes
