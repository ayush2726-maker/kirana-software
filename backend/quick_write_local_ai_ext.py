from __future__ import annotations

import re
from typing import Any

import backend.quick_write_canvas_fix_ext as quick_canvas
import backend.local_handwriting_ai_ext as local_ai

VERSION = "157"


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


def _local_quick_extract(raw: bytes) -> list[dict[str, Any]]:
    """Fast local Quick Write reader: LEFT qty | MIDDLE item | RIGHT rate."""
    fragments, width, _height = local_ai._paddle_fragments(raw)
    lines = local_ai._group_lines(fragments)
    out: list[dict[str, Any]] = []

    for line in lines:
        parts = list(line.get("parts") or [])
        if not parts:
            continue

        # Spatial columns are deliberate in the user's handwritten format.
        left = [p for p in parts if float(p.get("cx") or 0) < width * 0.27]
        right = [p for p in parts if float(p.get("cx") or 0) > width * 0.70]
        middle = [p for p in parts if width * 0.22 <= float(p.get("cx") or 0) <= width * 0.78]

        qty = 1.0
        if left:
            qtext = " ".join(str(p.get("text") or "") for p in left)
            q = _num_text(qtext)
            if 0 < q <= 999:
                qty = q

        rate = 0.0
        if right:
            rtext = " ".join(str(p.get("text") or "") for p in right)
            r = _num_text(rtext)
            if 0 < r <= 250000:
                rate = r

        # Remove numeric-only edge fragments from item text.
        item_parts = []
        for p in middle:
            text = str(p.get("text") or "").strip()
            cx = float(p.get("cx") or 0)
            if cx < width * 0.30 and _num_text(text) > 0 and re.fullmatch(r"[\s\d०-९./½¼¾-]+", text):
                continue
            if cx > width * 0.68 and _num_text(text) > 0 and re.fullmatch(r"[\s₹\d०-९.,/-]+", text):
                continue
            item_parts.append(text)
        item_text = " ".join(x for x in item_parts if x).strip()
        if not item_text:
            # Fallback: use line text minus obvious left/right numeric tokens.
            item_text = str(line.get("text") or "").strip()
            item_text = re.sub(r"^\s*(?:\d+\s*/\s*\d+|[½¼¾]|\d+(?:\.\d+)?)\s+", "", item_text)
            item_text = re.sub(r"\s+₹?\s*\d+(?:\.\d+)?\s*$", "", item_text).strip()

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
            "qty": round(qty, 3),
            "size": size,
            "rate": round(rate, 2),
            "confidence": round(max(0.0, min(1.0, score)), 3),
        })

    if not out:
        raise ValueError("Kirana AI handwriting ko reliably read nahi kar paya. Thoda bada aur seedha likhkar try karein.")
    return out[:40]


# Replace Gemini with local PaddleOCR-based reader. No API quota/network needed.
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

# UI wording + adaptive learning: when user corrects/selects an item, remember
# that raw handwriting alias for next time using the existing local learning API.
html = quick_canvas.HTML
html = html.replace("Handwriting read ho rahi hai…", "Kirana AI handwriting read kar raha hai…")
html = html.replace("Naye items read ho rahe hain…", "Kirana AI naye items read kar raha hai…")
html = html.replace(
    "var got=d.items||[];lines=append?lines.concat(got):got;",
    "var got=d.items||[];lines=append?lines.concat(got):got;",
)
learn_needle = "if(m){x.item_id=Number(m.id);x.item_name=m.name;x.size=m.size||'';"
learn_repl = "if(m){var rawAlias=x.source_text||x.item_name||'';x.item_id=Number(m.id);x.item_name=m.name;x.size=m.size||'';if(rawAlias){fetch('/api/photo-bill/learn',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({rows:[{source_text:rawAlias,item_id:Number(m.id)}]})}).catch(function(){})}"
html = html.replace(learn_needle, learn_repl)
quick_canvas.HTML = html
