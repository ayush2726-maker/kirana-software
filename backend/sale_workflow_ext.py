from __future__ import annotations

import io
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from openpyxl import load_workbook

import backend.app as core
import backend.vyapar_exact_ext as exact
from backend.app import STATIC_DIR, app, current_user, db, now_iso


# ---------------------------------------------------------------------------
# Vyapar Sale/Purchase import grouping
# ---------------------------------------------------------------------------
# Some Vyapar Item Details sheets use a line-level "Txn No." instead of the
# bill's Invoice No. The old parser then treated every item line as a separate
# bill. Match every unmatched line back to the summary sheet by date, party and
# bill total so one invoice always contains all of its item rows.


def _summary_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("invoice_date") or ""), exact._clean(row.get("name"))


def _merge_all_summary_items(
    items: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    kind: str,
) -> list[dict[str, Any]]:
    exact_by_date_invoice = {
        (row["invoice_date"], row["invoice_no"]): row
        for row in summaries
        if row.get("invoice_no")
    }
    by_invoice: dict[str, list[dict[str, Any]]] = defaultdict(list)
    summaries_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for summary in summaries:
        summaries_by_key[_summary_key(summary)].append(summary)
        if summary.get("invoice_no"):
            by_invoice[str(summary["invoice_no"])].append(summary)

    used_summary_rows: set[int] = set()
    pending: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for row in items:
        invoice = str(row.get("invoice_no") or "").strip()
        summary = exact_by_date_invoice.get((row["invoice_date"], invoice)) if invoice else None
        if summary is None and invoice and len(by_invoice.get(invoice, [])) == 1:
            candidate = by_invoice[invoice][0]
            if _summary_key(candidate) == _summary_key(row):
                summary = candidate
        if summary is not None:
            exact._apply_summary(row, summary, invoice or str(summary.get("invoice_no") or ""))
            used_summary_rows.add(int(summary["source_index"]))
        else:
            # Blank invoice numbers and line-level Txn numbers are both resolved
            # against the remaining bill summaries for this date and party.
            pending[_summary_key(row)].append(row)

    prefix = "S" if kind == "sales" else "P"
    for key, rows in pending.items():
        available = [
            summary
            for summary in summaries_by_key.get(key, [])
            if int(summary["source_index"]) not in used_summary_rows
        ]
        if available:
            cuts = exact._partition(
                [core.money(row.get("line_total"), 0) for row in rows],
                [core.money(summary.get("total"), 0) for summary in available],
            )
            consumed = 0
            for summary, (start, end) in zip(available, cuts):
                if start == end:
                    continue
                invoice = str(summary.get("invoice_no") or "").strip()
                if not invoice:
                    invoice = (
                        f"VYP-{prefix}-{summary['invoice_date'].replace('-', '')}-"
                        f"{int(summary['source_index']):06d}"
                    )
                for row in rows[start:end]:
                    exact._apply_summary(row, summary, invoice)
                used_summary_rows.add(int(summary["source_index"]))
                consumed = max(consumed, end)

            # If a damaged workbook has extra lines after all summaries, retain
            # them together as one reviewable bill rather than one bill per item.
            leftovers = rows[consumed:]
        else:
            leftovers = rows

        if leftovers:
            first = leftovers[0]
            fallback_invoice = (
                f"VYP-{prefix}-{first['invoice_date'].replace('-', '')}-"
                f"{int(first.get('source_index') or 1):06d}"
            )
            for row in leftovers:
                row["invoice_no"] = fallback_invoice

    # Vyapar restarts invoice numbers in older financial years. Keep the date in
    # the key only when the same invoice number occurs on multiple dates.
    invoice_dates: dict[str, set[str]] = defaultdict(set)
    for row in items:
        invoice_dates[str(row.get("invoice_no") or "")].add(str(row.get("invoice_date") or ""))
    repeated = {invoice for invoice, dates in invoice_dates.items() if invoice and len(dates) > 1}
    for row in items:
        if row.get("invoice_no") in repeated:
            row["invoice_no"] = f"{row['invoice_no']}-{row['invoice_date'].replace('-', '')}"

    # Reconcile round-off and additional charges with the Vyapar bill summary.
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in items:
        grouped[str(row["invoice_no"])].append(row)
    for rows in grouped.values():
        expected = next(
            (
                core.money(row.get("expected_total"), 0)
                for row in rows
                if row.get("expected_total") not in (None, "")
            ),
            None,
        )
        if expected is None:
            continue
        calculated = sum(
            core.number(row.get("qty"), 0)
            * core.money(row.get("rate"), 0)
            * (1 + core.number(row.get("gst_rate"), 0) / 100)
            for row in rows
        )
        difference = expected - calculated
        if abs(difference) > 0.009:
            last = rows[-1]
            qty = max(core.number(last.get("qty"), 0), 0.0001)
            factor = 1 + core.number(last.get("gst_rate"), 0) / 100
            last["rate"] = max(0.0, round(core.money(last.get("rate"), 0) + difference / (qty * factor), 6))
    return items


