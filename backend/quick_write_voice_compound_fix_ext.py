from __future__ import annotations

import re
from typing import Any

import backend.quick_write_canvas_fix_ext as quick_canvas
import backend.quick_write_voice_accuracy_ext as voice

VERSION = "169"

_NUMBER = r"(?:\d+(?:\.\d+)?|½|¼|¾)"
_UNIT = voice.UNIT_PATTERN
_WEIGHT_RE = re.compile(rf"(?P<num>{_NUMBER})\s*(?P<unit>{_UNIT})\b", re.I)
_EXPLICIT_RATE_RE = re.compile(r"(?:rate|रेट|भाव|price|₹|rs\.?|रुपये|रुपया)\s*[:=-]?\s*(\d+(?:\.\d+)?)", re.I)


def _unit(unit: str) -> str:
    return voice.UNIT_ALIASES.get(str(unit or "").strip().lower(), str(unit or "").strip().lower())


def _single_weight_qty(m: re.Match[str]) -> tuple[float, str]:
    """One spoken weight means actual quantity.

    Examples: 100g mishri -> 0.1 kg qty; 1kg mishri -> 1 kg qty.
    """
    n = voice._ntext(m.group("num"))
    u = _unit(m.group("unit"))
    if u == "gm":
        return round(n / 1000.0, 3), "kg"
    if u == "ml":
        return round(n / 1000.0, 3), "ltr"
    return round(n, 3), u


def _qty_and_size(matches: list[re.Match[str]]) -> tuple[float | None, str, str]:
    """Kirana speech semantics.

    One weight => quantity.
      100g mishri -> qty .1 kg, no pack size.

    Two weights => first is quantity/count, second is pack size.
      mishri 1 kilo 100g -> qty 1, size 100 gm.
      mishri 2 kilo 500g -> qty 2, size 500 gm.

    This intentionally does NOT add 1kg + 100g into 1.1kg.
    """
    if not matches:
        return None, "", ""
    if len(matches) == 1:
        qty, base_unit = _single_weight_qty(matches[0])
        return qty, "", base_unit

    first, second = matches[0], matches[1]
    qty = voice._ntext(first.group("num"))
    size_num = voice._ntext(second.group("num"))
    size_unit = _unit(second.group("unit"))
    size = voice.normalize_size_label(str(size_num), size_unit)
    return round(qty, 3), size, _unit(first.group("unit"))


def _clean_name(raw: str, matches: list[re.Match[str]]) -> str:
    chars = list(raw)
    for m in matches:
        for i in range(m.start(), m.end()):
            chars[i] = " "
    text = "".join(chars)
    text = _EXPLICIT_RATE_RE.sub(" ", text)
    text = re.sub(r"\b(?:rate|रेट|भाव|price|रुपये|रुपया|rs\.?)\b", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" -,:;|")
    return text


def _voice_rows(text: Any, items: list[dict[str, Any]], bill_type: str, conn: Any, bid: int):
    chunks = [
        c.strip()
        for c in re.split(r"(?:\s+फिर\s+|\s+next\s+|\s+अगला\s+|[,;\n]+)", str(text or "").strip(), flags=re.I)
        if c.strip()
    ]
    out = []
    for chunk in chunks:
        raw = re.sub(r"\s+", " ", chunk).strip()
        if not raw:
            continue

        weight_matches = list(_WEIGHT_RE.finditer(raw))
        qty, spoken_size, base_unit = _qty_and_size(weight_matches)
        name = _clean_name(raw, weight_matches)
        rate = 0.0

        if weight_matches:
            explicit = _EXPLICIT_RATE_RE.search(raw)
            if explicit:
                rate = voice._ntext(explicit.group(1))
        else:
            toks = raw.split()
            if toks:
                first = voice._spoken_number(toks[0])
                if first > 0:
                    qty = first
                    toks = toks[1:]
            if toks:
                last = voice._spoken_number(toks[-1])
                if last > 0:
                    rate = last
                    toks = toks[:-1]
            name = re.sub(r"\s+", " ", " ".join(toks)).strip(" -,:;|")

        if not name:
            continue
        if qty is None or qty <= 0 or qty > 999:
            qty = 1.0

        # Spoken pack size must participate in catalog matching so the correct
        # variant/rate is selected (e.g. Mishri 100 gm vs Mishri 500 gm).
        item, score = quick_canvas._best(name, spoken_size, items)
        if item:
            final_rate = rate if rate > 0 else quick_canvas._effective_rate(conn, bid, item, bill_type)
            out.append({
                "source_text": chunk,
                "item_id": int(item["id"]),
                "item_name": str(item.get("name") or name),
                "size": str(item.get("size") or spoken_size or ""),
                "qty": round(float(qty), 3),
                "rate": round(final_rate, 2),
                "gst_rate": round(quick_canvas.quick._number(item.get("gst_rate")), 2),
                "match_confidence": round(score, 3),
                "needs_create": False,
                "voice_unit": base_unit,
            })
        else:
            out.append({
                "source_text": chunk,
                "item_id": None,
                "item_name": name,
                "size": spoken_size,
                "qty": round(float(qty), 3),
                "rate": round(rate, 2),
                "gst_rate": 0,
                "match_confidence": 0,
                "needs_create": True,
                "voice_unit": base_unit,
            })
    return out


# Existing endpoint resolves this global at request time, so this stays OTA/server-side.
voice._voice_rows = _voice_rows
voice.VERSION = VERSION
