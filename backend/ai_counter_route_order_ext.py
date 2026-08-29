from __future__ import annotations

import backend.ai_counter_ext  # noqa: F401
from backend.app import app


AI_DESK_GET_PATHS = {"/owner/ai-desk", "/api/ai-counter/bootstrap"}


def _move_ai_desk_get_routes_before_spa_fallback() -> None:
    routes = list(app.router.routes)
    selected = [route for route in routes if getattr(route, "path", None) in AI_DESK_GET_PATHS]
    if not selected:
        return
    for route in selected:
        try:
            app.router.routes.remove(route)
        except ValueError:
            pass
    fallback_index = next(
        (
            index
            for index, route in enumerate(app.router.routes)
            if getattr(route, "path", None) == "/{path:path}"
        ),
        len(app.router.routes),
    )
    for offset, route in enumerate(selected):
        app.router.routes.insert(fallback_index + offset, route)


_move_ai_desk_get_routes_before_spa_fallback()
