from __future__ import annotations

from fastapi import Request
from fastapi.responses import Response

from backend.app import STATIC_DIR, app


BROKEN_LINE = "if(metaEl)metaEl.textContent=`${line.size?`${line.size} · `:''}${line.unit||'pcs'} · GST ${line.gst_rate}%`}updateCartTotals(k)}"
FIXED_LINE = "if(metaEl)metaEl.textContent=`${line.size?`${line.size} · `:''}${line.unit||'pcs'} · GST ${line.gst_rate}%`;updateCartTotals(k)}}"


def corrected_owner_core() -> str:
    core = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    if BROKEN_LINE not in core:
        return core
    return core.replace(BROKEN_LINE, FIXED_LINE, 1)


def no_cache_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }


@app.middleware("http")
async def serve_correct_owner_core(request: Request, call_next):
    if request.method == "GET" and request.url.path.rstrip("/") == "/owner-core.js":
        return Response(
            corrected_owner_core(),
            media_type="application/javascript",
            headers=no_cache_headers(),
        )
    return await call_next(request)
