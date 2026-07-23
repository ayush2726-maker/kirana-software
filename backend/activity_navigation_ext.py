from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from fastapi import Depends, Query
from fastapi.responses import HTMLResponse

from backend.app import STATIC_DIR, app, current_user, db


# Replace the original activity endpoint. IDs from separate tables cannot be
# compared with each other, so same-date records are mixed category-wise.
for route in list(app.router.routes):
    if getattr(route, "path", None) == "/api/activity":
        app.router.routes.remove(route)


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("entry_date") or ""),
            str(row.get("created_at") or ""),
            int(row.get("id") or 0),
        ),
        reverse=True,
    )


def _date_wise_mix(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_date[str(row.get("entry_date") or "")].append(row)

    result: list[dict[str, Any]] = []
    for entry_date in sorted(by_date, reverse=True):
        categories: dict[str, deque[dict[str, Any]]] = {
            "sale": deque(),
            "purchase": deque(),
            "other": deque(),
        }
        for row in _sort_rows(by_date[entry_date]):
            category = row["kind"] if row.get("kind") in {"sale", "purchase"} else "other"
            categories[category].append(row)

        # A sale and a purchase on the same date are shown next to each other,
        # instead of one complete imported block appearing before the other.
        order = ("sale", "purchase", "other")
        while any(categories[key] for key in order) and len(result) < limit:
            for key in order:
                if categories[key] and len(result) < limit:
                    result.append(categories[key].popleft())
        if len(result) >= limit:
            break
    return result


@app.get("/api/activity")
def mixed_activity(
    limit: int = Query(default=50, ge=1, le=500),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    bid = user["business_id"]
    fetch_limit = min(500, max(limit * 2, 100))
    with db() as conn:
        sales = [dict(row) for row in conn.execute(
            """
            SELECT id,invoice_no AS ref,party_name AS title,invoice_date AS entry_date,
                   total AS amount,due,'sale' AS kind,
                   CASE WHEN due>0 THEN 'unpaid' ELSE 'completed' END AS status,created_at
            FROM sales WHERE business_id=?
            ORDER BY invoice_date DESC,created_at DESC,id DESC LIMIT ?
            """,
            (bid, fetch_limit),
        ).fetchall()]
        purchases = [dict(row) for row in conn.execute(
            """
            SELECT id,invoice_no AS ref,party_name AS title,invoice_date AS entry_date,
                   total AS amount,due,'purchase' AS kind,
                   CASE WHEN due>0 THEN 'unpaid' ELSE 'completed' END AS status,created_at
            FROM purchases WHERE business_id=?
            ORDER BY invoice_date DESC,created_at DESC,id DESC LIMIT ?
            """,
            (bid, fetch_limit),
        ).fetchall()]
        entries = [dict(row) for row in conn.execute(
            """
            SELECT id,title AS ref,COALESCE(NULLIF(party_name,''),title) AS title,
                   entry_date,amount,0 AS due,entry_type AS kind,status,created_at
            FROM business_entries WHERE business_id=?
            ORDER BY entry_date DESC,created_at DESC,id DESC LIMIT ?
            """,
            (bid, fetch_limit),
        ).fetchall()]
        documents = [dict(row) for row in conn.execute(
            """
            SELECT id,doc_no AS ref,COALESCE(NULLIF(party_name,''),kind) AS title,
                   doc_date AS entry_date,amount,0 AS due,kind,status,created_at
            FROM documents WHERE business_id=?
            ORDER BY doc_date DESC,created_at DESC,id DESC LIMIT ?
            """,
            (bid, fetch_limit),
        ).fetchall()]
        returns = [dict(row) for row in conn.execute(
            """
            SELECT id,return_no AS ref,party_name AS title,return_date AS entry_date,
                   total AS amount,due,kind,'completed' AS status,created_at
            FROM returns WHERE business_id=?
            ORDER BY return_date DESC,created_at DESC,id DESC LIMIT ?
            """,
            (bid, fetch_limit),
        ).fetchall()]
    return _date_wise_mix(sales + purchases + entries + documents + returns, limit)


# This extension is loaded after settings_ext. It serves the root page with
# both the existing settings bundle and the new navigation/timeline bundle.
@app.middleware("http")
async def inject_activity_navigation_assets(request, call_next):
    if request.method == "GET" and request.url.path == "/":
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        html = html.replace(
            "</head>",
            '<link rel="stylesheet" href="/settings-v2.css?v=042" /></head>',
        )
        html = html.replace(
            "</body>",
            '<script src="/settings-v2.js?v=042"></script>'
            '<script src="/activity-navigation.js?v=043"></script></body>',
        )
        return HTMLResponse(
            html,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
            },
        )
    return await call_next(request)


# Newly registered endpoint must stay before the SPA fallback route.
activity_routes = [
    route for route in app.router.routes
    if getattr(route, "path", None) == "/api/activity"
]
for route in activity_routes:
    app.router.routes.remove(route)
fallback_index = next(
    (index for index, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
    len(app.router.routes),
)
app.router.routes[fallback_index:fallback_index] = activity_routes
