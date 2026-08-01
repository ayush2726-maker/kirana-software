from __future__ import annotations

from fastapi.responses import JSONResponse

from backend.app import app, db


@app.get("/health", include_in_schema=False)
def health() -> JSONResponse:
    """Public Railway health check with a lightweight database probe."""
    try:
        with db() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception as exc:  # pragma: no cover - used by Railway at runtime
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unavailable", "detail": str(exc)[:160]},
        )
    return JSONResponse(status_code=200, content={"status": "ok", "database": "ok"})


# Keep /health before backend.app's SPA catch-all route.
_health_routes = [
    route for route in app.router.routes
    if getattr(route, "path", None) == "/health"
]
for route in _health_routes:
    app.router.routes.remove(route)
_fallback_index = next(
    (
        index for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _health_routes
