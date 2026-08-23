from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import Request

from backend.app import app


def _request_meta(payload: dict[str, Any]) -> tuple[str, str, str, str]:
    request_data = payload.get("request") or {}
    request_type = str(request_data.get("type") or "unknown")
    intent_name = "-"
    if request_type == "IntentRequest":
        intent_name = str((request_data.get("intent") or {}).get("name") or "unknown")
    locale = str(request_data.get("locale") or "-")
    request_id = str(request_data.get("requestId") or "")
    request_hash = hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:12] if request_id else "-"
    return request_type, intent_name, locale, request_hash


def _audit_line(event: str, **fields: Any) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    safe_fields = " ".join(f"{key}={value}" for key, value in fields.items())
    print(f"ALEXA_AUDIT ts={timestamp} event={event} {safe_fields}".rstrip(), flush=True)


@app.middleware("http")
async def alexa_request_audit(request: Request, call_next):
    if request.url.path.rstrip("/") != "/api/alexa" or request.method != "POST":
        return await call_next(request)

    started = time.monotonic()
    raw_body = await request.body()
    request_type = "unknown"
    intent_name = "-"
    locale = "-"
    request_hash = "-"

    try:
        payload = json.loads(raw_body.decode("utf-8"))
        request_type, intent_name, locale, request_hash = _request_meta(payload)
    except Exception:
        _audit_line("received", type="invalid_json", intent="-", locale="-", request="-")
    else:
        _audit_line(
            "received",
            type=request_type,
            intent=intent_name,
            locale=locale,
            request=request_hash,
        )

    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": raw_body, "more_body": False}
        return {"type": "http.request", "body": b"", "more_body": False}

    replay_request = Request(request.scope, receive)

    try:
        response = await call_next(replay_request)
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        _audit_line(
            "failed",
            type=request_type,
            intent=intent_name,
            request=request_hash,
            error=type(exc).__name__,
            duration_ms=elapsed_ms,
        )
        raise

    elapsed_ms = int((time.monotonic() - started) * 1000)
    _audit_line(
        "completed",
        type=request_type,
        intent=intent_name,
        request=request_hash,
        status=response.status_code,
        duration_ms=elapsed_ms,
    )
    return response
