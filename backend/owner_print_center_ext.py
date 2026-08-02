from __future__ import annotations

import html
from typing import Any

from fastapi import Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from backend.app import STATIC_DIR, app, current_user, db
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner
import backend.transaction_share_print_ext as print_ext


VERSION = "132"
LAUNCHER_FILE = STATIC_DIR / "owner-print-center-launcher.js"
PAGE_FILE = STATIC_DIR / "owner-print-center.html"
LAUNCHER_URL = f"/owner-print-center-launcher.js?v={VERSION}"

if LAUNCHER_URL not in native_owner.OPTIONAL_JS_URLS:
    native_owner.OPTIONAL_JS_URLS.append(LAUNCHER_URL)
if LAUNCHER_FILE not in final_owner.JS_FILES:
    final_owner.JS_FILES.append(LAUNCHER_FILE)

native_owner.BUILD = VERSION
final_owner.BUILD = VERSION
stable_owner.VERSION = VERSION


_previous_stable_owner_page = stable_owner.stable_owner_page


def stable_owner_page_with_print_center(token: str) -> HTMLResponse:
    original = _previous_stable_owner_page(token)
    page = original.body.decode("utf-8")
    if LAUNCHER_URL not in page:
        page = page.replace("</body>", f'<script src="{LAUNCHER_URL}"></script></body>', 1)
    headers = {
        key: value
        for key, value in original.headers.items()
        if key.lower() not in {"content-length", "content-type", "set-cookie"}
    }
    response = HTMLResponse(page, status_code=original.status_code, headers=headers)
    cookie = original.headers.get("set-cookie")
    if cookie:
        response.headers.append("set-cookie", cookie)
    return response


stable_owner.stable_owner_page = stable_owner_page_with_print_center


_UNION_SQL = """
SELECT id, ref, title, entry_date, amount, due, kind, status, created_at
FROM (
    SELECT id, invoice_no AS ref,
           COALESCE(NULLIF(party_name,''),'Cash / Walk-in Customer') AS title,
           invoice_date AS entry_date, total AS amount, due,
           'sale' AS kind,
           CASE WHEN due>0 THEN 'unpaid' ELSE 'completed' END AS status,
           created_at, business_id
    FROM sales
    UNION ALL
    SELECT id, invoice_no AS ref,
           COALESCE(NULLIF(party_name,''),'Cash Purchase') AS title,
           invoice_date AS entry_date, total AS amount, due,
           'purchase' AS kind,
           CASE WHEN due>0 THEN 'unpaid' ELSE 'completed' END AS status,
           created_at, business_id
    FROM purchases
    UNION ALL
    SELECT id, title AS ref,
           COALESCE(NULLIF(party_name,''),title) AS title,
           entry_date, amount, 0 AS due, entry_type AS kind,
           status, created_at, business_id
    FROM business_entries
    UNION ALL
    SELECT id, doc_no AS ref,
           COALESCE(NULLIF(party_name,''),kind) AS title,
           doc_date AS entry_date, amount, 0 AS due, kind,
           status, created_at, business_id
    FROM documents
    UNION ALL
    SELECT id, return_no AS ref,
           COALESCE(NULLIF(party_name,''),'Return') AS title,
           return_date AS entry_date, total AS amount, due, kind,
           'completed' AS status, created_at, business_id
    FROM returns
) transaction_rows
WHERE business_id=?
"""


def _filtered_sql(
    business_id: int,
    date_from: str,
    date_to: str,
    kind: str,
    search: str,
) -> tuple[str, list[Any]]:
    sql = _UNION_SQL
    params: list[Any] = [business_id]
    if date_from:
        sql += " AND entry_date>=?"
        params.append(date_from[:10])
    if date_to:
        sql += " AND entry_date<=?"
        params.append(date_to[:10])
    if kind and kind != "all":
        sql += " AND kind=?"
        params.append(kind)
    if search:
        sql += " AND (LOWER(COALESCE(title,'')) LIKE ? OR LOWER(COALESCE(ref,'')) LIKE ? OR LOWER(COALESCE(kind,'')) LIKE ?)"
        pattern = f"%{search.lower()}%"
        params.extend([pattern, pattern, pattern])
    return sql, params


