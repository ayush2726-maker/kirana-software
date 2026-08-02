from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from fastapi import Depends

from backend.app import app, current_user, db
import backend.customer_self_register_ext as customer_otp


def _utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value or ""))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@app.get("/api/customer/otp-requests")
def owner_otp_requests_timezone_safe(
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    customer_otp.ensure_customer_otp_schema()
    now_utc = datetime.now(timezone.utc)

    with db() as conn:
        rows = conn.execute(
            """
            SELECT o.id,o.party_id,o.phone,o.otp_code,o.status,o.attempts,o.expires_at,o.created_at,
                   p.name AS party_name,b.name AS business_name
            FROM customer_registration_otps o
            JOIN parties p ON p.id=o.party_id
            JOIN businesses b ON b.id=o.business_id
            WHERE o.business_id=? AND o.status='pending'
            ORDER BY o.id DESC LIMIT 100
            """,
            (user["business_id"],),
        ).fetchall()

        active: list[dict[str, Any]] = []
        for raw in rows:
            row = dict(raw)
            try:
                expires_utc = _utc_datetime(row["expires_at"])
            except (TypeError, ValueError):
                conn.execute(
                    "UPDATE customer_registration_otps SET status='expired' WHERE id=? AND business_id=?",
                    (row["id"], user["business_id"]),
                )
                continue

            remaining_seconds = max(0, int((expires_utc - now_utc).total_seconds()))
            if remaining_seconds <= 0:
                conn.execute(
                    "UPDATE customer_registration_otps SET status='expired' WHERE id=? AND business_id=?",
                    (row["id"], user["business_id"]),
                )
                continue

            message = (
                f"{row['business_name']} registration OTP: {row['otp_code']}. "
                f"This OTP is valid for {customer_otp.OTP_MINUTES} minutes. Do not share it with anyone else."
            )
            row["expires_at"] = expires_utc.isoformat()
            row["remaining_seconds"] = remaining_seconds
            row["whatsapp_url"] = f"https://wa.me/91{row['phone']}?text={quote(message)}"
            row["message"] = message
            active.append(row)

    return active


# Remove every older GET implementation and keep only this timezone-safe route.
_latest = []
for route in list(app.router.routes):
    if getattr(route, "path", None) != "/api/customer/otp-requests":
        continue
    app.router.routes.remove(route)
    if getattr(route, "endpoint", None) is owner_otp_requests_timezone_safe:
        _latest.append(route)

_fallback_index = next(
    (
        index
        for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _latest
