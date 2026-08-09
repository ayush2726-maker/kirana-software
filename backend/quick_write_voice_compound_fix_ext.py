from __future__ import annotations

import re
from typing import Any

import backend.quick_write_canvas_fix_ext as quick_canvas
import backend.quick_write_voice_accuracy_ext as voice

VERSION = "168"

_NUMBER = r"(?:\d+(?:\.\d+)?|½|¼|¾)"
_UNIT = voice.UNIT_PATTERN
_WEIGHT_RE = re.compile(rf"(?P<num>{_NUMBER})\s*(?P<unit>{_UNIT})\b", re.I)
_EXPLICIT_RATE_RE = re.compile(r"(?:rate|रेट|भाव|price|₹|rs\.?|रुपये|रुपया)\s*[:=-]?\s*(\d+(?:\.\d+)?)", re.I)


def _unit(unit: str) -> str:
    return voice.UNIT_ALIASES.get(str(unit or "").strip().lower(), str(unit or "").strip().lower())


def _compound_qty(matches: list[re.Match[str]]) -> tuple[float | None, str]:
    if not matches:
        return None, ""
    units = [_unit(m.group("unit")) for m in matches]
    if all(u in {"kg", "gm"} for u in units):
        kg = 0.0
        for m, u in zip(matches, units):
            n = voice._ntext(m.group("num"))
            kg += n if u == "kg" else n / 1000.0
        return round(kg, 3), "kg"
    if all(u in {"ltr", "ml"} for u in units):
        litres = 0.0
        for m, u in zip(matches, units):
            n = voice._ntext(m.group("num"))
            litres += n if u == "ltr" else n / 1000.0
        return round(litres, 3), "ltr"
    if len(matches) == 1:
        m = matches[0]
        n = voice._ntext(m.group("num"))
        u = units[0]
        if u == "gm":
            return round(n / 1000.0, 3), "kg"
        if u == "ml":
            return round(n / 1000.0, 3), "ltr"
        if u in {"kg", "ltr", "pcs"}:
            return round(n, 3), u
    return None, ""


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


def _rate_from_text(raw: str, work_without_weight: str) -> float:
    explicit = _EXPLICIT_RATE_RE.search(raw)
    if explicit:
        return voice._ntext(explicit.group(1))
    # Keep the old shorthand only when no weight/unit is present: "2 moong 100".
    toks = work_without_weight.split()
    if toks:
        last = voice._spoken_number(toks[-1])
        if last > 0:
            return last
    return 0.0


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
        qty, base_unit = _compound_qty(weight_matches)
        name = _clean_name(raw, weight_matches)
        rate = 0.0

        if weight_matches:
            # Any plain number left after removing weights is not automatically a rate.
            # Rate is accepted only when the user explicitly says rate/price/rupees.
            explicit = _EXPLICIT_RATE_RE.search(raw)
            if explicit:
                rate = voice._ntext(explicit.group(1))
        else:
            work = raw
            toks = work.split()
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

        item, score = quick_canvas._best(name, "", items)
        if item:
            final_rate = rate if rate > 0 else quick_canvas._effective_rate(conn, bid, item, bill_type)
            out.append({
                "source_text": chunk,
                "item_id": int(item["id"]),
                "item_name": str(item.get("name") or name),
                "size": str(item.get("size") or ""),
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
                "size": "",
                "qty": round(float(qty), 3),
                "rate": round(rate, 2),
                "gst_rate": 0,
                "match_confidence": 0,
                "needs_create": True,
                "voice_unit": base_unit,
            })
    return out


# Existing /api/quick-bill/voice-parse route resolves this global at request time,
# so replacing the parser here upgrades the deployed web/Android app without a native APK rebuild.
voice._voice_rows = _voice_rows
voice.VERSION = VERSION
