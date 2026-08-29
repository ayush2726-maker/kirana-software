from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

import backend.ai_counter_ext as counter

VERSION = "182"
_base_norm = counter._norm

# Common Hindi/Android speech-recognition substitutions seen at the billing desk.
PHRASE_FIXES = {
    "शॉप": "सौंफ",
    "सोप": "सौंफ",
    "शोफ": "सौंफ",
    "सौफ": "सौंफ",
    "shop": "saunf",
    "souf": "saunf",
    "sauf": "saunf",
    "souff": "saunf",
    "चैनल": "चना",
    "चेनल": "चना",
    "चैनल्स": "चना",
    "channel": "chana",
    "channels": "chana",
    "chanel": "chana",
    "चनाा": "चना",
    "कबली": "काबली",
    "kabli": "kabuli",
    "kaabli": "kabuli",
    "kabuli": "kabuli",
    "देशी": "देसी",
    "deshi": "desi",
}

TOKEN_FIXES = {
    "souff": "saunf",
    "sauf": "saunf",
    "souf": "saunf",
    "shop": "saunf",
    "channel": "chana",
    "channels": "chana",
    "chanel": "chana",
    "kabli": "kabuli",
    "kaabli": "kabuli",
    "deshi": "desi",
}

QTY_TOKENS = {
    "kg", "kilogram", "kilo", "g", "gm", "gram", "grams", "ltr", "liter", "litre",
    "pcs", "pc", "piece", "pieces", "packet", "pack", "aadha", "adha", "half", "paav",
    "pav", "quarter", "dedh", "dhai", "sau", "hundred",
}


def _speech_fix(value: Any) -> str:
    text = str(value or "").lower().strip()
    for src, dst in PHRASE_FIXES.items():
        text = text.replace(src, dst)
    norm = _base_norm(text)
    words = [TOKEN_FIXES.get(w, w) for w in norm.split()]
    return " ".join(words).strip()


def _item_query(value: Any) -> str:
    norm = _speech_fix(value)
    words = []
    for w in norm.split():
        if w in QTY_TOKENS:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", w):
            continue
        words.append(w)
    return " ".join(words).strip()


def _score(text: Any, candidate: Any) -> float:
    a = _item_query(text)
    b = _speech_fix(candidate)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    at, bt = set(a.split()), set(b.split())
    if at and at.issubset(bt):
        return 0.97
    if a in b:
        return 0.95
    overlap = len(at & bt) / max(1, len(at))
    seq = SequenceMatcher(None, a, b).ratio()
    return max(overlap * 0.92, seq * 0.82)


def _best_rows(text: Any, rows: list[dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
    query = _item_query(text)
    if not query:
        return []
    ranked: list[tuple[float, float, int, int, int, dict[str, Any]]] = []
    for row in rows:
        name = str(row.get("name") or "")
        label = " ".join(str(row.get(k) or "") for k in ("name", "size", "unit", "sku", "barcode"))
        name_score = _score(query, name)
        overall_score = _score(query, label)
        if max(name_score, overall_score) < 0.52:
            continue
        price_ok = 1 if float(row.get("sale_price") or 0) > 0 else 0
        unit = str(row.get("unit") or "").lower()
        bulk_ok = 1 if unit in {"kg", "kgs", "kilo", "kilogram", "g", "gm", "gram"} else 0
        clean_size = 1 if not str(row.get("size") or "").strip() else 0
        ranked.append((name_score, overall_score, price_ok, bulk_ok, clean_size, row))
    ranked.sort(key=lambda p: (p[0], p[1], p[2], p[3], p[4]), reverse=True)

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name_score, overall_score, _price_ok, _bulk_ok, _clean_size, row in ranked:
        key = f"{_speech_fix(row.get('name'))}|{_speech_fix(row.get('size'))}"
        if key in seen:
            continue
        seen.add(key)
        # Route auto-select threshold uses match_score; use name-first confidence.
        effective = name_score if name_score >= 0.52 else overall_score * 0.88
        out.append({**row, "match_score": round(effective, 3)})
        if len(out) >= limit:
            break
    return out


counter._norm = _speech_fix
counter._score = _score
counter._best_rows = _best_rows
