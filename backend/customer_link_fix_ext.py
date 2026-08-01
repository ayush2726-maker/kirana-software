from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from backend.app import app, db
from backend.saas_ext import ensure_saas_schema


def default_customer_business(conn):
    """Return the primary shop for old customer links that do not contain ?shop=."""
    return conn.execute(
        """
        SELECT sb.business_id,sb.slug,sb.plan,sb.subscription_status,b.name AS business_name
        FROM saas_businesses sb
        JOIN businesses b ON b.id=sb.business_id
        WHERE sb.subscription_status IN ('active','trial')
        ORDER BY
            CASE WHEN sb.plan='legacy' THEN 0 ELSE 1 END,
            sb.business_id ASC
        LIMIT 1
        """
    ).fetchone()


@app.get("/api/saas/default-business")
def public_default_business():
    ensure_saas_schema()
    with db() as conn:
        row = default_customer_business(conn)
    if not row:
        raise HTTPException(status_code=404, detail="Koi active dukaan nahi mili")
    return {
        "business_id": row["business_id"],
        "business_name": row["business_name"],
        "slug": row["slug"],
        "customer_order_path": f"/customer?shop={row['slug']}",
    }


@app.middleware("http")
async def redirect_old_customer_link(request: Request, call_next):
    """Keep previously shared /customer links working after SaaS shop slugs were added."""
    if (
        request.method == "GET"
        and request.url.path.rstrip("/") == "/customer"
        and not request.query_params.get("shop")
    ):
        ensure_saas_schema()
        with db() as conn:
            row = default_customer_business(conn)
        if row:
            target = request.url.include_query_params(shop=row["slug"])
            return RedirectResponse(url=str(target), status_code=307)
    return await call_next(request)


# Keep the public helper endpoint ahead of backend.app's SPA fallback route.
_fix_routes = [
    route
    for route in app.router.routes
    if getattr(route, "path", None) == "/api/saas/default-business"
]
for route in _fix_routes:
    app.router.routes.remove(route)
_fallback_index = next(
    (
        index
        for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _fix_routes
