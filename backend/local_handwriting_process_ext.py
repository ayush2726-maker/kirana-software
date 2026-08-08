from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

from backend.app import app, db
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.local_handwriting_ai_ext as local
import backend.photo_bill_barcode_ext as legacy


VERSION = "143"
MAX_IMAGE_BYTES = 25 * 1024 * 1024
OCR_PYTHON = os.getenv("KIRANA_OCR_PYTHON", "/opt/kirana-ocr/bin/python")
WORKER = Path(__file__).with_name("local_handwriting_worker.py")


def _run_worker(raw: bytes) -> tuple[list[dict[str, Any]], int, int]:
    with tempfile.NamedTemporaryFile(prefix="kirana-bill-", suffix=".jpg", delete=False) as temp:
        temp.write(raw)
        temp_path = temp.name
    try:
        env = dict(os.environ)
        env["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
        completed = subprocess.run(
            [OCR_PYTHON, str(WORKER), temp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=110,
            env=env,
            check=False,
        )
        marker = None
        for line in reversed((completed.stdout or "").splitlines()):
            if line.startswith("KIRANA_JSON:"):
                marker = line[len("KIRANA_JSON:") :]
                break
        if marker is None:
            detail = (completed.stderr or completed.stdout or "local OCR worker returned no result")[-1200:]
            raise RuntimeError(detail)
        payload = json.loads(marker)
        if payload.get("error"):
            raise RuntimeError(str(payload["error"]))
        width = int(payload.get("width") or 0)
        height = int(payload.get("height") or 0)
        fragments: list[dict[str, Any]] = []
        for index, row in enumerate(payload.get("fragments") or []):
            text = str(row.get("text") or "").translate(local.DEVANAGARI_DIGITS).strip()
            if not text:
                continue
            score = max(0.0, min(1.0, local._num(row.get("score"))))
            box = row.get("box")
            if not isinstance(box, list) or len(box) != 4:
                y = float(index * 40)
                x1, y1, x2, y2 = 0.0, y, float(max(width, 1)), y + 30.0
            else:
                x1, y1, x2, y2 = [float(value) for value in box]
            fragments.append(
                {
                    "text": text,
                    "score": score,
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "cx": (x1 + x2) / 2.0,
                    "cy": (y1 + y2) / 2.0,
                    "h": max(1.0, y2 - y1),
                }
            )
        if not fragments:
            raise RuntimeError("local OCR model found no readable handwriting")
        return fragments, max(width, 1), max(height, 1)
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def _quality(rows: list[dict[str, Any]]) -> tuple[int, float, float]:
    if not rows:
        return 0, 0.0, 0.0
    matched = [
        row
        for row in rows
        if row.get("item_id") and local._num(row.get("match_confidence")) >= 0.58
    ]
    average = sum(local._num(row.get("match_confidence")) for row in rows) / len(rows)
    return len(matched), len(matched) / len(rows), average


def _tesseract_safe_rows(raw: bytes, items: list[dict[str, Any]], bill_type: str) -> tuple[list[dict[str, Any]], str]:
    text = legacy._ocr_text(raw)
    fallback = legacy._parse_item_lines(text, items, bill_type)
    safe_rows: list[dict[str, Any]] = []
    for row in fallback:
        if not row.get("item_id"):
            continue
        if local._num(row.get("match_confidence")) < 0.74:
            continue
        if not (0 < local._num(row.get("qty")) <= 100):
            continue
        if not (0 < local._num(row.get("amount")) <= 250_000):
            continue
        row["source_text"] = str(row.get("raw_line") or row.get("item_name") or "")
        safe_rows.append(row)
    return safe_rows, text


def _extract(raw: bytes, business_id: int, bill_type: str) -> dict[str, Any]:
    with db() as conn:
        items = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM items WHERE business_id=? ORDER BY name,size,id",
                (business_id,),
            ).fetchall()
        ]
        parties = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM parties WHERE business_id=? ORDER BY name,id",
                (business_id,),
            ).fetchall()
        ]
        aliases = local._load_aliases(conn, business_id)

    fragments, width, height = _run_worker(raw)
    lines = local._group_lines(fragments)
    rows, warnings, detected_total, calculated_total, raw_text = local._parse_local_rows(
        lines, width, height, items, aliases
    )

    matched_count, matched_ratio, average_confidence = _quality(rows)
    weak_local = (
        len(rows) < 2
        or matched_count < 2
        or matched_ratio < 0.50
        or average_confidence < 0.54
    )

    if weak_local:
        safe_rows, text = _tesseract_safe_rows(raw, items, bill_type)
        if len(safe_rows) >= 2:
            rows = safe_rows
            calculated_total = round(sum(local._num(row.get("amount")) for row in rows), 2)
            warnings.append("PP-OCRv5 handwriting confidence was low; safe local OCR fallback used.")
            raw_text = raw_text + "\n\nTESSERACT FALLBACK:\n" + text
        else:
            raise ValueError(
                "Handwriting abhi reliably read nahi hui, isliye galat bill draft nahi banaya. "
                "Photo ko seedha crop karke poora bill clear light me scan karein."
            )

    matched_count, matched_ratio, average_confidence = _quality(rows)
    unmatched_count = sum(1 for row in rows if not row.get("item_id"))
    low_count = sum(1 for row in rows if local._num(row.get("match_confidence")) < 0.65)

    total_ok = True
    if detected_total > 0 and calculated_total > 0:
        total_ok = abs(calculated_total - detected_total) <= max(5.0, detected_total * 0.05)

    save_allowed = (
        len(rows) >= 2
        and unmatched_count == 0
        and low_count == 0
        and matched_ratio >= 0.80
        and average_confidence >= 0.66
        and total_ok
    )
    if not save_allowed:
        warnings.append(
            "Draft review required: har row me catalog ka correct item select karein; tabhi Save Bill karein."
        )

    party_matches = legacy._party_matches(raw_text, parties, bill_type) if raw_text else []
    return {
        "bill_type": bill_type,
        "invoice_no": "",
        "invoice_date": "",
        "items": rows,
        "party_matches": party_matches,
        "ocr_text": "Kirana Handwriting AI v2 · PP-OCRv5 Hindi/Devanagari · self-hosted\n" + raw_text,
        "detected_lines": len(rows),
        "detected_total": detected_total,
        "calculated_total": calculated_total,
        "warnings": warnings,
        "save_allowed": save_allowed,
        "quality": {
            "matched_rows": matched_count,
            "matched_ratio": round(matched_ratio, 3),
            "average_confidence": round(average_confidence, 3),
            "unmatched_rows": unmatched_count,
            "low_confidence_rows": low_count,
            "total_ok": total_ok,
        },
        "reader": "kirana_handwriting_local_v2",
        "version": VERSION,
    }


@app.middleware("http")
async def isolated_local_handwriting_reader(request: Request, call_next):
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
            return JSONResponse({"detail": "Bill photo is too large (max 25 MB)"}, status_code=413)

        result = await asyncio.to_thread(
            _extract,
            raw,
            int(session["business_id"]),
            bill_type,
        )
        return JSONResponse(
            result,
            headers={
                "Cache-Control": "no-store",
                "X-Kirana-Photo-Reader": VERSION,
                "X-Kirana-AI-Provider": "self-hosted",
            },
        )
    except ValueError as exc:
        return JSONResponse(
            {"detail": str(exc), "reader": "kirana_handwriting_local_v2", "version": VERSION},
            status_code=422,
            headers={"Cache-Control": "no-store"},
        )
    except subprocess.TimeoutExpired:
        return JSONResponse(
            {"detail": "Local handwriting AI took too long. Try a smaller/clearer photo.", "version": VERSION},
            status_code=504,
            headers={"Cache-Control": "no-store"},
        )
    except Exception as exc:
        return JSONResponse(
            {
                "detail": f"Local handwriting AI failed safely: {exc}",
                "reader": "kirana_handwriting_local_v2",
                "version": VERSION,
            },
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )
