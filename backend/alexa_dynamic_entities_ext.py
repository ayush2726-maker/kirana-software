from __future__ import annotations

import re
from typing import Any

from ask_sdk_model.dialog import DynamicEntitiesDirective
from ask_sdk_model.er.dynamic import Entity, EntityListItem, EntityValueAndSynonyms, UpdateBehavior

from backend import alexa_hardening_ext as hard
from backend import alexa_https_ext as alexa
from backend.app import db


MAX_DYNAMIC_VALUES = 95  # Alexa limit is 100 entities + synonyms per response.


def _spoken_name(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s*\([^)]*[\u0900-\u097f][^)]*\)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _recent_item_entities(limit: int = 70) -> list[Entity]:
    bid = alexa._business_id()
    with db() as conn:
        rows = conn.execute(
            """
            SELECT i.id, i.name, MAX(s.id) AS last_sale_id
            FROM items i
            LEFT JOIN sale_items si ON si.item_id=i.id
            LEFT JOIN sales s ON s.id=si.sale_id AND s.business_id=i.business_id
            WHERE i.business_id=? AND COALESCE(i.archived_at,'')=''
            GROUP BY i.id, i.name
            ORDER BY (MAX(s.id) IS NOT NULL) DESC, MAX(s.id) DESC, i.name
            LIMIT ?
            """,
            (bid, limit),
        ).fetchall()

    entities: list[Entity] = []
    seen: set[str] = set()
    for row in rows:
        name = _spoken_name(row["name"])
        key = hard._name_key(name)
        if not name or not key or key in seen:
            continue
        seen.add(key)
        entities.append(
            Entity(
                id=f"item_{int(row['id'])}",
                name=EntityValueAndSynonyms(value=name, synonyms=[]),
            )
        )
    return entities


def _customer_entities(limit: int = 25) -> list[Entity]:
    bid = alexa._business_id()
    with db() as conn:
        rows = conn.execute(
            """
            SELECT p.id, p.name, MAX(s.id) AS last_sale_id
            FROM parties p
            LEFT JOIN sales s ON s.party_id=p.id AND s.business_id=p.business_id
            WHERE p.business_id=? AND p.type IN ('customer','both')
            GROUP BY p.id, p.name
            ORDER BY (MAX(s.id) IS NOT NULL) DESC, MAX(s.id) DESC, p.name
            LIMIT ?
            """,
            (bid, limit),
        ).fetchall()

    entities: list[Entity] = []
    seen: set[str] = set()
    for row in rows:
        name = _spoken_name(row["name"])
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        entities.append(
            Entity(
                id=f"customer_{int(row['id'])}",
                name=EntityValueAndSynonyms(value=name, synonyms=[]),
            )
        )
    return entities


def _dynamic_directive() -> DynamicEntitiesDirective | None:
    items = _recent_item_entities(70)
    customers = _customer_entities(25)
    if not items and not customers:
        return None

    types: list[EntityListItem] = []
    if items:
        types.append(EntityListItem(name="ITEM_NAME", values=items[:70]))
    if customers:
        remaining = max(0, MAX_DYNAMIC_VALUES - len(items[:70]))
        if remaining:
            types.append(EntityListItem(name="CUSTOMER_NAME", values=customers[:remaining]))
    return DynamicEntitiesDirective(update_behavior=UpdateBehavior.REPLACE, types=types)


def _attach_dynamic(response):
    try:
        directive = _dynamic_directive()
    except Exception as exc:
        print(f"Alexa dynamic entities skipped: {exc}", flush=True)
        return response
    if not directive or response is None:
        return response
    directives = list(getattr(response, "directives", None) or [])
    directives.append(directive)
    response.directives = directives
    return response


_original_launch = alexa.LaunchRequestHandler.handle
_original_select = alexa.SelectCustomerIntentHandler.handle


def _launch_with_dynamic(self, handler_input):
    return _attach_dynamic(_original_launch(self, handler_input))


def _select_with_dynamic(self, handler_input):
    return _attach_dynamic(_original_select(self, handler_input))


# Refresh the runtime catalog at launch and again after customer selection. This
# keeps ITEM_NAME / CUSTOMER_NAME tied to the live database instead of forcing
# every new product/customer into the static interaction-model JSON.
alexa.LaunchRequestHandler.handle = _launch_with_dynamic
alexa.SelectCustomerIntentHandler.handle = _select_with_dynamic
