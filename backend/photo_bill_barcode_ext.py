from __future__ import annotations

import base64
import html
import re
from difflib import SequenceMatcher
from io import BytesIO
from typing import Any

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError
from barcode import Code128
from barcode.writer import SVGWriter
from fastapi import Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from backend.app import STATIC_DIR, app, current_user, db
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner


VERSION = "135"
SMART_PAGE = STATIC_DIR / "owner-smart-tools.html"
LAUNCHER_FILE = STATIC_DIR / "owner-smart-tools-launcher.js"
LAUNCHER_URL = f"/owner-smart-tools-launcher.js?v={VERSION}"
MAX_IMAGE_BYTES = 12 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 30_000_000

if LAUNCHER_URL not in native_owner.OPTIONAL_JS_URLS:
    native_owner.OPTIONAL_JS_URLS.append(LAUNCHER_URL)
if LAUNCHER_FILE not in final_owner.JS_FILES:
    final_owner.JS_FILES.append(LAUNCHER_FILE)

_previous_stable_owner_page = stable_owner.stable_owner_page


def stable_owner_page_with_smart_tools(token: str) -> HTMLResponse:
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


stable_owner.stable_owner_page = stable_owner_page_with_smart_tools


def _owner_session(request: Request):
    return _session_row(request.cookies.get(COOKIE_NAME))


def _normalize(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9\u0900-\u097f]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value or "").replace(",", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        return default


def _preprocess_image(raw: bytes) -> Image.Image:
    try:
        image = Image.open(BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Photo could not be read. Use JPG, PNG or WEBP.") from exc
    if image.width < 300 or image.height < 300:
        raise HTTPException(status_code=400, detail="Photo is too small. Take a clearer full-bill photo.")
    if image.width * image.height > 30_000_000:
        raise HTTPException(status_code=413, detail="Photo resolution is too large.")
    image = image.convert("L")
    image = ImageOps.autocontrast(image)
    if image.width < 1800:
        scale = min(2.0, 1800.0 / max(1, image.width))
        image = image.resize((int(image.width * scale), int(image.height * scale)))
    image = ImageEnhance.Contrast(image).enhance(1.35)
    image = image.filter(ImageFilter.SHARPEN)
    return image


def _ocr_text(raw: bytes) -> str:
    image = _preprocess_image(raw)
    try:
        text = pytesseract.image_to_string(image, lang="eng+hin", config="--oem 3 --psm 6")
    except pytesseract.TesseractNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Bill photo reader is not installed on the server.") from exc
    except pytesseract.TesseractError:
        try:
            text = pytesseract.image_to_string(image, lang="eng", config="--oem 3 --psm 6")
        except Exception as exc:
            raise HTTPException(status_code=422, detail="Photo text could not be read. Try a clearer photo.") from exc
    return str(text or "").strip()


def _invoice_number(text: str) -> str:
    patterns = [
        r"(?:invoice|inv|bill)\s*(?:no\.?|number|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]{1,29})",
        r"(?:voucher|receipt)\s*(?:no\.?|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]{1,29})",
    ]
    upper = text.upper()
    for pattern in patterns:
        match = re.search(pattern, upper, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip("-:/ ")[:30]
    return ""


def _invoice_date(text: str) -> str:
    patterns = [
        r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b",
        r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})\b",
        r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2})\b",
    ]
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            if index == 0:
                year, month, day = [int(part) for part in match.groups()]
            else:
                day, month, year = [int(part) for part in match.groups()]
                if year < 100:
                    year += 2000
            if 1 <= month <= 12 and 1 <= day <= 31:
                return f"{year:04d}-{month:02d}-{day:02d}"
        except Exception:
            pass
    return ""


def _match_score(line: str, item: dict[str, Any]) -> float:
    candidate = _normalize(f"{item.get('name', '')} {item.get('size', '')}")
    haystack = _normalize(line)
    if not candidate or not haystack:
        return 0.0
    if candidate in haystack:
        return 0.99
    name = _normalize(item.get("name"))
    if name and name in haystack:
        return 0.94
    item_tokens = {token for token in candidate.split() if len(token) > 1}
    line_tokens = {token for token in haystack.split() if len(token) > 1}
    overlap = len(item_tokens & line_tokens) / max(1, len(item_tokens))
    sequence = SequenceMatcher(None, candidate, haystack).ratio()
    return max(sequence, overlap * 0.92)


