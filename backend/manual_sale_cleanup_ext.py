from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

import backend.sale_workflow_ext as workflow
from backend.app import STATIC_DIR, app, current_user, db


def _manual_candidates(conn: Any, business_id: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in workflow._sale_batch_stats(conn, business_id):
        # The broken import creates almost one invoice per Item Details row.
        # Keep this deliberately strict so normal small/mostly single-item sales
        # are not selected automatically.
        if "salereport" not in str(row.get("file_key") or ""):
            continue
        if int(row.get("transactions") or 0) < 100:
            continue
        if float(row.get("one_line_ratio") or 0) < 0.95:
            continue
        candidates.append(row)
    return candidates


@app.post("/api/import/manual-itemwise-sales")
def manual_itemwise_sales(
    execute: bool = Query(False),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")

    with db() as conn:
        candidates = _manual_candidates(conn, user["business_id"])
        removed = 0
        if execute:
            for batch in candidates:
                removed += workflow._rollback_sale_batch(
                    conn,
                    user["business_id"],
                    int(batch["batch_id"]),
                )
            conn.execute(
                """
                DELETE FROM items
                WHERE business_id=? AND sku LIKE 'IMP-%'
                  AND ABS(COALESCE(stock,0))<0.000001
                  AND NOT EXISTS (SELECT 1 FROM sale_items WHERE sale_items.item_id=items.id)
                  AND NOT EXISTS (SELECT 1 FROM purchase_items WHERE purchase_items.item_id=items.id)
                  AND NOT EXISTS (SELECT 1 FROM return_items WHERE return_items.item_id=items.id)
                """,
                (user["business_id"],),
            )

    return {
        "execute": execute,
        "batch_count": len(candidates),
        "transaction_count": sum(int(row.get("transactions") or 0) for row in candidates),
        "removed": removed,
        "batches": candidates,
    }


# Imported after sale_workflow_ext. Serve the root once with every browser
# extension plus the always-visible manual cleanup control.
@app.middleware("http")
async def inject_manual_cleanup_assets(request, call_next):
    if request.method == "GET" and request.url.path == "/":
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        html = html.replace(
            "</head>",
            '<link rel="stylesheet" href="/settings-v2.css?v=042" /></head>',
        )
        html = html.replace(
            "</body>",
            '<script src="/settings-v2.js?v=042"></script>'
            '<script src="/import-fix.js?v=044"></script>'
            '<script src="/activity-navigation.js?v=043"></script>'
            '<script src="/sale-item-picker.js?v=044"></script>'
            '<script src="/manual-sale-cleanup.js?v=045"></script></body>',
        )
        return HTMLResponse(
            html,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
            },
        )
    return await call_next(request)


# Keep the endpoint before the SPA fallback route.
new_paths = {"/api/import/manual-itemwise-sales"}
new_routes = [route for route in app.router.routes if getattr(route, "path", None) in new_paths]
for route in new_routes:
    app.router.routes.remove(route)
fallback_index = next(
    (index for index, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
    len(app.router.routes),
)
app.router.routes[fallback_index:fallback_index] = new_routes