# Patch the exact parser in-place; parse_exact_vyapar resolves this module
# function dynamically when each workbook is uploaded.
exact._merge_summary = _merge_all_summary_items
core.parse_upload = exact.parse_exact_vyapar


# ---------------------------------------------------------------------------
# High-confidence cleanup for previously imported item-wise duplicate bills
# ---------------------------------------------------------------------------


def _file_key(filename: str) -> str:
    return re.sub(r"[^a-z0-9]", "", Path(filename or "").name.casefold())


def _sale_batch_stats(conn: Any, business_id: int) -> list[dict[str, Any]]:
    batches = conn.execute(
        """
        SELECT * FROM import_batches
        WHERE business_id=? AND entity_type='sales'
          AND COALESCE(status,'')!='rolled_back'
        ORDER BY id DESC
        """,
        (business_id,),
    ).fetchall()
    stats: list[dict[str, Any]] = []
    for batch in batches:
        sales = conn.execute(
            """
            SELECT id,invoice_date,total,paid,due,payment_mode,party_id
            FROM sales WHERE business_id=? AND import_batch_id=? ORDER BY id
            """,
            (business_id, batch["id"]),
        ).fetchall()
        if not sales:
            continue
        line_counts = [
            int(conn.execute("SELECT COUNT(*) FROM sale_items WHERE sale_id=?", (sale["id"],)).fetchone()[0])
            for sale in sales
        ]
        dates = sorted(str(sale["invoice_date"] or "") for sale in sales)
        stats.append({
            "batch_id": int(batch["id"]),
            "filename": str(batch["filename"] or ""),
            "file_key": _file_key(str(batch["filename"] or "")),
            "transactions": len(sales),
            "lines": sum(line_counts),
            "one_line_ratio": sum(1 for count in line_counts if count == 1) / max(1, len(line_counts)),
            "total": round(sum(float(sale["total"] or 0) for sale in sales), 2),
            "date_from": dates[0],
            "date_to": dates[-1],
        })
    return stats


def _duplicate_itemwise_batches(conn: Any, business_id: int) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _sale_batch_stats(conn, business_id):
        groups[row["file_key"]].append(row)

    found: list[dict[str, Any]] = []
    for rows in groups.values():
        if len(rows) < 2:
            continue
        for candidate in rows:
            if candidate["transactions"] < 20 or candidate["one_line_ratio"] < 0.90:
                continue
            peers = []
            for peer in rows:
                if peer["batch_id"] == candidate["batch_id"]:
                    continue
                same_dates = (
                    peer["date_from"] == candidate["date_from"]
                    and peer["date_to"] == candidate["date_to"]
                )
                line_tolerance = max(3, int(max(peer["lines"], candidate["lines"]) * 0.02))
                same_lines = abs(peer["lines"] - candidate["lines"]) <= line_tolerance
                total_tolerance = max(2.0, max(abs(peer["total"]), abs(candidate["total"])) * 0.01)
                same_total = abs(peer["total"] - candidate["total"]) <= total_tolerance
                properly_grouped = peer["transactions"] + max(5, int(peer["transactions"] * 0.10)) < candidate["transactions"]
                if same_dates and same_lines and same_total and properly_grouped:
                    peers.append(peer)
            if not peers:
                continue
            best = min(peers, key=lambda row: row["transactions"])
            found.append({
                **candidate,
                "matched_batch_id": best["batch_id"],
                "matched_transactions": best["transactions"],
            })
    # A batch can compare successfully with more than one good re-import.
    return list({row["batch_id"]: row for row in found}.values())


