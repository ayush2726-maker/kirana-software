from __future__ import annotations

import asyncio
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

from backend.app import app, db
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.local_handwriting_ai_ext as local
import backend.local_handwriting_process_ext as process
import backend.photo_bill_barcode_ext as legacy

VERSION = "145"
MAX_IMAGE_BYTES = 25 * 1024 * 1024


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value or "").replace(",", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        return default


def _legacy_review_rows(raw: bytes, items: list[dict[str, Any]], bill_type: str) -> tuple[list[dict[str, Any]], str]:
    text = legacy._ocr_text(raw)
    parsed = legacy._parse_item_lines(text, items, bill_type)
    rows: list[dict[str, Any]] = []
    for row in parsed[:80]:
        qty = _num(row.get("qty"), 1.0)
        amount = _num(row.get("amount"))
        rate = _num(row.get("rate"))
        if qty <= 0 or qty > 100:
            qty = 1.0
        if amount <= 0 and rate > 0:
            amount = qty * rate
        if amount <= 0 or amount > 250_000:
            continue
        if rate <= 0:
            rate = amount / max(qty, 1e-9)
        row["qty"] = round(qty, 3)
        row["rate"] = round(rate, 2)
        row["amount"] = round(amount, 2)
        row["source_text"] = str(row.get("raw_line") or row.get("item_name") or "")
        rows.append(row)
    return rows, text


def _extract_review(raw: bytes, business_id: int, bill_type: str) -> dict[str, Any]:
    with db() as conn:
        items = [dict(row) for row in conn.execute(
            "SELECT * FROM items WHERE business_id=? AND COALESCE(archived_at,'')='' ORDER BY name,size,id",
            (business_id,),
        ).fetchall()]
        parties = [dict(row) for row in conn.execute(
            "SELECT * FROM parties WHERE business_id=? ORDER BY name,id",
            (business_id,),
        ).fetchall()]
        aliases = local._load_aliases(conn, business_id)

    warnings: list[str] = []
    raw_text = ""
    rows: list[dict[str, Any]] = []
    detected_total = 0.0
    calculated_total = 0.0
    reader = "kirana_handwriting_review_v3"

    try:
        fragments, width, height = process._run_worker(raw)
        lines = local._group_lines(fragments)
        rows, local_warnings, detected_total, calculated_total, raw_text = local._parse_local_rows(
            lines, width, height, items, aliases
        )
        warnings.extend(local_warnings)
    except Exception as exc:
        warnings.append("Handwriting AI pass weak/failed; safe OCR review fallback use hua.")
        raw_text = f"Local handwriting pass: {exc}"

    if not rows:
        try:
            fallback_rows, fallback_text = _legacy_review_rows(raw, items, bill_type)
            rows = fallback_rows
            raw_text = (raw_text + "\n\nOCR REVIEW:\n" + fallback_text).strip()
            calculated_total = round(sum(_num(row.get("amount")) for row in rows), 2)
            reader = "kirana_handwriting_review_fallback"
        except Exception as exc:
            warnings.append(f"OCR fallback bhi weak raha: {exc}")

    if not rows:
        return {
            "bill_type": bill_type,
            "invoice_no": "",
            "invoice_date": "",
            "items": [{
                "item_id": None,
                "item_name": "",
                "size": "",
                "qty": 1,
                "rate": 0,
                "gst_rate": 0,
                "amount": 0,
                "match_confidence": 0,
                "source_text": "",
            }],
            "party_matches": [],
            "ocr_text": raw_text or "Handwriting could not be auto-read. Add/correct rows manually.",
            "detected_lines": 0,
            "detected_total": 0,
            "calculated_total": 0,
            "warnings": [
                "Photo difficult hai. Blank editable draft khola gaya hai — item select karke qty/rate correct karein."
            ],
            "save_allowed": False,
            "reader": reader,
            "version": VERSION,
        }

    # Do not block a useful draft just because catalog confidence is low. The
    # existing Smart Billing table is editable, so uncertain rows can be fixed.
    low = sum(1 for row in rows if not row.get("item_id") or _num(row.get("match_confidence")) < 0.65)
    if low:
        warnings.append(f"{low} row(s) ko check/edit karein. Low-confidence handwriting ko auto-save nahi maana gaya.")

    party_matches = legacy._party_matches(raw_text, parties, bill_type) if raw_text else []
    return {
        "bill_type": bill_type,
        "invoice_no": "",
        "invoice_date": "",
        "items": rows,
        "party_matches": party_matches,
        "ocr_text": "Kirana Handwriting Review v3\n" + raw_text,
        "detected_lines": len(rows),
        "detected_total": detected_total,
        "calculated_total": calculated_total or round(sum(_num(row.get("amount")) for row in rows), 2),
        "warnings": warnings,
        "save_allowed": low == 0,
        "reader": reader,
        "version": VERSION,
    }


@app.middleware("http")
async def handwriting_review_reader(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if request.method != "POST" or path != "/api/photo-bill/ocr":
        return await call_next(request)

    session = _session_row(request.cookies.get(COOKIE_NAME))
    if not session:
        return RedirectResponse("/owner-login", status_code=303)
    try:
        form = await request.form()
        upload = form.get("file")
        bill_type = str(form.get("bill_type") or "purchase").strip().lower()
        if bill_type not in {"sale", "purchase"}:
            bill_type = "purchase"
        if upload is None or not hasattr(upload, "read"):
            return JSONResponse({"detail": "Upload a bill photo"}, status_code=400)
        raw = await upload.read()
        if not raw:
            return JSONResponse({"detail": "Bill photo is empty"}, status_code=400)
        if len(raw) > MAX_IMAGE_BYTES:
            return JSONResponse({"detail": "Bill photo is too large (max 25 MB)"}, status_code=413)
        result = await asyncio.to_thread(_extract_review, raw, int(session["business_id"]), bill_type)
        return JSONResponse(result, headers={
            "Cache-Control": "no-store",
            "X-Kirana-Photo-Reader": VERSION,
            "X-Kirana-Review-Draft": "1",
        })
    except Exception as exc:
        # Final safety net: keep the screen usable instead of showing a hard red
        # blocker. User can still manually add rows in the existing draft table.
        return JSONResponse({
            "bill_type": "purchase",
            "invoice_no": "",
            "invoice_date": "",
            "items": [{"item_id": None, "item_name": "", "size": "", "qty": 1, "rate": 0, "gst_rate": 0, "match_confidence": 0}],
            "party_matches": [],
            "ocr_text": f"Reader fallback: {exc}",
            "detected_lines": 0,
            "warnings": ["Photo auto-read nahi hui; editable blank row khol di gayi hai."],
            "save_allowed": False,
            "reader": "kirana_handwriting_review_safe",
            "version": VERSION,
        }, headers={"Cache-Control": "no-store", "X-Kirana-Photo-Reader": VERSION})
