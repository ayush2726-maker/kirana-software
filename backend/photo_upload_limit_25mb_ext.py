from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

import backend.photo_bill_barcode_ext as legacy_photo
import backend.handwritten_bill_ai_ext as handwriting_ai
from backend.app import app


VERSION = "139"
MAX_IMAGE_BYTES = 25 * 1024 * 1024

# Keep both the original OCR reader and the AI handwriting reader on the same
# upload limit. The AI middleware normally handles /api/photo-bill/ocr first,
# but setting both prevents an older/fallback route from silently retaining 12 MB.
legacy_photo.MAX_IMAGE_BYTES = MAX_IMAGE_BYTES
handwriting_ai.MAX_IMAGE_BYTES = MAX_IMAGE_BYTES


@app.middleware("http")
async def photo_bill_25mb_guard(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if request.method == "POST" and path == "/api/photo-bill/ocr":
        length = request.headers.get("content-length")
        if length:
            try:
                # Multipart adds a small envelope around the image, so allow
                # 512 KB overhead while still enforcing a 25 MB image limit in
                # the actual reader below.
                if int(length) > MAX_IMAGE_BYTES + (512 * 1024):
                    return JSONResponse(
                        {"detail": "Bill photo is too large (max 25 MB)", "version": VERSION},
                        status_code=413,
                        headers={"Cache-Control": "no-store"},
                    )
            except (TypeError, ValueError):
                pass
    return await call_next(request)
