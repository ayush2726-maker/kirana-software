from __future__ import annotations

import asyncio
import json
import math
import re
import statistics
import threading
from io import BytesIO
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from PIL import Image, ImageOps, UnidentifiedImageError

from backend.app import app, db
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.photo_bill_barcode_ext as legacy


VERSION = "140"
MAX_IMAGE_BYTES = 25 * 1024 * 1024
_MODEL = None
_MODEL_LOCK = threading.Lock()
_INFER_LOCK = threading.Lock()
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
SIZE_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(kg|kgs|kilo|kilogram|g|gm|gms|gram|grams|ml|l|ltr|litre|liter|pkt|pack|pc|pcs)\b",
    re.IGNORECASE,
)
QTY_RE = re.compile(r"(?:\bqty\s*[:=-]?\s*(\d+(?:\.\d+)?)\b|\b(\d+(?:\.\d+)?)\s*[x×]\b|\b(\d+)\s*pcs?\b)", re.IGNORECASE)
AT_RATE_RE = re.compile(r"[@＠]\s*₹?\s*([0-9][0-9,]*(?:\.\d+)?)")
NUMBER_RE = re.compile(r"(?<![A-Za-z])₹?\s*([0-9][0-9,]*(?:\.\d+)?)")


def _normalize(value: Any) -> str:
    text = str(value or "").translate(DEVANAGARI_DIGITS).lower()
    text = re.sub(r"[^a-z0-9\u0900-\u097f]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value or "").translate(DEVANAGARI_DIGITS).replace(",", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        return default


def _ensure_learning_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS handwriting_aliases (
            business_id INTEGER NOT NULL,
            raw_key TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            hits INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (business_id, raw_key)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_handwriting_alias_item ON handwriting_aliases(business_id,item_id)"
    )


def _load_aliases(conn, business_id: int) -> dict[str, int]:
    _ensure_learning_table(conn)
    rows = conn.execute(
        "SELECT raw_key,item_id FROM handwriting_aliases WHERE business_id=? ORDER BY hits DESC,updated_at DESC",
        (business_id,),
    ).fetchall()
    return {str(row["raw_key"]): int(row["item_id"]) for row in rows}


def _learn_aliases(conn, business_id: int, rows: list[dict[str, Any]]) -> int:
    _ensure_learning_table(conn)
    valid_ids = {
        int(row["id"])
        for row in conn.execute("SELECT id FROM items WHERE business_id=?", (business_id,)).fetchall()
    }
    learned = 0
    for row in rows[:100]:
        if not isinstance(row, dict):
            continue
        raw_key = _normalize(row.get("source_text"))
        try:
            item_id = int(row.get("item_id") or 0)
        except (TypeError, ValueError):
            item_id = 0
        if len(raw_key) < 2 or item_id not in valid_ids:
            continue
        conn.execute(
            """
            INSERT INTO handwriting_aliases(business_id,raw_key,item_id,hits,updated_at)
            VALUES(?,?,?,1,CURRENT_TIMESTAMP)
            ON CONFLICT(business_id,raw_key) DO UPDATE SET
                item_id=excluded.item_id,
                hits=handwriting_aliases.hits+1,
                updated_at=CURRENT_TIMESTAMP
            """,
            (business_id, raw_key, item_id),
        )
        learned += 1
    conn.commit()
    return learned


def _get_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL
        from paddleocr import PaddleOCR

        # Hindi requires the multilingual PP-OCRv3 recognizer. It also recognizes
        # the Latin digits/units commonly used in kirana handwritten notes.
        _MODEL = PaddleOCR(
            lang="hi",
            ocr_version="PP-OCRv3",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device="cpu",
            enable_mkldnn=True,
            cpu_threads=2,
            text_rec_score_thresh=0.12,
        )
        return _MODEL


def _prepare_image(raw: bytes) -> tuple[Any, int, int]:
    try:
        image = Image.open(BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Photo could not be read. Use JPG, PNG or WEBP.") from exc
    if image.width < 300 or image.height < 300:
        raise ValueError("Photo is too small. Take a clearer full-bill photo.")
    image = image.convert("RGB")
    max_side = max(image.width, image.height)
    if max_side > 2800:
        scale = 2800.0 / max_side
        image = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))))
    import numpy as np

    return np.asarray(image), image.width, image.height


def _result_dict(result: Any) -> dict[str, Any]:
    payload = getattr(result, "json", None)
    if callable(payload):
        payload = payload()
    if payload is None and hasattr(result, "to_dict"):
        payload = result.to_dict()
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("res")
    return nested if isinstance(nested, dict) else payload