def _rollback_sale_batch(conn: Any, business_id: int, batch_id: int) -> int:
    sales = conn.execute(
        """
        SELECT id,party_id,due,paid,payment_mode
        FROM sales WHERE business_id=? AND import_batch_id=?
        """,
        (business_id, batch_id),
    ).fetchall()
    for sale in sales:
        lines = conn.execute(
            "SELECT item_id,qty FROM sale_items WHERE sale_id=?",
            (sale["id"],),
        ).fetchall()
        for line in lines:
            if line["item_id"]:
                conn.execute(
                    "UPDATE items SET stock=stock+?,updated_at=? WHERE id=?",
                    (float(line["qty"] or 0), now_iso(), line["item_id"]),
                )
        conn.execute(
            "DELETE FROM stock_movements WHERE business_id=? AND reference_type='sale' AND reference_id=?",
            (business_id, sale["id"]),
        )
        conn.execute(
            "DELETE FROM ledger_entries WHERE business_id=? AND reference_type='sale' AND reference_id=?",
            (business_id, sale["id"]),
        )
        if sale["party_id"] and sale["due"]:
            conn.execute(
                "UPDATE parties SET balance=MAX(0,balance-?),updated_at=? WHERE id=?",
                (float(sale["due"] or 0), now_iso(), sale["party_id"]),
            )
        if sale["paid"]:
            core.adjust_account(conn, business_id, str(sale["payment_mode"] or "cash"), -float(sale["paid"] or 0))
    conn.execute("DELETE FROM sales WHERE business_id=? AND import_batch_id=?", (business_id, batch_id))
    conn.execute(
        """
        UPDATE import_batches
        SET status='rolled_back',rows_imported=0,errors_json=?
        WHERE id=? AND business_id=?
        """,
        (json.dumps([{"error": "Removed item-wise duplicate sale bills"}]), batch_id, business_id),
    )
    return len(sales)


@app.post("/api/import/cleanup-itemwise-sales")
def cleanup_itemwise_sales(
    execute: bool = Query(False),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    with db() as conn:
        batches = _duplicate_itemwise_batches(conn, user["business_id"])
        removed = 0
        if execute:
            for batch in batches:
                removed += _rollback_sale_batch(conn, user["business_id"], batch["batch_id"])
            conn.execute(
                """
                DELETE FROM items
                WHERE business_id=? AND sku LIKE 'IMP-%'
                  AND ABS(COALESCE(stock,0))<0.000001
                  AND NOT EXISTS (SELECT 1 FROM sale_items WHERE sale_items.item_id=items.id)
                  AND NOT EXISTS (SELECT 1 FROM purchase_items WHERE purchase_items.item_id=items.id)
                  AND NOT EXISTS (SELECT 1 FROM return_items WHERE return_items.item_id=items.id)
                """,
                (user["business_id"],),
            )
    return {
        "execute": execute,
        "batch_count": len(batches),
        "transaction_count": sum(int(batch["transactions"]) for batch in batches),
        "removed": removed,
        "batches": batches,
    }


# ---------------------------------------------------------------------------
# Root document injection
# ---------------------------------------------------------------------------
# This is imported last and intentionally serves the root with every extension
# bundle once. It avoids middleware ordering causing one feature bundle to hide
# another on Android Chrome/WebView.


@app.middleware("http")
async def inject_sale_workflow_assets(request, call_next):
    if request.method == "GET" and request.url.path == "/":
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        html = html.replace(
            "</head>",
            '<link rel="stylesheet" href="/settings-v2.css?v=042" /></head>',
        )
        html = html.replace(
            "</body>",
            '<script src="/settings-v2.js?v=042"></script>'
            '<script src="/import-fix.js?v=044"></script>'
            '<script src="/activity-navigation.js?v=043"></script>'
            '<script src="/sale-item-picker.js?v=044"></script></body>',
        )
        return HTMLResponse(
            html,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
            },
        )
    return await call_next(request)


# New endpoint must remain before the SPA fallback route.
new_paths = {"/api/import/cleanup-itemwise-sales"}
new_routes = [route for route in app.router.routes if getattr(route, "path", None) in new_paths]
for route in new_routes:
    app.router.routes.remove(route)
fallback_index = next(
    (index for index, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
    len(app.router.routes),
)
app.router.routes[fallback_index:fallback_index] = new_routes
