from __future__ import annotations

import hashlib
import re
import secrets
import unicodedata
from typing import Any

import backend.app as core
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner
from backend.app import db, now_iso


VERSION = "126"
_ITEM_CACHE: dict[tuple[int, int], dict[str, Any]] = {}
_INVISIBLE = re.compile(r"[\u200B-\u200D\u2060\uFEFF]")
_UNIT_ALIASES = {
    "g": "gm", "gm": "gm", "gms": "gm", "gram": "gm", "grams": "gm",
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
    "ml": "ml", "millilitre": "ml", "millilitres": "ml", "milliliter": "ml", "milliliters": "ml",
    "l": "ltr", "lt": "ltr", "ltr": "ltr", "litre": "ltr", "litres": "ltr", "liter": "ltr", "liters": "ltr",
    "pc": "pcs", "pcs": "pcs", "piece": "pcs", "pieces": "pcs",
    "pkt": "packet", "pkts": "packet", "packet": "packet", "packets": "packet",
}
_UNIT_PATTERN = "|".join(sorted((re.escape(value) for value in _UNIT_ALIASES), key=len, reverse=True))
_TRAILING_PACK = re.compile(
    rf"^(?P<base>.+?)\s+(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>{_UNIT_PATTERN})?$",
    re.IGNORECASE,
)
_TRAILING_GRADE = re.compile(r"^(?P<base>.+?)\s+(?P<size>XXL|XL|L|M|S)$", re.IGNORECASE)


def _tidy(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = _INVISIBLE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _number_label(value: Any) -> str:
    text = _tidy(value)
    try:
        numeric = float(text)
    except (TypeError, ValueError):
        return text
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.8f}".rstrip("0").rstrip(".")


def _normalize_unit(value: Any) -> str:
    unit = _tidy(value).lower().replace(".", "")
    return _UNIT_ALIASES.get(unit, unit)


def normalize_variant_size(value: Any, unit: Any = "") -> str:
    text = _tidy(value)
    if not text:
        return ""
    match = re.fullmatch(rf"(\d+(?:\.\d+)?)\s*({_UNIT_PATTERN})?", text, re.IGNORECASE)
    if not match:
        return text
    normalized_unit = _normalize_unit(match.group(2) or unit)
    return f"{_number_label(match.group(1))}{f' {normalized_unit}' if normalized_unit else ''}".strip()


def split_item_name_size_v2(name: Any, current_size: Any = "", item_unit: Any = "") -> tuple[str, str]:
    """Normalize Vyapar Item Name + size/batch without losing variants."""

    raw_name = _tidy(name)
    explicit_size = normalize_variant_size(current_size, item_unit)
    if not raw_name:
        return raw_name, explicit_size

    translation = ""
    core_name = raw_name
    translation_match = re.search(r"\s*(\([^()]*\))\s*$", raw_name)
    if translation_match:
        translation = _tidy(translation_match.group(1))
        core_name = _tidy(raw_name[: translation_match.start()])

    detected_size = ""
    pack_match = _TRAILING_PACK.match(core_name)
    if pack_match:
        number_text = pack_match.group("number")
        embedded_unit = pack_match.group("unit") or ""
        numeric = float(number_text)
        looks_like_pack = bool(explicit_size or embedded_unit or translation or numeric >= 10)
        if looks_like_pack:
            core_name = _tidy(pack_match.group("base")).rstrip(" -_/.,")
            detected_size = normalize_variant_size(number_text, embedded_unit)

    if not explicit_size and not detected_size and translation:
        grade_match = _TRAILING_GRADE.match(core_name)
        if grade_match:
            core_name = _tidy(grade_match.group("base")).rstrip(" -_/.,")
            detected_size = grade_match.group("size").upper()

    translation_text = _tidy(translation[1:-1]) if translation else ""
    clean_name = f"{core_name}{f' ({translation_text})' if translation_text else ''}".strip()
    return clean_name or raw_name, explicit_size or detected_size


def product_identity(value: Any) -> str:
    name, _ = split_item_name_size_v2(value)
    english_name = re.sub(r"\s*\([^()]*\)\s*$", "", name)
    english_name = re.sub(r"[._,/\\-]+", " ", english_name)
    return _tidy(english_name).casefold()


def _size_identity(value: Any, unit: Any = "") -> str:
    return normalize_variant_size(value, unit).casefold()


def _unique_variant_sku(conn: Any, business_id: int, base_sku: str, clean_size: str) -> str:
    if not base_sku:
        return f"IMP-{secrets.token_hex(3).upper()}"
    existing = conn.execute(
        "SELECT id,size,unit FROM items WHERE business_id=? AND sku=?",
        (business_id, base_sku),
    ).fetchone()
    if not existing or _size_identity(existing["size"], existing["unit"]) == _size_identity(clean_size):
        return base_sku
    suffix = hashlib.sha1(clean_size.casefold().encode("utf-8")).hexdigest()[:6].upper()
    candidate = f"{base_sku}-{suffix}"
    sequence = 2
    while conn.execute(
        "SELECT 1 FROM items WHERE business_id=? AND sku=?",
        (business_id, candidate),
    ).fetchone():
        candidate = f"{base_sku}-{suffix}-{sequence}"
        sequence += 1
    return candidate


def _item_cache(conn: Any, bid: int) -> dict[str, Any]:
    cache_key = (id(conn), bid)
    cached = _ITEM_CACHE.get(cache_key)
    if cached is not None:
        return cached
    by_variant: dict[tuple[str, str], dict[str, Any]] = {}
    sibling_units: dict[str, str] = {}
    for row in conn.execute(
        "SELECT id,name,size,unit,sku FROM items WHERE business_id=?",
        (bid,),
    ).fetchall():
        item = dict(row)
        identity = product_identity(item["name"])
        size_key = _size_identity(item["size"], item["unit"])
        by_variant.setdefault((identity, size_key), item)
        normalized_unit = _normalize_unit(item["unit"])
        if normalized_unit and normalized_unit != "pcs":
            sibling_units.setdefault(identity, normalized_unit)
    cached = {"by_variant": by_variant, "sibling_units": sibling_units}
    if len(_ITEM_CACHE) >= 32:
        _ITEM_CACHE.clear()
    _ITEM_CACHE[cache_key] = cached
    return cached


def find_or_create_item_v2(
    conn: Any,
    bid: int,
    name: str,
    sku: str = "",
    size: str = "",
    unit: str = "pcs",
    batch_id: int | None = None,
) -> int:
    del batch_id
    clean_name, clean_size = split_item_name_size_v2(name, size, unit)
    identity = product_identity(clean_name)
    clean_size_key = _size_identity(clean_size, unit)
    cached = _item_cache(conn, bid)
    by_variant: dict[tuple[str, str], dict[str, Any]] = cached["by_variant"]
    existing_variant = by_variant.get((identity, clean_size_key))
    if existing_variant:
        return int(existing_variant["id"])

    if sku and not clean_size:
        exact_sku = conn.execute(
            "SELECT id,name,size,unit,sku FROM items WHERE business_id=? AND sku=?",
            (bid, sku),
        ).fetchone()
        if exact_sku:
            item = dict(exact_sku)
            by_variant.setdefault(
                (product_identity(item["name"]), _size_identity(item["size"], item["unit"])),
                item,
            )
            return int(item["id"])

    sibling_unit = cached["sibling_units"].get(identity, "")
    normalized_unit = _normalize_unit(unit)
    if (not normalized_unit or normalized_unit == "pcs") and sibling_unit:
        normalized_unit = sibling_unit
    normalized_unit = normalized_unit or "pcs"

    generated_sku = _unique_variant_sku(conn, bid, _tidy(sku), clean_size)
    cursor = conn.execute(
        "INSERT INTO items(business_id,name,sku,unit,size,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        (bid, clean_name or "Imported Item", generated_sku, normalized_unit, clean_size, now_iso(), now_iso()),
    )
    item = {
        "id": int(cursor.lastrowid),
        "name": clean_name or "Imported Item",
        "size": clean_size,
        "unit": normalized_unit,
        "sku": generated_sku,
    }
    by_variant[(identity, clean_size_key)] = item
    if normalized_unit and normalized_unit != "pcs":
        cached["sibling_units"].setdefault(identity, normalized_unit)
    return int(item["id"])


core.split_item_name_size = split_item_name_size_v2
core.find_or_create_item = find_or_create_item_v2


@core.app.on_event("startup")
def normalize_existing_item_variant_fields() -> None:
    """Make old imported name/size fields groupable without deleting history."""

    with db() as conn:
        rows = conn.execute("SELECT id,name,size,unit FROM items").fetchall()
        for row in rows:
            clean_name, clean_size = split_item_name_size_v2(row["name"], row["size"], row["unit"])
            if clean_name == row["name"] and clean_size == str(row["size"] or ""):
                continue
            conn.execute(
                "UPDATE items SET name=?,size=?,updated_at=? WHERE id=?",
                (clean_name, clean_size, now_iso(), row["id"]),
            )


PATCH_JS = core.STATIC_DIR / "owner-item-variants-core.js"
_original_patched_owner_js = stable_owner.patched_owner_js


def patched_owner_js_with_item_variants() -> str:
    script = _original_patched_owner_js()
    if "Vyapar item-size variants v126" in script:
        return script
    marker = "  boot();\n})();"
    if marker not in script:
        raise RuntimeError("Owner boot marker was not found")
    patch = PATCH_JS.read_text(encoding="utf-8")
    return script.replace(marker, f"{patch}\n\n{marker}", 1)


stable_owner.patched_owner_js = patched_owner_js_with_item_variants
stable_owner.VERSION = VERSION
final_owner.BUILD = VERSION