def _box_values(box: Any) -> tuple[float, float, float, float] | None:
    try:
        if hasattr(box, "tolist"):
            box = box.tolist()
        if len(box) == 4 and not isinstance(box[0], (list, tuple)):
            x1, y1, x2, y2 = [float(v) for v in box]
            return x1, y1, x2, y2
        points = list(box)
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        return None


def _paddle_fragments(raw: bytes) -> tuple[list[dict[str, Any]], int, int]:
    image, width, height = _prepare_image(raw)
    model = _get_model()
    with _INFER_LOCK:
        outputs = model.predict(image)
    fragments: list[dict[str, Any]] = []
    for output in outputs:
        data = _result_dict(output)
        texts = list(data.get("rec_texts") or [])
        scores = list(data.get("rec_scores") or [])
        boxes = list(data.get("rec_boxes") or data.get("rec_polys") or [])
        for index, raw_text in enumerate(texts):
            text = str(raw_text or "").translate(DEVANAGARI_DIGITS).strip()
            if not text:
                continue
            score = _num(scores[index] if index < len(scores) else 0.0)
            box = _box_values(boxes[index]) if index < len(boxes) else None
            if box is None:
                # Preserve sequence even if a backend version omits boxes.
                y = float(index * 40)
                box = (0.0, y, float(width), y + 30.0)
            x1, y1, x2, y2 = box
            fragments.append(
                {
                    "text": text,
                    "score": max(0.0, min(1.0, score)),
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "cx": (x1 + x2) / 2.0,
                    "cy": (y1 + y2) / 2.0,
                    "h": max(1.0, y2 - y1),
                }
            )
    return fragments, width, height


