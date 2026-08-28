from __future__ import annotations

import json
import os
from contextvars import ContextVar

from fastapi import Request

from backend.app import app, db, now_iso
import backend.alexa_https_ext as alexa_https

_current_business_id: ContextVar[int | None] = ContextVar("kirana_alexa_business_id", default=None)
_legacy_business_id = alexa_https._business_id


def _account_linking_required() -> bool:
    return str(os.getenv("ALEXA_REQUIRE_ACCOUNT_LINKING", "0")).strip().lower() in {"1", "true", "yes", "on"}


def _business_from_access_token(token: str) -> int | None:
    token = str(token or "").strip()
    if not token:
        return None
    with db() as conn:
        row = conn.execute(
            """
            SELECT u.business_id
            FROM sessions s
            JOIN users u ON u.id=s.user_id
            WHERE s.token=? AND s.expires_at>?
            LIMIT 1
            """,
            (token, now_iso()),
        ).fetchone()
    if not row:
        return None
    return int(row["business_id"])


def _multiuser_business_id() -> int:
    linked = _current_business_id.get()
    if linked is not None:
        return int(linked)
    if _account_linking_required():
        raise RuntimeError("Alexa account linking is required")
    # Keep the current simulator/live behaviour until Account Linking is turned
    # on in the Alexa console. After that set ALEXA_REQUIRE_ACCOUNT_LINKING=1.
    return _legacy_business_id()


# Existing Alexa handlers resolve the business dynamically through this global,
# so replacing it here upgrades all current intents without duplicating them.
alexa_https._business_id = _multiuser_business_id


def _extract_access_token(payload: dict) -> str:
    context_user = ((((payload.get("context") or {}).get("System") or {}).get("user") or {}))
    session_user = (((payload.get("session") or {}).get("user") or {}))
    return str(context_user.get("accessToken") or session_user.get("accessToken") or "").strip()


@app.middleware("http")
async def kirana_alexa_multiuser_context(request: Request, call_next):
    if request.url.path.rstrip("/") != "/api/alexa":
        return await call_next(request)

    marker = None
    try:
        body = await request.body()
        # Re-feed the body because Alexa's existing endpoint still needs to read it.
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = receive  # type: ignore[attr-defined]
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {}

        token = _extract_access_token(payload)
        business_id = _business_from_access_token(token) if token else None
        marker = _current_business_id.set(business_id)

        if _account_linking_required() and business_id is None:
            # Let the Alexa SDK endpoint return its normal response shape, but force
            # the business resolver to reject data access instead of ever falling
            # back to another shop.
            marker and None

        return await call_next(request)
    finally:
        if marker is not None:
            _current_business_id.reset(marker)


@app.get("/api/alexa/multiuser-health")
def kirana_alexa_multiuser_health():
    return {
        "status": "ok",
        "mode": "multi_user_business_isolation",
        "account_linking_required": _account_linking_required(),
    }
