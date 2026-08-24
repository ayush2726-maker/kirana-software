from __future__ import annotations

import re
from typing import Any

from backend import alexa_hardening_ext as hard
from backend import alexa_https_ext as alexa
from backend.app import db


_DEVANAGARI_RE = re.compile(r"[\u0900-\u097f]")


def _clean_spoken_text(value: Any) -> str:
    """Keep only one readable product name in Alexa speech.

    Database names remain untouched. Parenthetical translations such as
    `Jeera (जीरा)` are removed only from the spoken/displayed Alexa response.
    """
    text = str(value or "")
    text = re.sub(r"\s*\([^)]*[\u0900-\u097f][^)]*\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


_original_speak = alexa._speak


def _speak_clean(handler_input, text: str, reprompt: str | None = None, end: bool = False):
    return _original_speak(
        handler_input,
        _clean_spoken_text(text),
        _clean_spoken_text(reprompt) if reprompt else reprompt,
        end=end,
    )


# Every hardening handler calls alexa._speak at runtime, so this changes only
# Alexa speech/UI text and does not rewrite item names stored in invoices.
alexa._speak = _speak_clean


def _size_is_obviously_dirty(value: Any) -> bool:
    text = alexa._normalize_size(str(value or ""))
    if not text:
        return False
    # Zero-size variants are import artefacts and must never be offered.
    return bool(re.match(r"^0(?:\.0+)?(?:\s|$)", text))


def _last_nonzero_rate_for_item(conn, business_id: int, item_id: int) -> float:
    row = conn.execute(
        """
        SELECT si.rate
        FROM sale_items si
        JOIN sales s ON s.id=si.sale_id
        WHERE s.business_id=? AND si.item_id=? AND COALESCE(si.rate,0)>0
        ORDER BY s.invoice_date DESC, si.id DESC
        LIMIT 1
        """,
        (business_id, item_id),
    ).fetchone()
    return float(row["rate"] or 0) if row else 0.0


def _last_nonzero_family_rate(conn, business_id: int, item: dict[str, Any]) -> float:
    target_name = hard._name_key(item.get("name"))
    target_size = alexa._normalize_size(item.get("size", ""))
    rows = conn.execute(
        """
        SELECT si.rate, i.name, i.size
        FROM sale_items si
        JOIN sales s ON s.id=si.sale_id
        LEFT JOIN items i ON i.id=si.item_id
        WHERE s.business_id=? AND COALESCE(si.rate,0)>0
        ORDER BY s.invoice_date DESC, si.id DESC
        LIMIT 300
        """,
        (business_id,),
    ).fetchall()
    for row in rows:
        if hard._name_key(row["name"] or "") != target_name:
            continue
        if target_size and alexa._normalize_size(row["size"] or "") != target_size:
            continue
        return float(row["rate"] or 0)
    return 0.0


def _row_has_usable_rate(row: dict[str, Any]) -> bool:
    if float(row.get("sale_price") or 0) > 0:
        return True
    bid = alexa._business_id()
    with db() as conn:
        return _last_nonzero_rate_for_item(conn, bid, int(row.get("id") or 0)) > 0 or _last_nonzero_family_rate(conn, bid, row) > 0


_original_candidate_rows = hard._candidate_rows


def _candidate_rows_clean(phrase: str):
    query, requested_size, rows = _original_candidate_rows(phrase)
    rows = [r for r in rows if not _size_is_obviously_dirty(r.get("size"))]

    # Prefer variants that have either a catalog sale rate or a real historical
    # non-zero billed rate. Keep unpriced rows only when no usable variant exists,
    # so valid old products are still discoverable but junk variants do not crowd
    # the voice choice list.
    usable = [r for r in rows if _row_has_usable_rate(r)]
    if usable:
        rows = usable
    return query, requested_size, rows


hard._candidate_rows = _candidate_rows_clean


_original_effective_rate = hard._effective_rate


def _effective_rate_with_history(item_id: int, party_id: int | None):
    rate, source = _original_effective_rate(item_id, party_id)
    if rate > 0:
        return rate, source

    bid = alexa._business_id()
    with db() as conn:
        rate = _last_nonzero_rate_for_item(conn, bid, int(item_id))
        if rate > 0:
            return rate, "last_nonzero_sale"
        row = conn.execute(
            "SELECT id,name,size FROM items WHERE id=? AND business_id=?",
            (int(item_id), bid),
        ).fetchone()
        if row:
            rate = _last_nonzero_family_rate(conn, bid, dict(row))
            if rate > 0:
                return rate, "last_nonzero_variant_sale"
    return 0.0, source


hard._effective_rate = _effective_rate_with_history


# Existing handler functions reference hard._candidate_rows / _effective_rate
# through module globals at runtime, so no handler re-registration is required.
