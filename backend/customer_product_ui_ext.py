from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse

from backend.app import app


@app.middleware("http")
async def force_latest_customer_product_assets(request: Request, call_next):
    response = await call_next(request)
    if request.method != "GET" or request.url.path.rstrip("/") != "/customer":
        return response
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        return response
    body = b""
    async for chunk in response.body_iterator:
        body += chunk
    html = body.decode("utf-8")
    html = html.replace("/customer-order.js?v=060", "/customer-order.js?v=063")
    html = html.replace("/customer-order.css?v=060", "/customer-order.css?v=063")
    headers = dict(response.headers)
    headers.pop("content-length", None)
    headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    headers["Pragma"] = "no-cache"
    return HTMLResponse(html, status_code=response.status_code, headers=headers)