def _group_lines(fragments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not fragments:
        return []
    heights = [row["h"] for row in fragments if row["h"] > 0]
    median_height = statistics.median(heights) if heights else 28.0
    tolerance = max(14.0, median_height * 0.78)
    groups: list[list[dict[str, Any]]] = []
    for frag in sorted(fragments, key=lambda row: (row["cy"], row["x1"])):
        target = None
        best_delta = float("inf")
        for group in groups[-4:]:
            center = sum(item["cy"] for item in group) / len(group)
            delta = abs(frag["cy"] - center)
            if delta <= tolerance and delta < best_delta:
                target = group
                best_delta = delta
        if target is None:
            groups.append([frag])
        else:
            target.append(frag)
    lines: list[dict[str, Any]] = []
    for group in groups:
        ordered = sorted(group, key=lambda row: row["x1"])
        lines.append(
            {
                "parts": ordered,
                "text": " ".join(part["text"] for part in ordered).strip(),
                "score": sum(part["score"] for part in ordered) / max(1, len(ordered)),
                "y": sum(part["cy"] for part in ordered) / max(1, len(ordered)),
                "x1": min(part["x1"] for part in ordered),
                "x2": max(part["x2"] for part in ordered),
            }
        )
    return sorted(lines, key=lambda row: row["y"])


def _numbers(text: str) -> list[float]:
    clean = str(text or "").translate(DEVANAGARI_DIGITS)
    return [_num(match.group(1)) for match in NUMBER_RE.finditer(clean)]


def _rightmost_amount(line: dict[str, Any], page_width: int) -> tuple[float, str | None]:
    parts = line["parts"]
    # Prefer the far-right OCR fragment: in these bills the final column is the
    # actual line amount, while @price in the middle is a reference/kg rate.
    for part in sorted(parts, key=lambda row: row["x2"], reverse=True):
        nums = _numbers(part["text"])
        if not nums:
            continue
        if part["cx"] >= page_width * 0.55 or len(parts) == 1:
            return nums[-1], part["text"]
    nums = _numbers(line["text"])
    return (nums[-1], None) if nums else (0.0, None)


def _size_from_text(text: str) -> str:
    match = SIZE_RE.search(str(text or "").translate(DEVANAGARI_DIGITS))
    if not match:
        return ""
    value = match.group(1)
    unit = match.group(2).lower()
    unit_map = {"g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g", "kgs": "kg", "kilo": "kg", "kilogram": "kg", "ltr": "L", "litre": "L", "liter": "L"}
    unit = unit_map.get(unit, unit)
    return f"{value}{unit}"


def _qty_from_text(text: str) -> float:
    match = QTY_RE.search(str(text or "").translate(DEVANAGARI_DIGITS))
    if not match:
        return 1.0
    for value in match.groups():
        if value:
            qty = _num(value, 1.0)
            return qty if 0 < qty <= 100 else 1.0
    return 1.0


def _listed_rate(text: str) -> float:
    match = AT_RATE_RE.search(str(text or "").translate(DEVANAGARI_DIGITS))
    return _num(match.group(1)) if match else 0.0


def _item_text(line: dict[str, Any], amount_fragment_text: str | None, amount: float) -> str:
    text = str(line["text"] or "").translate(DEVANAGARI_DIGITS)
    if amount_fragment_text and len(line["parts"]) > 1:
        # Remove only the rightmost amount fragment when OCR split the columns.
        pieces = [part["text"] for part in line["parts"]]
        for index in range(len(pieces) - 1, -1, -1):
            if pieces[index] == amount_fragment_text:
                del pieces[index]
                break
        text = " ".join(pieces)
    else:
        # Single OCR fragment: remove the final numeric occurrence only.
        matches = list(NUMBER_RE.finditer(text))
        if matches:
            last = matches[-1]
            text = text[: last.start()] + " " + text[last.end() :]
    text = AT_RATE_RE.sub(" ", text)
    text = SIZE_RE.sub(" ", text, count=1)
    text = QTY_RE.sub(" ", text)
    text = re.sub(r"\b(?:rs|inr|amt|amount|total)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[@₹|:=]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -.,/|:")
    # A leftover standalone number is usually a reference rate, not the item.
    text = re.sub(r"\s+\d+(?:\.\d+)?\s*$", "", text).strip()
    return text[:160]


def _alias_item(raw_text: str, aliases: dict[str, int], item_by_id: dict[int, dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    key = _normalize(raw_text)
    item_id = aliases.get(key)
    if item_id and item_id in item_by_id:
        return item_by_id[item_id], 1.0
    return None, 0.0


def _parse_local_rows(
    lines: list[dict[str, Any]],
    page_width: int,
    page_height: int,
    items: list[dict[str, Any]],
    aliases: dict[str, int],
) -> tuple[list[dict[str, Any]], list[str], float, float, str]:
    item_by_id = {int(item["id"]): item for item in items}
    rows: list[dict[str, Any]] = []
    total_candidates: list[tuple[float, float]] = []
    raw_lines: list[str] = []

    for line in lines:
        raw = str(line["text"] or "").strip()
        if not raw:
            continue
        raw_lines.append(f"[{line['score']:.2f}] {raw}")
        amount, amount_fragment = _rightmost_amount(line, page_width)
        if amount <= 0 or amount > 250_000:
            continue
        size = _size_from_text(raw)
        qty = _qty_from_text(raw)
        listed_rate = _listed_rate(raw)
        name = _item_text(line, amount_fragment, amount)
        normalized_name = _normalize(name)

        # A number-only line near the bottom is treated as the handwritten grand total.
        if len(normalized_name) < 2 or re.fullmatch(r"[0-9 ]+", normalized_name or ""):
            if line["y"] >= page_height * 0.65:
                total_candidates.append((line["y"], amount))
            continue

        learned_item, learned_score = _alias_item(raw, aliases, item_by_id)
        if learned_item is not None:
            matched = learned_item
            match_score = learned_score
        else:
            matched, match_score = legacy._best_item(f"{name} {size}", items)

        if matched and match_score >= 0.46:
            item_id = int(matched["id"])
            item_name = str(matched.get("name") or name)
            matched_size = str(matched.get("size") or "").strip()
            if matched_size:
                size = matched_size
        else:
            item_id = None
            item_name = name

        if qty <= 0 or qty > 100:
            qty = 1.0
        rate = amount / max(qty, 1e-9)
        ocr_score = max(0.0, min(1.0, _num(line.get("score"))))
        confidence = max(ocr_score * 0.72, match_score)
        rows.append(
            {
                "item_id": item_id,
                "item_name": item_name,
                "size": size,
                "qty": round(qty, 3),
                "rate": round(rate, 2),
                "gst_rate": 0.0,
                "amount": round(amount, 2),
                "listed_rate": round(listed_rate, 2),
                "match_confidence": round(max(0.0, min(1.0, confidence)), 3),
                "source_text": raw,
            }
        )

    calculated_total = round(sum(_num(row.get("amount")) for row in rows), 2)
    detected_total = 0.0
    if total_candidates:
        # Bottom-most plausible amount wins, matching the usual underlined bill total.
        detected_total = round(sorted(total_candidates, key=lambda pair: pair[0])[-1][1], 2)

    warnings: list[str] = []
    if detected_total > 0 and calculated_total > 0:
        delta = abs(calculated_total - detected_total)
        if delta > max(5.0, detected_total * 0.05):
            warnings.append(
                f"Line total ₹{calculated_total:.2f} does not match handwritten total ₹{detected_total:.2f}. Check rows before saving."
            )
    low = [row for row in rows if _num(row.get("match_confidence")) < 0.58]
    if low:
        warnings.append(f"{len(low)} row(s) need item-name verification.")
    return rows, warnings, detected_total, calculated_total, "\n".join(raw_lines)


def _local_extract(raw: bytes, business_id: int) -> dict[str, Any]:
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
        aliases = _load_aliases(conn, business_id)

    fragments, width, height = _paddle_fragments(raw)
    lines = _group_lines(fragments)
    rows, warnings, detected_total, calculated_total, raw_text = _parse_local_rows(
        lines, width, height, items, aliases
    )
    if len(rows) < 2:
        # Safe local fallback only; Gemini is intentionally not used.
        text = legacy._ocr_text(raw)
        fallback = legacy._parse_item_lines(text, items, "purchase")
        fallback = [
            row
            for row in fallback
            if _num(row.get("match_confidence")) >= 0.72
            and 0 < _num(row.get("qty")) <= 100
            and 0 < _num(row.get("amount")) <= 250_000
        ]
        if len(fallback) >= 2:
            for row in fallback:
                row["source_text"] = str(row.get("raw_line") or row.get("item_name") or "")
            rows = fallback
            calculated_total = round(sum(_num(row.get("amount")) for row in rows), 2)
            warnings.append("Paddle handwriting confidence was low; safe local OCR fallback used.")
            raw_text = raw_text + "\n\nTESSERACT FALLBACK:\n" + text
        else:
            raise ValueError(
                "Local handwriting AI could not read this bill reliably. Try a clearer, straighter photo and keep the full bill visible."
            )

    party_matches = legacy._party_matches(raw_text, parties, "purchase") if raw_text else []
    return {
        "items": rows,
        "party_matches": party_matches,
        "ocr_text": "Kirana Handwriting AI v1 (local, no Gemini)\n" + raw_text,
        "detected_lines": len(rows),
        "detected_total": detected_total,
        "calculated_total": calculated_total,
        "warnings": warnings,
    }


@app.middleware("http")
async def local_handwriting_ai(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"

    if request.method == "POST" and path == "/api/photo-bill/learn":
        session = _session_row(request.cookies.get(COOKIE_NAME))
        if not session:
            return RedirectResponse("/owner-login", status_code=303)
        try:
            payload = await request.json()
            rows = payload.get("rows") if isinstance(payload, dict) else []
            with db() as conn:
                learned = _learn_aliases(conn, int(session["business_id"]), list(rows or []))
            return JSONResponse(
                {"ok": True, "learned": learned, "version": VERSION},
                headers={"Cache-Control": "no-store", "X-Kirana-Local-AI": VERSION},
            )
        except Exception as exc:
            return JSONResponse({"detail": f"Learning update failed: {exc}"}, status_code=400)

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

        result = await asyncio.to_thread(_local_extract, raw, int(session["business_id"]))
        # Re-evaluate party matching according to selected bill type when needed.
        if bill_type == "sale":
            with db() as conn:
                parties = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT * FROM parties WHERE business_id=? ORDER BY name,id",
                        (int(session["business_id"]),),
                    ).fetchall()
                ]
            result["party_matches"] = legacy._party_matches(result.get("ocr_text", ""), parties, bill_type)

        return JSONResponse(
            {
                "bill_type": bill_type,
                "invoice_no": "",
                "invoice_date": "",
                **result,
                "reader": "kirana_handwriting_local_v1",
                "version": VERSION,
            },
            headers={
                "Cache-Control": "no-store",
                "X-Kirana-Photo-Reader": VERSION,
                "X-Kirana-AI-Provider": "local",
            },
        )
    except ValueError as exc:
        return JSONResponse(
            {"detail": str(exc), "reader": "kirana_handwriting_local_v1", "version": VERSION},
            status_code=422,
            headers={"Cache-Control": "no-store"},
        )
    except Exception as exc:
        return JSONResponse(
            {
                "detail": f"Local handwriting AI failed safely: {exc}",
                "reader": "kirana_handwriting_local_v1",
                "version": VERSION,
            },
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )
