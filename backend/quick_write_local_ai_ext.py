from __future__ import annotations

import re
from io import BytesIO
from typing import Any

from PIL import Image, ImageOps, ImageEnhance
import pytesseract

import backend.quick_write_canvas_fix_ext as quick_canvas
import backend.local_handwriting_ai_ext as local_ai

VERSION = "158"


def _num_text(text: Any) -> float:
    s = str(text or "").strip().translate(local_ai.DEVANAGARI_DIGITS)
    s = s.replace("½", "0.5").replace("¼", "0.25").replace("¾", "0.75")
    m = re.search(r"(?<!\d)(\d+\s*/\s*\d+)(?!\d)", s)
    if m:
        try:
            a, b = [float(x.strip()) for x in m.group(1).split("/", 1)]
            if b:
                return a / b
        except Exception:
            pass
    nums = re.findall(r"\d+(?:\.\d+)?", s.replace(",", ""))
    return float(nums[-1]) if nums else 0.0


def _prepare(raw: bytes) -> Image.Image:
    img = Image.open(BytesIO(raw))
    img = ImageOps.exif_transpose(img).convert("L")
    # Canvas is already clean white/black; mild contrast improves handwriting OCR.
    img = ImageEnhance.Contrast(img).enhance(1.8)
    if img.width < 900:
        scale = 900 / max(1, img.width)
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    return img


def _ocr_words(raw: bytes) -> tuple[list[dict[str, Any]], int, int]:
    img = _prepare(raw)
    configs = [
        ("hin+eng", "--oem 3 --psm 6"),
        ("eng", "--oem 3 --psm 6"),
    ]
    last_exc = None
    for lang, config in configs:
        try:
            data = pytesseract.image_to_data(img, lang=lang, config=config, output_type=pytesseract.Output.DICT)
            words: list[dict[str, Any]] = []
            n = len(data.get("text", []))
            for i in range(n):
                text = str(data["text"][i] or "").strip()
                if not text:
                    continue
                try:
                    conf = float(data.get("conf", [0] * n)[i])
                except Exception:
                    conf = 0.0
                x = float(data["left"][i]); y = float(data["top"][i])
                w = float(data["width"][i]); h = float(data["height"][i])
                words.append({
                    "text": text,
                    "score": max(0.0, min(1.0, conf / 100.0)),
                    "x1": x,
                    "y1": y,
                    "x2": x + w,
                    "y2": y + h,
                    "cx": x + w / 2.0,
                    "cy": y + h / 2.0,
                    "h": max(1.0, h),
                    "line": (data.get("block_num", [0]*n)[i], data.get("par_num", [0]*n)[i], data.get("line_num", [0]*n)[i]),
                })
            if words:
                return words, img.width, img.height
        except Exception as exc:
            last_exc = exc
    if last_exc:
        raise last_exc
    return [], img.width, img.height


def _group(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    by_line: dict[Any, list[dict[str, Any]]] = {}
    for w in words:
        by_line.setdefault(w.get("line"), []).append(w)
    lines = [sorted(v, key=lambda x: x["x1"]) for v in by_line.values()]
    return sorted(lines, key=lambda row: sum(x["cy"] for x in row) / max(1, len(row)))


def _local_quick_extract(raw: bytes) -> list[dict[str, Any]]:
    """Local Quick Write reader: LEFT qty | MIDDLE item | RIGHT rate."""
    words, width, _height = _ocr_words(raw)
    lines = _group(words)
    out: list[dict[str, Any]] = []

    for parts in lines:
        if not parts:
            continue
        # Fixed spatial bill format: left qty, middle item, right rate.
        left = [p for p in parts if p["cx"] < width * 0.23]
        right = [p for p in parts if p["cx"] > width * 0.72]
        middle = [p for p in parts if width * 0.18 <= p["cx"] <= width * 0.82]

        qty = 1.0
        qtext = " ".join(p["text"] for p in left)
        q = _num_text(qtext)
        if 0 < q <= 999:
            qty = q

        rate = 0.0
        rtext = " ".join(p["text"] for p in right)
        r = _num_text(rtext)
        if 0 < r <= 250000:
            rate = r

        item_parts: list[str] = []
        for p in middle:
            text = str(p["text"] or "").strip()
            # Ignore edge-column pure numbers from item text.
            pure_num = bool(re.fullmatch(r"[\s₹\d०-९.,/½¼¾-]+", text))
            if pure_num and (p["cx"] < width * 0.30 or p["cx"] > width * 0.68):
                continue
            item_parts.append(text)
        item_text = " ".join(x for x in item_parts if x).strip()

        # If OCR merged a full row, remove first qty and last rate numerically.
        if not item_text:
            full = " ".join(p["text"] for p in parts).strip()
            full = re.sub(r"^\s*(?:\d+\s*/\s*\d+|[½¼¾]|\d+(?:\.\d+)?)\s+", "", full)
            full = re.sub(r"\s+₹?\s*\d+(?:\.\d+)?\s*$", "", full).strip()
            item_text = full

        size = local_ai._size_from_text(item_text)
        if size:
            item_text = local_ai.SIZE_RE.sub(" ", item_text, count=1)
            item_text = re.sub(r"\s+", " ", item_text).strip()

        norm = local_ai._normalize(item_text)
        if len(norm) < 2 or re.fullmatch(r"[0-9 ]+", norm or ""):
            continue

        score = sum(float(p.get("score") or 0) for p in parts) / max(1, len(parts))
        out.append({
            "item_name": item_text[:160],
            "source_text": item_text[:160],
            "qty": round(qty, 3),
            "size": size,
            "rate": round(rate, 2),
            "confidence": round(max(0.0, min(1.0, score)), 3),
        })

    if not out:
        raise ValueError("Kirana AI handwriting ko read nahi kar paya. Thoda bada aur ek row me Qty | Item | Rate likhkar try karein.")
    return out[:40]


# Replace Gemini/Paddle with lightweight local OCR. No API quota, numpy or Paddle required.
quick_canvas._gemini_canvas_extract = _local_quick_extract

# Preserve handwritten right-column rate. Catalog/last-billed rate is only fallback.
_original_rows_from_ai = quick_canvas._rows_from_ai


def _rows_from_ai_local(ai_rows, items, bill_type, conn, bid):
    rows = _original_rows_from_ai(ai_rows, items, bill_type, conn, bid)
    for idx, row in enumerate(rows):
        if idx >= len(ai_rows):
            break
        handwritten_rate = quick_canvas.quick._number(ai_rows[idx].get("rate"), 0.0)
        if handwritten_rate > 0:
            row["rate"] = round(handwritten_rate, 2)
    return rows


quick_canvas._rows_from_ai = _rows_from_ai_local
quick_canvas.VERSION = VERSION

# UI wording + adaptive learning: when user corrects/selects an item, remember alias.
html = quick_canvas.HTML
html = html.replace("Handwriting read ho rahi hai…", "Kirana AI handwriting read kar raha hai…")
html = html.replace("Naye items read ho rahe hain…", "Kirana AI naye items read kar raha hai…")
learn_needle = "if(m){x.item_id=Number(m.id);x.item_name=m.name;x.size=m.size||'';"
learn_repl = "if(m){var rawAlias=x.source_text||x.item_name||'';x.item_id=Number(m.id);x.item_name=m.name;x.size=m.size||'';if(rawAlias){fetch('/api/photo-bill/learn',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({rows:[{source_text:rawAlias,item_id:Number(m.id)}]})}).catch(function(){})}"
html = html.replace(learn_needle, learn_repl)
quick_canvas.HTML = html
