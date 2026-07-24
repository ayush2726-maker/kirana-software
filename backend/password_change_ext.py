from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.app import app, current_user, db, hash_password, verify_password


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=4, max_length=128)
    confirm_password: str = Field(min_length=4, max_length=128)


@app.post("/api/account/change-password")
def change_password(
    payload: ChangePasswordIn,
    user: dict[str, Any] = Depends(current_user),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirm password do not match")
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=400, detail="New password must be different from current password")

    current_token = ""
    if authorization and authorization.lower().startswith("bearer "):
        current_token = authorization.split(" ", 1)[1].strip()

    with db() as conn:
        account = conn.execute(
            "SELECT id,password_hash FROM users WHERE id=? AND business_id=?",
            (user["user_id"], user["business_id"]),
        ).fetchone()
        if not account:
            raise HTTPException(status_code=404, detail="User account not found")
        if not verify_password(payload.current_password, account["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=? AND business_id=?",
            (hash_password(payload.new_password), user["user_id"], user["business_id"]),
        )
        if current_token:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE user_id=? AND token<>?",
                (user["user_id"], current_token),
            )
        else:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE user_id=?",
                (user["user_id"],),
            )

    return {
        "ok": True,
        "username": user["username"],
        "other_sessions_logged_out": max(0, int(cursor.rowcount or 0)),
        "current_session_active": bool(current_token),
    }


# Keep this endpoint ahead of the SPA fallback route.
paths = {"/api/account/change-password"}
routes = [route for route in app.router.routes if getattr(route, "path", None) in paths]
for route in routes:
    app.router.routes.remove(route)
fallback_index = next(
    (index for index, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
    len(app.router.routes),
)
app.router.routes[fallback_index:fallback_index] = routes
