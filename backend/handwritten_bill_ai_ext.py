from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

from backend.app import app, db
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.photo_bill_barcode_ext as legacy


VERSION = "137"
MAX_IMAGE_BYTES = 12 * 1024 * 1024
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite").strip() or "gemini-2.5-flash-lite"


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value or "").replace(",", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        return default


def _json_from_model(text: str) -> dict[str, Any]:
    clean = str(text or "").strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*```$", "", clean)
    start = clean.find("{")
    end = clean.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("AI response did not contain JSON")
    return json.loads(clean[start : end + 1])


def _catalog_text(items: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    total_chars = 0
    for item in items:
        name = str(item.get("name") or "").strip()
        size = str(item.get("size") or "").strip()
        if not name:
            continue
        line = f"- {name}" + (f" | {size}" if size else "")
        if total_chars + len(line) > 42000:
            break
        lines.append(line)
        total_chars += len(line) + 1
    return "\n".join(lines)


def _gemini_extract(raw: bytes, mime_type: str, items: list[dict[str, Any]], bill_type: str) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    prompt = f"""You are reading a handwritten Indian kirana {bill_type} bill from a photo.
Return ONLY one JSON object, no markdown.

Important interpretation rules:
1. Read Hindi/Devanagari and English handwriting directly from the image; do not rely on OCR-like character guessing.
2. Each handwritten row usually has a pack/weight on the LEFT (examples 100g, 500g, 1kg), item name in the MIDDLE, sometimes an @ per-kg/reference rate, and the actual LINE AMOUNT on the FAR RIGHT.
3. A weight such as 100g or 500g is a SIZE/PACK, NOT quantity. If there is no explicit count, qty must be 1.
4. For app billing, `rate` must be the price per selected pack/line unit, so when qty=1 set rate equal to the far-right line amount. Keep any @ per-kg/reference rate only in `listed_rate`.
5. Never turn a pack weight (100, 500, 1000) into qty.
6. The bottom underlined number is usually the bill total. Use it to cross-check the sum of line amounts.
7. If a word is uncertain, choose the closest item from the catalog only when visually plausible; otherwise transcribe what you can and lower confidence.
8. Do not invent GST. Use gst_rate=0 unless GST is explicitly written.

JSON schema:
{{
  "invoice_no": "",
  "invoice_date": "YYYY-MM-DD or empty",
  "party_name": "",
  "total": 0,
  "rows": [
    {{
      "item_name": "",
      "size": "",
      "qty": 1,
      "rate": 0,
      "amount": 0,
      "listed_rate": 0,
      "gst_rate": 0,
      "confidence": 0.0
    }}
  ]
}}

Existing item catalog (prefer these exact names/sizes when the handwriting matches):
{_catalog_text(items)}
"""

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type or "image/jpeg",
                            "data": base64.b64encode(raw).decode("ascii"),
                        }
                    },
                ],
            }
        ],
        "generationConfig": {"temperature": 0.1},
    }
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"AI handwriting reader HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"AI handwriting reader failed: {exc}") from exc

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        raise RuntimeError("AI handwriting reader returned no usable result") from exc
    return _json_from_model(text)


def _normalize_ai_rows(ai: dict[str, Any], items: list[dict[str, Any]], bill_type: str) -> tuple[list[dict[str, Any]], list[str], float, float]:
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for raw_row in list(ai.get("rows") or [])[:80]:
        if not isinstance(raw_row, dict):
            continue
        name = str(raw_row.get("item_name") or "").strip()[:160]
        size = str(raw_row.get("size") or "").strip()[:60]
        qty = _num(raw_row.get("qty"), 1.0)
        amount = _num(raw_row.get("amount"))
        rate = _num(raw_row.get("rate"))
        gst = max(0.0, min(100.0, _num(raw_row.get("gst_rate"))))
        confidence = max(0.0, min(1.0, _num(raw_row.get("confidence"))))

        # Handwritten weight/pack must never become a giant quantity.
        if qty <= 0 or qty > 100:
            qty = 1.0
        if amount <= 0 and rate > 0:
            amount = qty * rate
        if amount <= 0 or amount > 1_000_000:
            continue
        expected_rate = amount / max(qty, 1e-9)
        # The far-right line amount is authoritative for these handwritten bills.
        if rate <= 0 or abs((qty * rate) - amount) > max(2.0, amount * 0.08):
            rate = expected_rate

        matched, match_score = legacy._best_item(f"{name} {size}", items)
        if matched and match_score >= 0.48:
            item_id = int(matched["id"])
            name = str(matched.get("name") or name)
            size = str(matched.get("size") or size)
            confidence = max(confidence, match_score)
        else:
            item_id = None

        if len(name) < 2:
            continue
        rows.append(
            {
                "item_id": item_id,
                "item_name": name,
                "size": size,
                "qty": round(qty, 3),
                "rate": round(rate, 2),
                "gst_rate": round(gst, 2),
                "amount": round(amount, 2),
                "match_confidence": round(confidence, 3),
            }
        )

    calculated_total = round(sum(_num(row.get("amount")) for row in rows), 2)
    detected_total = round(_num(ai.get("total")), 2)
    if detected_total > 0 and calculated_total > 0:
        delta = abs(calculated_total - detected_total)
        if delta > max(5.0, detected_total * 0.05):
            warnings.append(
                f"Line total ₹{calculated_total:.2f} does not match handwritten total ₹{detected_total:.2f}. Check rows before saving."
            )
    low_confidence = [row for row in rows if _num(row.get("match_confidence")) < 0.60]
    if low_confidence:
        warnings.append(f"{len(low_confidence)} row(s) need item-name verification.")
    return rows, warnings, detected_total, calculated_total


def _strict_legacy(raw: bytes, items: list[dict[str, Any]], bill_type: str) -> dict[str, Any]:
    text = legacy._ocr_text(raw)
    parsed = legacy._parse_item_lines(text, items, bill_type)
    safe = []
    for row in parsed:
        score = _num(row.get("match_confidence"))
        qty = _num(row.get("qty"))
        rate = _num(row.get("rate"))
        amount = _num(row.get("amount"))
        # Never expose OCR garbage as a ready-to-save bill.
        if score < 0.72:
            continue
        if qty <= 0 or qty > 100 or rate < 0 or rate > 100_000 or amount <= 0 or amount > 250_000:
            continue
        safe.append(row)
    if len(safe) < 2:
        raise ValueError(
            "Handwritten bill detected, but normal OCR could not read it reliably. AI handwriting reader is required for this photo."
        )
    return {"text": text, "rows": safe}


@app.middleware("http")
async def handwritten_bill_ai_reader(request: Request, call_next):
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
            return JSONResponse({"detail": "Bill type must be sale or purchase"}, status_code=400)
        if upload is None or not hasattr(upload, "read"):
            return JSONResponse({"detail": "Upload a bill photo"}, status_code=400)
        raw = await upload.read()
        if not raw:
            return JSONResponse({"detail": "Bill photo is empty"}, status_code=400)
        if len(raw) > MAX_IMAGE_BYTES:
            return JSONResponse({"detail": "Bill photo is too large (max 12 MB)"}, status_code=413)
        mime_type = str(getattr(upload, "content_type", "") or "image/jpeg")

        with db() as conn:
            item_rows = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM items WHERE business_id=? AND COALESCE(archived_at,'')='' ORDER BY name,size,id",
                    (int(session["business_id"]),),
                ).fetchall()
            ]
            party_rows = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM parties WHERE business_id=? ORDER BY name,id",
                    (int(session["business_id"]),),
                ).fetchall()
            ]

        api_key_ready = bool(os.getenv("GEMINI_API_KEY", "").strip())
        if api_key_ready:
            ai = _gemini_extract(raw, mime_type, item_rows, bill_type)
            rows, warnings, detected_total, calculated_total = _normalize_ai_rows(ai, item_rows, bill_type)
            if not rows:
                return JSONResponse(
                    {"detail": "AI could not confidently read item rows from this handwriting. Try a clearer, straighter photo."},
                    status_code=422,
                )
            party_text = str(ai.get("party_name") or "")
            party_matches = legacy._party_matches(party_text, party_rows, bill_type) if party_text else []
            return JSONResponse(
                {
                    "bill_type": bill_type,
                    "invoice_no": str(ai.get("invoice_no") or "")[:30],
                    "invoice_date": str(ai.get("invoice_date") or "")[:10],
                    "items": rows,
                    "party_matches": party_matches,
                    "ocr_text": "AI Vision handwriting reader used. Review low-confidence rows before saving.",
                    "detected_lines": len(rows),
                    "detected_total": detected_total,
                    "calculated_total": calculated_total,
                    "warnings": warnings,
                    "reader": "ai_vision",
                    "version": VERSION,
                },
                headers={"Cache-Control": "no-store", "X-Kirana-Photo-Reader": VERSION},
            )

        # No AI key: do not return the old garbage draft for handwriting.
        fallback = _strict_legacy(raw, item_rows, bill_type)
        return JSONResponse(
            {
                "bill_type": bill_type,
                "invoice_no": legacy._invoice_number(fallback["text"]),
                "invoice_date": legacy._invoice_date(fallback["text"]),
                "items": fallback["rows"],
                "party_matches": legacy._party_matches(fallback["text"], party_rows, bill_type),
                "ocr_text": fallback["text"],
                "detected_lines": len(fallback["rows"]),
                "warnings": ["Normal OCR mode used. Handwritten bills need AI Vision for best accuracy."],
                "reader": "strict_ocr",
                "version": VERSION,
            },
            headers={"Cache-Control": "no-store", "X-Kirana-Photo-Reader": VERSION},
        )
    except ValueError as exc:
        return JSONResponse(
            {
                "detail": str(exc),
                "ai_configured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
                "version": VERSION,
            },
            status_code=422,
            headers={"Cache-Control": "no-store"},
        )
    except Exception as exc:
        return JSONResponse(
            {"detail": f"Photo bill reader failed safely: {exc}", "version": VERSION},
            status_code=502,
            headers={"Cache-Control": "no-store"},
        )