@app.get("/api/print-center-transactions")
def print_center_transactions(
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    kind: str = Query(default="all"),
    search: str = Query(default=""),
    sort: str = Query(default="newest"),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=500000),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    base_sql, params = _filtered_sql(
        int(user["business_id"]),
        str(date_from or "").strip(),
        str(date_to or "").strip(),
        str(kind or "all").strip().lower(),
        str(search or "").strip()[:120],
    )
    order_by = {
        "oldest": "entry_date ASC, created_at ASC, id ASC",
        "amount_high": "amount DESC, entry_date DESC, id DESC",
        "amount_low": "amount ASC, entry_date DESC, id DESC",
    }.get(str(sort or "").strip().lower(), "entry_date DESC, created_at DESC, id DESC")

    with db() as conn:
        total_row = conn.execute(
            f"SELECT COUNT(*) AS count FROM ({base_sql}) filtered_rows",
            params,
        ).fetchone()
        rows = conn.execute(
            f"{base_sql} ORDER BY {order_by} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return {
        "rows": [dict(row) for row in rows],
        "total": int(total_row["count"] if total_row else 0),
        "offset": offset,
        "limit": limit,
    }


def _owner_session(request: Request):
    return _session_row(request.cookies.get(COOKIE_NAME))


def _business_name(session: Any) -> str:
    with db() as conn:
        row = conn.execute(
            "SELECT name FROM businesses WHERE id=?",
            (int(session["business_id"]),),
        ).fetchone()
    return str(row["name"] if row and row["name"] else "Kirana Software")


@app.get("/owner/print-center", response_class=HTMLResponse)
def owner_print_center(request: Request):
    session = _owner_session(request)
    if not session:
        return RedirectResponse("/owner-login", status_code=303)
    page = PAGE_FILE.read_text(encoding="utf-8").replace(
        "__BUSINESS__",
        html.escape(_business_name(session)),
    )
    return HTMLResponse(
        page,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Kirana-Print-Center": VERSION,
        },
    )


@app.get("/owner/print-center/print", response_class=HTMLResponse)
def owner_print_center_print(
    request: Request,
    items: str = Query(default=""),
    autoprint: bool = Query(default=False),
):
    session = _owner_session(request)
    if not session:
        return RedirectResponse("/owner-login", status_code=303)

    selections: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for raw in str(items or "").split(","):
        if ":" not in raw:
            continue
        kind_text, id_text = raw.split(":", 1)
        try:
            kind = print_ext._clean_kind(kind_text)
            transaction_id = int(id_text)
        except Exception:
            continue
        key = (kind, transaction_id)
        if transaction_id > 0 and key not in seen:
            seen.add(key)
            selections.append(key)
        if len(selections) >= 100:
            break

    if not selections:
        return HTMLResponse("Select at least one transaction to print", status_code=400)

    blocks: list[str] = []
    with db() as conn:
        for kind, transaction_id in selections:
            try:
                detail = print_ext._load_detail(
                    conn,
                    int(session["business_id"]),
                    kind,
                    transaction_id,
                )
            except Exception:
                continue
            blocks.append(print_ext._transaction_block(detail))

    if not blocks:
        return HTMLResponse("Selected transaction details were not found", status_code=404)

    return HTMLResponse(
        print_ext._page_html(
            f"Print {len(blocks)} Transaction{'s' if len(blocks) != 1 else ''}",
            "".join(blocks),
            auto_print=autoprint,
            back_href="/owner/print-center",
        ),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "X-Kirana-Print-Center": VERSION,
        },
    )


@app.middleware("http")
async def serve_print_center_launcher(request: Request, call_next):
    if request.method == "GET" and request.url.path.rstrip("/") == "/owner-print-center-launcher.js":
        return Response(
            LAUNCHER_FILE.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "X-Kirana-Print-Center": VERSION,
            },
        )
    return await call_next(request)


_ROUTE_PATHS = {
    "/api/print-center-transactions",
    "/owner/print-center",
    "/owner/print-center/print",
}
_routes = [
    route
    for route in list(app.router.routes)
    if getattr(route, "path", None) in _ROUTE_PATHS
]
for route in _routes:
    app.router.routes.remove(route)
_fallback_index = next(
    (
        index
        for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _routes
