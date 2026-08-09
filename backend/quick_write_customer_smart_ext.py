from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.app import app, db
from backend.owner_session_ext import COOKIE_NAME, _session_row

VERSION = "170"


@app.post('/api/quick-bill/customer-smart')
async def quick_bill_customer_smart(request: Request):
    session = _session_row(request.cookies.get(COOKIE_NAME))
    if not session:
        return JSONResponse({'detail': 'Session expired'}, status_code=401)
    try:
        data = await request.json()
    except Exception:
        data = {}
    name = str(data.get('name') or '').strip()
    phone = ''.join(ch for ch in str(data.get('phone') or '') if ch.isdigit())[-10:]
    if len(name) < 2:
        return JSONResponse({'detail': 'Customer name chahiye'}, status_code=400)
    if phone and len(phone) != 10:
        return JSONResponse({'detail': '10 digit mobile number dalo'}, status_code=400)
    bid = int(session['business_id'])
    with db() as conn:
        if phone:
            existing = conn.execute(
                "SELECT * FROM parties WHERE business_id=? AND type IN ('customer','both') AND REPLACE(REPLACE(REPLACE(COALESCE(phone,''),' ',''),'-',''),'+91','') LIKE ? LIMIT 1",
                (bid, '%' + phone),
            ).fetchone()
            if existing:
                return JSONResponse({'ok': True, 'party': dict(existing), 'created': False, 'matched_by': 'phone'})
        cur = conn.execute(
            "INSERT INTO parties(business_id,name,type,phone,gstin,address,opening_balance,balance,created_at,updated_at) VALUES(?,?, 'customer', ?, '', '', 0, 0, datetime('now'), datetime('now'))",
            (bid, name, phone),
        )
        row = conn.execute('SELECT * FROM parties WHERE id=?', (int(cur.lastrowid),)).fetchone()
    return JSONResponse({'ok': True, 'party': dict(row), 'created': True})

# Keep API ahead of frontend catch-all.
matches = [r for r in list(app.router.routes) if getattr(r, 'path', None) == '/api/quick-bill/customer-smart']
for route in matches:
    app.router.routes.remove(route)
idx = next((i for i, route in enumerate(app.router.routes) if getattr(route, 'path', None) == '/{path:path}'), len(app.router.routes))
app.router.routes[idx:idx] = matches
