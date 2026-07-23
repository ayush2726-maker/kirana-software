from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from backend.app import STATIC_DIR, app, now_iso
from backend.settings_ext import ext_user


def _connect() -> sqlite3.Connection:
    from backend.app import DB_PATH

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ean13_check_digit(base12: str) -> str:
    if len(base12) != 12 or not base12.isdigit():
        raise ValueError("EAN-13 base must contain 12 digits")
    total = sum(int(ch) if index % 2 == 0 else int(ch) * 3 for index, ch in enumerate(base12))
    return str((10 - (total % 10)) % 10)


def _internal_ean13(business_id: int, item_id: int, salt: int = 0) -> str:
    # Prefix 29 is intended for restricted/internal distribution. These labels are
    # for the shop's own billing and stock use; they are not a GS1 registration.
    base = f"29{business_id % 10000:04d}{item_id % 100000:05d}{salt % 10}"
    return base + _ean13_check_digit(base)


def _generate_unique_barcode(conn: sqlite3.Connection, business_id: int, item_id: int) -> str:
    for salt in range(10):
        barcode = _internal_ean13(business_id, item_id, salt)
        exists = conn.execute(
            "SELECT 1 FROM items WHERE business_id=? AND barcode=? AND id<>?",
            (business_id, barcode, item_id),
        ).fetchone()
        if not exists:
            return barcode
    timestamp = now_iso().replace("-", "").replace(":", "").replace("T", "")
    digits = "".join(ch for ch in timestamp if ch.isdigit())[-10:].rjust(10, "0")
    base = f"29{digits}"
    return base + _ean13_check_digit(base)


@app.post("/api/items/{item_id}/barcode/generate")
def generate_item_barcode(
    item_id: int,
    force: bool = False,
    user: dict[str, Any] = Depends(ext_user),
) -> dict[str, Any]:
    conn = _connect()
    try:
        item = conn.execute(
            "SELECT id,name,size,barcode FROM items WHERE id=? AND business_id=?",
            (item_id, user["business_id"]),
        ).fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        if item["barcode"] and not force:
            return {"ok": True, "barcode": item["barcode"], "item_id": item_id, "existing": True}
        barcode = _generate_unique_barcode(conn, user["business_id"], item_id)
        conn.execute(
            "UPDATE items SET barcode=?,updated_at=? WHERE id=? AND business_id=?",
            (barcode, now_iso(), item_id, user["business_id"]),
        )
        conn.commit()
        return {"ok": True, "barcode": barcode, "item_id": item_id, "existing": False}
    finally:
        conn.close()


@app.post("/api/items/barcodes/generate-missing")
def generate_missing_barcodes(user: dict[str, Any] = Depends(ext_user)) -> dict[str, Any]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id FROM items WHERE business_id=? AND TRIM(COALESCE(barcode,''))='' ORDER BY id",
            (user["business_id"],),
        ).fetchall()
        generated: list[dict[str, Any]] = []
        for row in rows:
            item_id = int(row["id"])
            barcode = _generate_unique_barcode(conn, user["business_id"], item_id)
            conn.execute(
                "UPDATE items SET barcode=?,updated_at=? WHERE id=? AND business_id=?",
                (barcode, now_iso(), item_id, user["business_id"]),
            )
            generated.append({"item_id": item_id, "barcode": barcode})
        conn.commit()
        return {"ok": True, "count": len(generated), "items": generated}
    finally:
        conn.close()


@app.middleware("http")
async def enforce_managed_user_permissions(request: Request, call_next):
    path = request.url.path
    method = request.method.upper()
    if not path.startswith("/api/") or method in {"GET", "HEAD", "OPTIONS"}:
        return await call_next(request)
    if path in {"/api/setup", "/api/login", "/api/logout"}:
        return await call_next(request)

    authorization = request.headers.get("authorization")
    try:
        user = ext_user(authorization)
    except HTTPException:
        return await call_next(request)

    role = str(user.get("role") or "viewer")
    if role == "viewer":
        return JSONResponse({"detail": "Viewer access is read-only"}, status_code=403)

    if role == "cashier":
        protected_prefixes = (
            "/api/settings",
            "/api/business",
            "/api/import",
            "/api/backup",
            "/api/export",
            "/api/accounts",
        )
        if path.startswith(protected_prefixes) or (path.startswith("/api/items") and "barcode" not in path):
            return JSONResponse({"detail": "Cashier is not allowed to change this section"}, status_code=403)

    if role == "manager" and path.startswith("/api/settings/users"):
        return JSONResponse({"detail": "Only the owner can manage users"}, status_code=403)

    return await call_next(request)


def _no_cache_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }


@app.get("/features-v1.js", include_in_schema=False)
def feature_javascript() -> Response:
    return Response(
        content=(STATIC_DIR / "features-v1.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers=_no_cache_headers(),
    )


@app.get("/features-v1.css", include_in_schema=False)
def feature_stylesheet() -> Response:
    return Response(
        content=(STATIC_DIR / "features-v1.css").read_text(encoding="utf-8"),
        media_type="text/css",
        headers=_no_cache_headers(),
    )


@app.middleware("http")
async def inject_complete_feature_assets(request: Request, call_next):
    if request.method == "GET" and request.url.path == "/":
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        head_assets = (
            '<link rel="stylesheet" href="/settings-v2.css?v=046" />'
            '<link rel="stylesheet" href="/features-v1.css?v=046" />'
        )
        popup_compat = (
            '<script>(function(){var nativeOpen=window.open.bind(window);window.open=function(url,target,features){'
            'var safeFeatures=features==="noopener,noreferrer"?"":features;var opened=nativeOpen(url,target,safeFeatures);'
            'if(opened){try{opened.opener=null}catch(e){}}return opened;};})();</script>'
        )
        body_assets = (
            popup_compat
            + '<script src="/settings-v2.js?v=046"></script>'
            + '<script src="/features-v1.js?v=046"></script>'
        )
        html = html.replace("</head>", f"{head_assets}</head>")
        html = html.replace("</body>", f"{body_assets}</body>")
        return HTMLResponse(html, headers=_no_cache_headers())
    return await call_next(request)


extension_paths = {
    "/api/items/{item_id}/barcode/generate",
    "/api/items/barcodes/generate-missing",
    "/features-v1.js",
    "/features-v1.css",
}
extension_routes = [route for route in app.router.routes if getattr(route, "path", None) in extension_paths]
for route in extension_routes:
    app.router.routes.remove(route)
fallback_index = next(
    (index for index, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
    len(app.router.routes),
)
app.router.routes[fallback_index:fallback_index] = extension_routes