def _best_item(line: str, items: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    best: dict[str, Any] | None = None
    best_score = 0.0
    for item in items:
        score = _match_score(line, item)
        if score > best_score:
            best = item
            best_score = score
    if best_score < 0.48:
        return None, best_score
    return best, best_score


def _strip_matched_size(line: str, item: dict[str, Any] | None) -> str:
    if not item:
        return line
    size = str(item.get("size") or "").strip()
    if not size:
        return line
    escaped = re.escape(size).replace(r"\ ", r"\s*")
    return re.sub(escaped, " ", line, count=1, flags=re.IGNORECASE)


def _line_numbers(line: str) -> list[float]:
    values = re.findall(r"(?<![A-Za-z])(?:₹\s*)?\d[\d,]*(?:\.\d+)?", line)
    return [_number(value) for value in values]


def _looks_like_non_item(line: str) -> bool:
    clean = _normalize(line)
    if len(clean) < 3:
        return True
    prefixes = (
        "invoice ", "bill ", "date ", "gstin ", "gst ", "phone ", "mobile ", "address ",
        "subtotal", "sub total", "grand total", "total ", "net total", "discount", "round off",
        "cgst", "sgst", "igst", "tax ", "amount ", "qty ", "quantity ", "rate ", "hsn ",
        "thank ", "bank ", "upi ", "cash ", "balance ", "paid ", "due ", "terms ",
    )
    return clean.startswith(prefixes)


def _parse_item_lines(text: str, items: list[dict[str, Any]], bill_type: str) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    seen: set[tuple[int | None, str, float, float]] = set()
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip(" |\t")
        if _looks_like_non_item(line):
            continue
        item, score = _best_item(line, items)
        numeric_line = _strip_matched_size(line, item)
        numbers = _line_numbers(numeric_line)
        if not numbers and not item:
            continue

        gst = _number(item.get("gst_rate")) if item else 0.0
        qty = 1.0
        rate = 0.0
        amount = 0.0
        if len(numbers) >= 4 and numbers[-2] in {0.0, 5.0, 12.0, 18.0, 28.0}:
            qty, rate, gst, amount = numbers[-4], numbers[-3], numbers[-2], numbers[-1]
        elif len(numbers) >= 3:
            qty, rate, amount = numbers[-3], numbers[-2], numbers[-1]
        elif len(numbers) == 2:
            qty, rate = numbers[-2], numbers[-1]
            amount = qty * rate
        elif len(numbers) == 1:
            amount = numbers[-1]
            rate = amount

        if qty <= 0 or qty > 100000:
            qty = 1.0
        if rate <= 0 and item:
            rate = _number(item.get("purchase_price" if bill_type == "purchase" else "sale_price"))
        if amount <= 0:
            amount = qty * rate

        if item:
            item_name = str(item.get("name") or "Item")
            size = str(item.get("size") or "")
            item_id = int(item["id"])
        else:
            item_name = re.sub(r"(?:₹\s*)?\d[\d,]*(?:\.\d+)?", " ", line)
            item_name = re.sub(r"\s+", " ", item_name).strip(" -|:.")[:160]
            if len(item_name) < 2:
                continue
            size = ""
            item_id = None

        key = (item_id, _normalize(item_name), round(qty, 3), round(rate, 2))
        if key in seen:
            continue
        seen.add(key)
        parsed.append(
            {
                "item_id": item_id,
                "item_name": item_name,
                "size": size,
                "qty": round(qty, 3),
                "rate": round(rate, 2),
                "gst_rate": round(gst, 2),
                "amount": round(amount, 2),
                "match_confidence": round(score, 3),
                "raw_line": line[:300],
            }
        )
        if len(parsed) >= 80:
            break
    return parsed


def _party_matches(text: str, parties: list[dict[str, Any]], bill_type: str) -> list[dict[str, Any]]:
    haystack = _normalize(" ".join(text.splitlines()[:12]))
    wanted = "supplier" if bill_type == "purchase" else "customer"
    scored: list[tuple[float, dict[str, Any]]] = []
    for party in parties:
        if str(party.get("type") or "") not in {wanted, "both"}:
            continue
        name = _normalize(party.get("name"))
        if not name:
            continue
        score = 0.97 if name in haystack else SequenceMatcher(None, name, haystack).ratio()
        if score >= 0.35:
            scored.append((score, party))
    scored.sort(key=lambda row: row[0], reverse=True)
    return [
        {"id": int(party["id"]), "name": party.get("name"), "score": round(score, 3)}
        for score, party in scored[:5]
    ]


@app.post("/api/photo-bill/ocr")
async def photo_bill_ocr(
    file: UploadFile = File(...),
    bill_type: str = Form(default="purchase"),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    clean_type = str(bill_type or "purchase").strip().lower()
    if clean_type not in {"sale", "purchase"}:
        raise HTTPException(status_code=400, detail="Bill type must be sale or purchase")
    content_type = str(file.content_type or "").lower()
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload a bill photo (JPG, PNG or WEBP).")
    raw = await file.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Photo is too large. Maximum size is 12 MB.")
    if not raw:
        raise HTTPException(status_code=400, detail="Photo file is empty.")

    text = _ocr_text(raw)
    if len(_normalize(text)) < 8:
        raise HTTPException(status_code=422, detail="Very little text was detected. Take a clearer, straight photo in good light.")

    bid = int(user["business_id"])
    with db() as conn:
        items = [dict(row) for row in conn.execute(
            "SELECT id,name,size,unit,barcode,gst_rate,purchase_price,sale_price FROM items WHERE business_id=? ORDER BY name,size",
            (bid,),
        ).fetchall()]
        parties = [dict(row) for row in conn.execute(
            "SELECT id,name,type,phone FROM parties WHERE business_id=? ORDER BY name",
            (bid,),
        ).fetchall()]

    lines = _parse_item_lines(text, items, clean_type)
    return {
        "bill_type": clean_type,
        "invoice_no": _invoice_number(text),
        "invoice_date": _invoice_date(text),
        "items": lines,
        "party_matches": _party_matches(text, parties, clean_type),
        "ocr_text": text[:20000],
        "detected_lines": len(lines),
    }


class BarcodeGenerateIn(BaseModel):
    item_ids: list[int] = Field(default_factory=list)
    force: bool = False


def _barcode_value(business_id: int, item_id: int) -> str:
    return f"KS{business_id:04d}{item_id:08d}"


def _ensure_barcodes(conn: Any, business_id: int, item_ids: list[int], force: bool = False) -> list[dict[str, Any]]:
    if not item_ids:
        return []
    clean_ids = list(dict.fromkeys(int(item_id) for item_id in item_ids if int(item_id) > 0))[:300]
    placeholders = ",".join("?" for _ in clean_ids)
    rows = [dict(row) for row in conn.execute(
        f"SELECT id,name,size,unit,barcode,sale_price FROM items WHERE business_id=? AND id IN ({placeholders}) ORDER BY name,size",
        [business_id, *clean_ids],
    ).fetchall()]
    for row in rows:
        if force or not str(row.get("barcode") or "").strip():
            value = _barcode_value(business_id, int(row["id"]))
            conn.execute("UPDATE items SET barcode=?,updated_at=datetime('now') WHERE id=? AND business_id=?", (value, row["id"], business_id))
            row["barcode"] = value
    return rows


@app.post("/api/barcodes/generate")
def generate_barcodes(
    payload: BarcodeGenerateIn,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    with db() as conn:
        rows = _ensure_barcodes(conn, int(user["business_id"]), payload.item_ids, payload.force)
    return {"items": rows, "count": len(rows)}


def _barcode_svg(value: str) -> str:
    output = BytesIO()
    Code128(str(value), writer=SVGWriter()).write(
        output,
        options={
            "module_width": 0.22,
            "module_height": 10.0,
            "quiet_zone": 1.2,
            "font_size": 7,
            "text_distance": 1.2,
            "write_text": True,
        },
    )
    return "data:image/svg+xml;base64," + base64.b64encode(output.getvalue()).decode("ascii")


@app.get("/owner/smart-tools", response_class=HTMLResponse)
def owner_smart_tools(request: Request):
    if not _owner_session(request):
        return RedirectResponse("/owner-login", status_code=303)
    page = SMART_PAGE.read_text(encoding="utf-8")
    return HTMLResponse(
        page,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Kirana-Smart-Tools": VERSION,
        },
    )


@app.get("/owner/barcodes/print", response_class=HTMLResponse)
def print_barcodes(
    request: Request,
    ids: str = Query(default=""),
    copies: int = Query(default=1, ge=1, le=20),
):
    session = _owner_session(request)
    if not session:
        return RedirectResponse("/owner-login", status_code=303)
    item_ids: list[int] = []
    for raw in str(ids or "").split(","):
        try:
            value = int(raw.strip())
        except ValueError:
            continue
        if value > 0 and value not in item_ids:
            item_ids.append(value)
        if len(item_ids) >= 300:
            break
    if not item_ids:
        return HTMLResponse("Select at least one item", status_code=400)

    with db() as conn:
        rows = _ensure_barcodes(conn, int(session["business_id"]), item_ids)
    labels: list[str] = []
    for row in rows:
        barcode_value = str(row.get("barcode") or "").strip()
        if not barcode_value:
            continue
        label = (
            "<article class='label'>"
            f"<b>{html.escape(str(row.get('name') or 'Item'))}</b>"
            f"<span>{html.escape(str(row.get('size') or ''))}</span>"
            f"<img src='{_barcode_svg(barcode_value)}' alt='Barcode' />"
            "</article>"
        )
        labels.extend([label] * copies)
    body = "".join(labels)
    return HTMLResponse(
        f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Barcode Labels</title><style>
*{{box-sizing:border-box}}body{{margin:0;font-family:Arial,sans-serif;background:#eef5f8;color:#17212b}}.toolbar{{position:sticky;top:0;display:flex;justify-content:center;gap:10px;padding:10px;background:white;border-bottom:1px solid #ccd8df;z-index:2}}.toolbar a,.toolbar button{{border:0;border-radius:9px;padding:10px 16px;font-weight:800;text-decoration:none}}.toolbar a{{background:#eef2f5;color:#17212b}}.toolbar button{{background:#0b82c2;color:white}}.sheet{{width:194mm;margin:10mm auto;display:grid;grid-template-columns:repeat(3,1fr);gap:3mm}}.label{{height:28mm;background:white;border:.25mm solid #cfd7dd;padding:2mm;display:grid;grid-template-rows:auto auto 1fr;align-items:center;text-align:center;overflow:hidden;break-inside:avoid}}.label b{{font-size:9pt;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.label span{{font-size:7pt;min-height:3mm;color:#596671}}.label img{{width:100%;height:17mm;object-fit:contain}}@media print{{@page{{size:A4 portrait;margin:8mm}}body{{background:white}}.toolbar{{display:none!important}}.sheet{{width:auto;margin:0;gap:3mm}}.label{{border:.2mm solid #bbb}}}}@media(max-width:700px){{.sheet{{width:auto;margin:10px;grid-template-columns:1fr 1fr}}}}
</style></head><body><nav class='toolbar'><a href='/owner/smart-tools#barcode'>← Back</a><button onclick='window.print()'>Print Labels</button></nav><main class='sheet'>{body}</main></body></html>""",
        headers={"Cache-Control": "no-store", "X-Kirana-Barcode-Print": VERSION},
    )


@app.middleware("http")
async def serve_owner_smart_tools_launcher(request: Request, call_next):
    if request.method == "GET" and request.url.path.rstrip("/") == "/owner-smart-tools-launcher.js":
        return Response(
            LAUNCHER_FILE.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"},
        )
    return await call_next(request)


# Keep explicit pages ahead of the frontend catch-all route.
for wanted_path in ("/owner/smart-tools", "/owner/barcodes/print"):
    matches = [route for route in list(app.router.routes) if getattr(route, "path", None) == wanted_path]
    for route in matches:
        app.router.routes.remove(route)
    fallback_index = next(
        (index for index, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
        len(app.router.routes),
    )
    app.router.routes[fallback_index:fallback_index] = matches
