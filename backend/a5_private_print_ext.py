from __future__ import annotations

import base64
import re
from io import BytesIO
from typing import Any
from urllib.parse import urlencode

import qrcode
import qrcode.image.svg
from fastapi import Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.app import app, db
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.transaction_share_print_ext as print_ext


VERSION = "133"
PRINT_PATH = "/owner/print-center/print"
UPI_PATTERN = re.compile(r"^[^\s@]{2,}@[^\s@]{2,}$")


def _clean_upi_id(value: Any) -> str:
    text = str(value or "").strip()[:100]
    return text if UPI_PATTERN.fullmatch(text) else ""


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _label(kind: str) -> str:
    labels = {
        "sale": "Sale",
        "purchase": "Purchase",
        "sale_return": "Sale Return",
        "purchase_return": "Purchase Return",
        "payment_in": "Payment In",
        "payment_out": "Payment Out",
        "expense": "Expense",
        "transfer": "Account Transfer",
        "delivery_challan": "Delivery Challan",
        "estimate": "Estimate",
        "proforma": "Proforma",
        "sale_order": "Sale Order",
        "purchase_order": "Purchase Order",
        "sale_asset": "Sale Asset",
        "purchase_asset": "Purchase Asset",
    }
    return labels.get(kind, str(kind or "Transaction").replace("_", " ").title())


def _qr_data_uri(payload: str) -> str:
    image = qrcode.make(
        payload,
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=5,
        border=1,
    )
    output = BytesIO()
    image.save(output)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _payment_qr(detail: dict[str, Any], kind: str, number: str) -> str:
    if kind != "sale":
        return ""
    upi_id = _clean_upi_id(detail.get("_print_upi_id"))
    if not upi_id:
        return ""
    amount = _number(detail.get("due"))
    if amount <= 0:
        amount = _number(detail.get("total"))
    params = {
        "pa": upi_id,
        "pn": "Payment",
        "cu": "INR",
        "am": f"{max(amount, 0):.2f}",
    }
    if number:
        params["tn"] = f"Sale {number}"[:80]
    uri = "upi://pay?" + urlencode(params)
    return (
        "<section class='pay-qr'>"
        f"<img src='{_qr_data_uri(uri)}' alt='UPI payment QR' />"
        "<div><b>Scan &amp; Pay</b>"
        f"<span>{print_ext._money(amount)}</span></div>"
        "</section>"
    )


def _transaction_block(detail: dict[str, Any], *, public_view: bool = False) -> str:
    party = detail.get("party") or {}
    kind = str(detail.get("kind") or "transaction")
    items = list(detail.get("items") or [])
    title = _label(kind)
    number = str(detail.get("number") or detail.get("reference") or "")
    party_name = detail.get("party_name") or party.get("name") or detail.get("title") or ""

    if items:
        rows = "".join(
            "<tr>"
            f"<td class='serial'>{index}</td>"
            f"<td class='item-name'>{print_ext._esc(item.get('item_name'))}</td>"
            f"<td class='size'>{print_ext._esc(item.get('size') or '-')}</td>"
            f"<td class='num qty'>{print_ext._esc(item.get('qty'))}</td>"
            f"<td class='num rate'>{print_ext._money(item.get('rate'))}</td>"
            f"<td class='num amount'>{print_ext._money(item.get('line_total'))}</td>"
            "</tr>"
            for index, item in enumerate(items, 1)
        )
        item_section = (
            "<table class='items'><colgroup>"
            "<col class='c-serial'><col class='c-item'><col class='c-size'>"
            "<col class='c-qty'><col class='c-rate'><col class='c-amount'>"
            "</colgroup><thead><tr><th>#</th><th>Item</th><th>Size</th>"
            "<th class='num'>Qty</th><th class='num'>Rate</th><th class='num'>Amount</th>"
            "</tr></thead><tbody>" + rows + "</tbody></table>"
        )
    else:
        account = detail.get("account_name") or ""
        to_account = detail.get("to_account_name") or ""
        account_text = print_ext._esc(account)
        if to_account:
            account_text += " → " + print_ext._esc(to_account)
        item_section = (
            "<section class='entry-detail'>"
            f"<div><span>Transaction</span><b>{print_ext._esc(title)}</b></div>"
            + (f"<div><span>Account</span><b>{account_text}</b></div>" if account_text else "")
            + f"<div><span>Mode</span><b>{print_ext._esc(detail.get('payment_mode') or '-')}</b></div>"
            + "</section>"
        )

    discount = _number(detail.get("discount"))
    tax = _number(detail.get("tax"))
    totals = [
        f"<div class='grand'><span>Total</span><b>{print_ext._money(detail.get('total'))}</b></div>"
    ]
    if discount:
        totals.insert(0, f"<div><span>Discount</span><b>{print_ext._money(discount)}</b></div>")
    if tax:
        totals.insert(0, f"<div><span>Tax</span><b>{print_ext._money(tax)}</b></div>")
    totals.extend(
        [
            f"<div><span>Paid</span><b>{print_ext._money(detail.get('paid'))}</b></div>",
            f"<div><span>Balance</span><b>{print_ext._money(detail.get('due'))}</b></div>",
        ]
    )

    status = str(detail.get("status") or "").replace("_", " ").title()
    notes = str(detail.get("notes") or "").strip()
    qr = _payment_qr(detail, kind, number)
    return (
        f"<article class='bill-page item-count-{len(items)}'>"
        "<header class='bill-head'>"
        f"<div class='bill-type'><b>{print_ext._esc(title)}</b><span>{print_ext._esc(number)}</span></div>"
        f"<div class='bill-date'><small>Date</small><b>{print_ext._esc(print_ext._format_date(detail.get('date')))}</b></div>"
        "</header>"
        "<section class='party-line'>"
        f"<div><small>Party</small><b>{print_ext._esc(party_name or 'Cash')}</b></div>"
        f"<span>{print_ext._esc(status)}</span>"
        "</section>"
        f"{item_section}"
        "<section class='settlement'>"
        f"{qr}"
        f"<section class='totals'>{''.join(totals)}</section>"
        "</section>"
        + (f"<p class='notes'><b>Note:</b> {print_ext._esc(notes)}</p>" if notes else "")
        + "</article>"
    )


def _page_html(title: str, body: str, *, auto_print: bool = False, back_href: str = "/") -> str:
    auto_script = (
        "window.addEventListener('load',function(){setTimeout(function(){window.print();},300);});"
        if auto_print
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{print_ext._esc(title)}</title>
<style>
:root{{--ink:#17212b;--muted:#5d6770;--line:#cfd7dd;--blue:#0b82c2;--bg:#edf7fd}}
*{{box-sizing:border-box}}
html,body{{margin:0}}
body{{background:var(--bg);color:var(--ink);font-family:Arial,sans-serif}}
.toolbar{{position:sticky;top:0;z-index:5;display:flex;gap:10px;justify-content:center;align-items:center;padding:10px;background:#fff;border-bottom:1px solid var(--line)}}
.toolbar button,.toolbar a{{border:0;border-radius:10px;padding:10px 17px;font-weight:800;text-decoration:none;cursor:pointer;font-size:14px}}
.toolbar button{{background:var(--blue);color:#fff}}.toolbar a{{background:#eef2f5;color:var(--ink)}}.toolbar span{{font-size:12px;color:var(--muted);font-weight:700}}
.print-wrap{{width:148mm;max-width:100%;margin:14px auto;padding:0}}
.bill-page{{width:148mm;min-height:210mm;background:#fff;border:1px solid var(--line);padding:5mm;margin:0 auto 8mm;box-shadow:0 7px 24px rgba(20,60,90,.12);break-after:page;page-break-after:always}}
.bill-page:last-child{{break-after:auto;page-break-after:auto}}
.bill-head{{display:flex;justify-content:space-between;align-items:flex-start;gap:5mm;border-bottom:.55mm solid var(--ink);padding-bottom:2mm}}
.bill-type{{display:grid;gap:.7mm}}.bill-type b{{font-size:14pt;line-height:1;text-transform:uppercase;letter-spacing:.4mm}}.bill-type span{{font-size:8pt;font-weight:700;color:var(--muted)}}
.bill-date{{text-align:right;display:grid;gap:.5mm}}.bill-date small,.party-line small{{color:var(--muted);font-size:7pt;text-transform:uppercase;letter-spacing:.2mm}}.bill-date b{{font-size:9pt}}
.party-line{{min-height:9mm;display:flex;justify-content:space-between;align-items:center;gap:4mm;padding:1.5mm 0}}
.party-line div{{display:grid;gap:.4mm;min-width:0}}.party-line b{{font-size:9pt;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.party-line>span{{font-size:7pt;color:var(--muted);white-space:nowrap}}
.items{{width:100%;border-collapse:collapse;table-layout:fixed;font-size:7.4pt}}
.items .c-serial{{width:5%}}.items .c-item{{width:37%}}.items .c-size{{width:14%}}.items .c-qty{{width:9%}}.items .c-rate{{width:15%}}.items .c-amount{{width:20%}}
.items thead{{display:table-header-group}}.items th{{background:#eef3f6;font-size:7pt;text-transform:uppercase;letter-spacing:.1mm}}
.items th,.items td{{border:.2mm solid var(--line);padding:.55mm .7mm;height:3.75mm;line-height:1.05;vertical-align:middle}}
.items td.item-name,.items td.size{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.items td.size{{color:#37434d;font-weight:700}}
.num{{text-align:right!important;white-space:nowrap}}.serial{{text-align:center}}
.entry-detail{{border:.2mm solid var(--line);display:grid;gap:1.2mm;padding:2mm;font-size:8pt}}.entry-detail div{{display:flex;justify-content:space-between;gap:4mm}}
.settlement{{display:grid;grid-template-columns:1fr 58mm;gap:4mm;align-items:end;margin-top:2.4mm}}
.totals{{display:grid;gap:.65mm;font-size:8pt}}.totals div{{display:flex;justify-content:space-between;gap:5mm}}.totals .grand{{border-top:.45mm solid var(--ink);padding-top:1mm;font-size:10pt}}
.pay-qr{{display:flex;align-items:center;gap:2.2mm;min-height:25mm}}.pay-qr img{{width:24mm;height:24mm;display:block}}.pay-qr div{{display:grid;gap:1mm}}.pay-qr b{{font-size:8pt}}.pay-qr span{{font-size:10pt;font-weight:900}}
.notes{{margin:1.5mm 0 0;border-top:.2mm solid var(--line);padding-top:1mm;font-size:7pt;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
@media(max-width:650px){{.toolbar span{{display:none}}.print-wrap,.bill-page{{width:100%}}.bill-page{{min-height:auto;padding:12px}}.items{{font-size:7pt}}}}
@media print{{
  @page{{size:A5 portrait;margin:5mm}}
  html,body{{background:#fff}}
  .toolbar{{display:none!important}}
  .print-wrap{{width:auto;max-width:none;margin:0;padding:0}}
  .bill-page{{width:auto;min-height:200mm;border:0;box-shadow:none;margin:0;padding:0}}
}}
</style>
</head>
<body>
<nav class="toolbar"><a href="{print_ext._esc(back_href)}">← Back</a><button onclick="window.print()">Print A5 / Save PDF</button><span>A5 • compact 30+ item layout</span></nav>
<main class="print-wrap">{body}</main>
<script>{auto_script}</script>
</body></html>"""


# Replace shared print rendering globally so single print, bulk print and public
# share previews use the same private A5 layout.
print_ext._label = _label
print_ext._transaction_block = _transaction_block
print_ext._page_html = _page_html


# Remove the older print-center route before registering the A5 version.
for route in list(app.router.routes):
    if getattr(route, "path", None) == PRINT_PATH:
        app.router.routes.remove(route)


@app.get(PRINT_PATH, response_class=HTMLResponse)
def owner_print_center_print_a5(
    request: Request,
    items: str = Query(default=""),
    upi_id: str = Query(default=""),
    autoprint: bool = Query(default=False),
):
    session = _session_row(request.cookies.get(COOKIE_NAME))
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

    clean_upi = _clean_upi_id(upi_id)
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
            detail["_print_upi_id"] = clean_upi
            blocks.append(_transaction_block(detail))

    if not blocks:
        return HTMLResponse("Selected transaction details were not found", status_code=404)

    return HTMLResponse(
        _page_html(
            f"Print {len(blocks)} Transaction{'s' if len(blocks) != 1 else ''}",
            "".join(blocks),
            auto_print=autoprint,
            back_href="/owner/print-center",
        ),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "X-Kirana-A5-Print": VERSION,
        },
    )


# Keep this explicit route ahead of the catch-all owner/customer frontend route.
_a5_route = next(
    route
    for route in reversed(app.router.routes)
    if getattr(route, "path", None) == PRINT_PATH
)
app.router.routes.remove(_a5_route)
_fallback_index = next(
    (
        index
        for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes.insert(_fallback_index, _a5_route)
