from __future__ import annotations

from datetime import datetime

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.app import app, db, now_iso
from backend.saas_ext import ensure_saas_schema


OWNER_ALWAYS_ALLOWED = {
    "/api/saas/me",
    "/api/logout",
    "/api/account/change-password",
    "/api/business",
}

PUBLIC_PREFIXES = (
    "/api/health",
    "/api/setup",
    "/api/login",
    "/api/saas/register-business",
    "/api/saas/business/",
    "/api/saas/platform/",
    "/api/customer/login",
    "/api/customer/register/",
)


def effective_status(row) -> str:
    status = str(row["subscription_status"] or "trial")
    now = datetime.now()
    if status == "trial" and row["trial_ends_at"]:
        if datetime.fromisoformat(row["trial_ends_at"]) <= now:
            return "expired"
    if status == "active" and row["paid_until"]:
        if datetime.fromisoformat(row["paid_until"]) <= now:
            return "expired"
    return status


def blocked_response(status: str) -> JSONResponse:
    if status == "suspended":
        return JSONResponse(
            status_code=403,
            content={"detail": "Business subscription suspended hai. Seller se contact karein.", "subscription_status": status},
        )
    return JSONResponse(
        status_code=402,
        content={"detail": "Trial ya subscription expire ho gayi hai. Plan renew karein.", "subscription_status": "expired"},
    )


@app.middleware("http")
async def enforce_saas_subscription(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/") or path in OWNER_ALWAYS_ALLOWED or path.startswith(PUBLIC_PREFIXES):
        return await call_next(request)

    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return await call_next(request)
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return await call_next(request)

    ensure_saas_schema()
    status: str | None = None
    with db() as conn:
        row = conn.execute(
            """
            SELECT sb.business_id,sb.subscription_status,sb.trial_ends_at,sb.paid_until
            FROM sessions s
            JOIN users u ON u.id=s.user_id
            JOIN saas_businesses sb ON sb.business_id=u.business_id
            WHERE s.token=? AND s.expires_at>?
            """,
            (token, now_iso()),
        ).fetchone()
        if not row:
            row = conn.execute(
                """
                SELECT sb.business_id,sb.subscription_status,sb.trial_ends_at,sb.paid_until
                FROM customer_sessions cs
                JOIN customer_accounts ca ON ca.id=cs.customer_account_id
                JOIN saas_businesses sb ON sb.business_id=ca.business_id
                WHERE cs.token=? AND cs.expires_at>?
                """,
                (token, now_iso()),
            ).fetchone()
        if row:
            status = effective_status(row)
            if status == "expired" and row["subscription_status"] != "expired":
                conn.execute(
                    "UPDATE saas_businesses SET subscription_status='expired',updated_at=? WHERE business_id=?",
                    (now_iso(), row["business_id"]),
                )
    if status in {"expired", "suspended"}:
        return blocked_response(status)
    return await call_next(request)
