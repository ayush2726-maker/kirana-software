from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from backend.app import STATIC_DIR, app
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.photo_bill_barcode_ext as smart


VERSION = "136"
RUNTIME_FILE = STATIC_DIR / "owner-smart-tools-runtime.js"
RUNTIME_PATH = "/owner-smart-tools-runtime.js"


def _no_cache() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }


@app.middleware("http")
async def serve_smart_tools_runtime_fix(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"

    if request.method == "GET" and path == RUNTIME_PATH:
        return Response(
            RUNTIME_FILE.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={**_no_cache(), "X-Kirana-Smart-Runtime": VERSION},
        )

    if request.method == "GET" and path == "/owner/smart-tools":
        session = _session_row(request.cookies.get(COOKIE_NAME))
        if not session:
            return RedirectResponse("/owner-login", status_code=303)

        page = smart.SMART_PAGE.read_text(encoding="utf-8")
        runtime_tag = f'<script src="{RUNTIME_PATH}?v={VERSION}"></script>'
        if runtime_tag not in page:
            page = page.replace("</body>", runtime_tag + "</body>", 1)

        return HTMLResponse(
            page,
            headers={
                **_no_cache(),
                "X-Kirana-Smart-Tools": VERSION,
                "Clear-Site-Data": '"cache"',
            },
        )

    return await call_next(request)
