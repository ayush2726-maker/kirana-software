from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse

from backend.app import app, db
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.quick_write_bill_ext as quick
import backend.handwritten_bill_ai_ext as handwriting

VERSION = "152"
ALIASES = {
    "kabli": "kabuli", "kabali": "kabuli", "kabalee": "kabuli",
    "desi": "desi chana", "shakkar": "shakar", "sakkar": "shakar",
}


def _norm(v: Any) -> str:
    x = quick._norm(v)
    return ALIASES.get(x, x)


def _size_key(v: Any) -> str:
    s = str(v or "").lower().replace(" ", "")
    s = s.replace("grams", "g").replace("gram", "g").replace("gms", "g").replace("gm", "g")
    s = s.replace("kgs", "kg").replace("kilo", "kg").replace("litre", "l").replace("ltr", "l")
    return s.replace("1000g", "1kg")


def _parts(line: str):
    name, size, qty = quick._line_parts(line)
    if not size:
        m = re.match(r"^(.*?)[\s]+(\d+(?:\.\d+)?)$", str(line or "").strip())
        if m and m.group(1).strip():
            name, qty = m.group(1).strip(), max(0.001, quick._number(m.group(2), 1.0))
    return name, size, qty


def _best(name: str, size: str, items: list[dict[str, Any]]):
    q = _norm(name)
    qtok = set(q.split())
    wanted = _size_key(size)
    best = None
    best_score = 0.0
    for item in items:
        c = _norm(item.get("name"))
        if not c:
            continue
        ctok = set(c.split())
        score = 0.0
        if q == c:
            score = 1.0
        elif q in c or c in q:
            score = 0.90
        if qtok and ctok:
            score = max(score, len(qtok & ctok) / max(1, len(qtok)) * 0.92)
        score = max(score, quick.difflib.SequenceMatcher(None, q, c).ratio() * 0.82)
        actual = _size_key(item.get("size") or item.get("unit"))
        if wanted and actual:
            score += 0.24 if wanted == actual else -0.16
        if score > best_score:
            best, best_score = item, score
    return (best, min(best_score, 1.0)) if best is not None and best_score >= 0.60 else (None, best_score)


def _last_rate(conn: Any, business_id: int, item_id: int, bill_type: str) -> float:
    if bill_type == "purchase":
        row = conn.execute(
            "SELECT pi.rate FROM purchase_items pi JOIN purchases p ON p.id=pi.purchase_id "
            "WHERE p.business_id=? AND pi.item_id=? AND pi.rate>0 ORDER BY p.invoice_date DESC, p.id DESC, pi.id DESC LIMIT 1",
            (business_id, item_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT si.rate FROM sale_items si JOIN sales s ON s.id=si.sale_id "
            "WHERE s.business_id=? AND si.item_id=? AND si.rate>0 ORDER BY s.invoice_date DESC, s.id DESC, si.id DESC LIMIT 1",
            (business_id, item_id),
        ).fetchone()
    return quick._number(row["rate"]) if row else 0.0


def _effective_rate(conn: Any, business_id: int, item: dict[str, Any], bill_type: str) -> float:
    field = "purchase_price" if bill_type == "purchase" else "sale_price"
    rate = quick._number(item.get(field))
    if rate > 0:
        return rate
    return _last_rate(conn, business_id, int(item["id"]), bill_type)


def _parse_text(text: str, items: list[dict[str, Any]], bill_type: str, conn: Any, business_id: int):
    out = []
    for raw in re.split(r"[\r\n]+", str(text or "")):
        raw = raw.strip()
        if not raw:
            continue
        name, size, qty = _parts(raw)
        item, score = _best(name, size, items)
        if item:
            rate = _effective_rate(conn, business_id, item, bill_type)
            out.append({
                "source_text": raw,
                "item_id": int(item["id"]),
                "item_name": str(item.get("name") or name),
                "size": str(item.get("size") or size),
                "qty": round(qty, 3),
                "rate": round(rate, 2),
                "gst_rate": round(quick._number(item.get("gst_rate")), 2),
                "match_confidence": round(score, 3),
            })
        else:
            out.append({
                "source_text": raw, "item_id": None, "item_name": name, "size": size,
                "qty": round(qty, 3), "rate": 0, "gst_rate": 0,
                "match_confidence": round(score, 3),
            })
    return out


def _json_from_model(text: str) -> dict[str, Any]:
    clean = str(text or "").strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.I)
    clean = re.sub(r"\s*```$", "", clean)
    a, b = clean.find("{"), clean.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("AI response did not contain JSON")
    return json.loads(clean[a:b+1])


def _gemini_canvas_extract(raw: bytes) -> list[dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    model = str(getattr(handwriting, "GEMINI_MODEL", "") or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")).strip()
    if model.startswith("models/"):
        model = model.split("/", 1)[1]
    prompt = """Read this handwritten kirana Quick Write canvas. Return ONLY JSON.
Each handwritten line is usually: ITEM NAME then optional QUANTITY and/or SIZE.
Critical rules:
- A BARE number with no unit means QUANTITY. Example: 'काबली 2' => item_name='काबली', qty=2, size=''.
- A number with kg/g/gm/l/ltr/ml/pcs/packet is SIZE. Example: 'काबली 2kg' => qty=1, size='2kg'.
- If both are present, keep both separately. Example: 'काबली 2 1kg' => qty=2, size='1kg'.
- Never convert a bare 1,2,3,4... into kg/g/size.
- Do not invent rate, amount or size.
- Preserve Hindi/English item words as read.
Schema: {"rows":[{"item_name":"","qty":1,"size":"","confidence":0.0}]}
"""
    payload = {
        "contents": [{"role": "user", "parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(raw).decode("ascii")}},
        ]}],
        "generationConfig": {"temperature": 0.0},
    }
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = _json_from_model(text)
        return [r for r in list(parsed.get("rows") or []) if isinstance(r, dict)][:40]
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"Gemini HTTP {exc.code}: {detail}") from exc


def _rows_from_ai(ai_rows: list[dict[str, Any]], items: list[dict[str, Any]], bill_type: str, conn: Any, bid: int):
    out = []
    for raw in ai_rows:
        name = str(raw.get("item_name") or "").strip()
        if len(_norm(name)) < 2:
            continue
        size = str(raw.get("size") or "").strip()
        qty = quick._number(raw.get("qty"), 1.0)
        if qty <= 0 or qty > 999:
            qty = 1.0
        if re.fullmatch(r"\d+(?:\.\d+)?", size):
            qty = quick._number(size, qty)
            size = ""
        item, score = _best(name, size, items)
        if item:
            rate = _effective_rate(conn, bid, item, bill_type)
            out.append({
                "source_text": name,
                "item_id": int(item["id"]),
                "item_name": str(item.get("name") or name),
                "size": str(item.get("size") or size),
                "qty": round(qty, 3),
                "rate": round(rate, 2),
                "gst_rate": round(quick._number(item.get("gst_rate")), 2),
                "match_confidence": round(max(score, quick._number(raw.get("confidence"))), 3),
            })
        else:
            out.append({"source_text": name, "item_id": None, "item_name": name, "size": size, "qty": round(qty,3), "rate": 0, "gst_rate": 0, "match_confidence": round(quick._number(raw.get("confidence")),3)})
    return out


HTML = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>Quick Write Bill</title><style>
*{box-sizing:border-box}body{margin:0;background:#eef8fe;color:#263545;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial}.head{position:sticky;top:0;z-index:9;background:#fff;border-bottom:1px solid #d5e2e9;padding:12px 14px;display:flex;gap:12px;align-items:center}.back{width:44px;height:44px;border:0;border-radius:50%;background:#eaf5fb;color:#0873a7;font-size:25px}.head small{font-weight:900;letter-spacing:1.2px;color:#0873a7}.head h1{margin:2px 0 0;font-size:23px}.wrap{max-width:980px;margin:auto;padding:14px 12px 55px}.card{background:#fff;border:1px solid #d5e2e9;border-radius:18px;padding:15px;margin-bottom:12px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}label{display:grid;gap:6px;font-size:13px;font-weight:850;color:#53616d}select,input{font:inherit;width:100%;border:2px solid #d5e2e9;border-radius:12px;padding:10px;background:#fff;color:#263545}.canvas-wrap{border:2px solid #d5e2e9;border-radius:14px;overflow:hidden;background:#fff;margin-top:10px}.canvas-tools{display:flex;gap:8px;flex-wrap:wrap;padding:8px;background:#f4f8fa;border-bottom:1px solid #dce6eb}.btn{border:0;border-radius:12px;min-height:46px;padding:10px 16px;font-weight:900;background:#0b82c2;color:#fff}.secondary{background:#fff;color:#0873a7;border:2px solid #b8d6e6}canvas{display:block;width:100%;height:560px;touch-action:none;background:#fff}.status{display:none;margin-top:10px;padding:10px 12px;border-radius:10px;background:#eef7fb;font-weight:750}.status.show{display:block}.status.err{background:#fff0ef;color:#b42318}.table{overflow:auto;border:1px solid #d5e2e9;border-radius:12px;margin-top:12px}table{width:100%;min-width:760px;border-collapse:collapse}th,td{padding:7px;border-bottom:1px solid #e2eaee;text-align:left}th{background:#f1f6f9;font-size:12px}td input{min-height:38px;padding:6px;border-width:1px}.ok{color:#138a52;font-size:11px;font-weight:900}.low{color:#a16a00}.total{text-align:right;font-size:20px;font-weight:900;margin-top:10px}.actions{display:flex;gap:9px;flex-wrap:wrap;margin-top:12px}.hint{font-size:12px;color:#70808d;margin:8px 2px 0}@media(max-width:700px){.grid{grid-template-columns:1fr}.actions .btn{flex:1}canvas{height:590px}}
</style></head><body><header class="head"><button class="back" id="back">‹</button><div><small>SMART BILLING</small><h1>✍️ Quick Write Bill</h1></div></header><main class="wrap"><section class="card"><div class="grid"><label>Bill Type<select id="type"><option value="sale">Sale</option><option value="purchase">Purchase</option></select></label><label>Party<select id="party"><option value="">Cash / No party</option></select></label></div><div class="canvas-wrap"><div class="canvas-tools"><button class="btn secondary" id="undo">Undo</button><button class="btn secondary" id="clear">Clear Page</button></div><canvas id="pad"></canvas></div><div class="actions"><button class="btn" id="make">Read & Make Draft</button><button class="btn secondary" id="more">＋ Add More Items</button></div><div class="hint">Bare number = Qty (e.g. काबली 2). Unit ke saath number = Size (e.g. काबली 2kg).</div><div id="status" class="status"></div></section><section class="card" id="draft" style="display:none"><div class="table"><table><thead><tr><th>#</th><th>Item</th><th>Size</th><th>Qty</th><th>Rate</th><th>Amount</th></tr></thead><tbody id="rows"></tbody></table></div><div class="total" id="total">₹0.00</div><div class="actions"><button class="btn" id="save">Save Bill</button></div></section></main><script>
(function(){'use strict';var lines=[],items=[],parties=[],strokes=[],drawing=false,current=[];function q(x){return document.getElementById(x)}function n(v){var x=Number(v||0);return isFinite(x)?x:0}function money(v){return '₹'+n(v).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})}async function api(p,o){o=o||{};var h=Object.assign({Accept:'application/json'},o.headers||{}),b=o.body;if(b&&typeof b!=='string'){h['Content-Type']='application/json';b=JSON.stringify(b)}var r=await fetch(p,Object.assign({},o,{body:b,headers:h,credentials:'include',cache:'no-store'}));var d=await r.json().catch(function(){return{}});if(!r.ok)throw new Error(d.detail||('Request failed '+r.status));return d}function show(m,e){q('status').textContent=m;q('status').className='status show'+(e?' err':'')}function label(i){return String(i.name||'')+(i.size?' | '+i.size:'')}function totals(){var t=0;document.querySelectorAll('#rows tr').forEach(function(tr){var qty=n(tr.querySelector('[data-f=qty]').value),rate=n(tr.querySelector('[data-f=rate]').value);tr.querySelector('.amt').textContent=money(qty*rate);t+=qty*rate});q('total').textContent=money(t)}function render(){q('rows').innerHTML=lines.map(function(x,i){var c=Math.round(n(x.match_confidence)*100),tag=x.item_id?(c>=75?'Matched '+c+'%':'Check '+c+'%'):'Select item';return '<tr data-i="'+i+'"><td>'+(i+1)+'</td><td><input data-f="item" list="all-items" value="'+String(x.item_name||'').replace(/"/g,'&quot;')+'"><div class="'+(c>=75?'ok':'ok low')+'">'+tag+'</div></td><td><input data-f="size" value="'+String(x.size||'').replace(/"/g,'&quot;')+'"></td><td><input data-f="qty" type="number" step="0.001" value="'+n(x.qty)+'"></td><td><input data-f="rate" type="number" step="0.01" value="'+n(x.rate)+'"></td><td><b class="amt">'+money(n(x.qty)*n(x.rate))+'</b></td></tr>'}).join('');q('draft').style.display='block';totals()}function fillParties(){var want=q('type').value==='purchase'?'supplier':'customer';q('party').innerHTML='<option value="">Cash / No party</option>'+parties.filter(function(p){return p.type===want||p.type==='both'}).map(function(p){return '<option value="'+p.id+'">'+p.name+'</option>'}).join('')}async function load(){var a=await Promise.all([api('/api/items?limit=2000'),api('/api/parties')]);items=a[0]||[];parties=a[1]||[];var dl=document.createElement('datalist');dl.id='all-items';dl.innerHTML=items.map(function(i){return '<option value="'+label(i).replace(/"/g,'&quot;')+'"></option>'}).join('');document.body.appendChild(dl);fillParties()}var c=q('pad'),ctx=c.getContext('2d');function resize(){var r=c.getBoundingClientRect(),d=Math.min(devicePixelRatio||1,1.5);c.width=Math.round(r.width*d);c.height=Math.round(r.height*d);ctx.setTransform(d,0,0,d,0,0);redraw()}function redraw(){ctx.clearRect(0,0,c.width,c.height);ctx.lineCap='round';ctx.lineJoin='round';ctx.lineWidth=3;ctx.strokeStyle='#1f2d3d';strokes.forEach(function(s){if(!s.length)return;ctx.beginPath();ctx.moveTo(s[0].x,s[0].y);s.slice(1).forEach(function(p){ctx.lineTo(p.x,p.y)});ctx.stroke()})}function pos(e){var r=c.getBoundingClientRect();return{x:e.clientX-r.left,y:e.clientY-r.top}}function start(e){e.preventDefault();drawing=true;current=[pos(e)];strokes.push(current);c.setPointerCapture&&c.setPointerCapture(e.pointerId)}function move(e){if(!drawing)return;e.preventDefault();current.push(pos(e));redraw()}function end(){drawing=false;current=[]}c.addEventListener('pointerdown',start);c.addEventListener('pointermove',move);c.addEventListener('pointerup',end);c.addEventListener('pointercancel',end);q('undo').onclick=function(){strokes.pop();redraw()};function clearPad(){strokes=[];redraw()}q('clear').onclick=clearPad;async function readPad(append){try{if(!strokes.length)throw new Error('Pehle pencil se item likho');show(append?'Naye items read ho rahe hain…':'Handwriting read ho rahi hai…');var jpg=c.toDataURL('image/jpeg',0.72);var d=await api('/api/quick-bill/handwriting',{method:'POST',body:{image:jpg,bill_type:q('type').value}});var got=d.items||[];lines=append?lines.concat(got):got;render();clearPad();show(got.length+' naye item ready. Total '+lines.length+' item draft me.')}catch(e){show(e.message,true)}}q('make').onclick=function(){readPad(false)};q('more').onclick=function(){readPad(true)};q('rows').addEventListener('input',function(e){var tr=e.target.closest('tr');if(!tr)return;var i=Number(tr.dataset.i),x=lines[i],f=e.target.dataset.f;if(!x||!f)return;if(f==='qty'||f==='rate'){x[f]=n(e.target.value);totals();return}if(f==='size'){x.size=e.target.value;return}if(f==='item'){x.item_name=e.target.value;var v=e.target.value.trim().toLowerCase(),m=items.find(function(z){return label(z).toLowerCase()===v})||items.find(function(z){return String(z.name||'').toLowerCase()===v});if(m){x.item_id=Number(m.id);x.item_name=m.name;x.size=m.size||'';x.rate=n(q('type').value==='purchase'?m.purchase_price:m.sale_price);x.gst_rate=n(m.gst_rate);tr.querySelector('[data-f=size]').value=x.size;tr.querySelector('[data-f=rate]').value=x.rate;totals()}else{x.item_id=null}}});q('save').onclick=async function(){try{var clean=lines.filter(function(x){return String(x.item_name||'').trim()&&n(x.qty)>0});if(clean.some(function(x){return !x.item_id}))throw new Error('Unmatched item pehle select karo');var payload={party_id:q('party').value?Number(q('party').value):null,invoice_date:new Date().toISOString().slice(0,10),discount:0,paid:0,payment_mode:'credit',notes:'Created from pencil Quick Write',items:clean.map(function(x){return{item_id:Number(x.item_id),item_name:x.item_name,size:x.size||'',qty:n(x.qty),rate:n(x.rate),gst_rate:n(x.gst_rate)}})};var type=q('type').value,s=await api(type==='purchase'?'/api/purchases':'/api/sales',{method:'POST',body:payload});show((type==='purchase'?'Purchase':'Sale')+' saved: '+String(s.invoice_no||''));q('save').textContent='Saved ✓'}catch(e){show(e.message,true)}};q('type').onchange=fillParties;q('back').onclick=function(){location.assign('/?page=menu&stable=100')};window.addEventListener('resize',resize);resize();load().catch(function(e){show(e.message,true)})})();
</script></body></html>'''


@app.middleware("http")
async def quick_canvas_fix(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if path == "/owner/quick-bill" and request.method == "GET":
        s = _session_row(request.cookies.get(COOKIE_NAME))
        if not s:
            return await call_next(request)
        return HTMLResponse(HTML, headers={"Cache-Control": "no-store", "X-Kirana-Quick": VERSION})

    if path == "/api/quick-bill/parse" and request.method == "POST":
        s = _session_row(request.cookies.get(COOKIE_NAME))
        if not s:
            return JSONResponse({"detail": "Session expired"}, status_code=401)
        data = await request.json()
        bill_type = str(data.get("bill_type") or "sale").lower()
        text = str(data.get("text") or "")
        bid = int(s["business_id"])
        with db() as conn:
            items = [dict(r) for r in conn.execute("SELECT * FROM items WHERE business_id=? ORDER BY name,size,id", (bid,)).fetchall()]
            rows = _parse_text(text, items, bill_type, conn, bid)
        return JSONResponse({"items": rows, "detected_lines": len(rows), "version": VERSION})

    if path == "/api/quick-bill/handwriting" and request.method == "POST":
        s = _session_row(request.cookies.get(COOKIE_NAME))
        if not s:
            return JSONResponse({"detail": "Session expired"}, status_code=401)
        data = await request.json()
        bill_type = str(data.get("bill_type") or "sale").lower()
        image = str(data.get("image") or "")
        if "," not in image:
            return JSONResponse({"detail": "Handwriting image missing"}, status_code=400)
        try:
            raw = base64.b64decode(image.split(",", 1)[1])
        except Exception:
            return JSONResponse({"detail": "Handwriting image invalid"}, status_code=400)
        bid = int(s["business_id"])
        try:
            ai_rows = _gemini_canvas_extract(raw)
            with db() as conn:
                items = [dict(r) for r in conn.execute("SELECT * FROM items WHERE business_id=? ORDER BY name,size,id", (bid,)).fetchall()]
                rows = _rows_from_ai(ai_rows, items, bill_type, conn, bid)
            return JSONResponse({"items": rows, "detected_lines": len(rows), "version": VERSION, "reader": "gemini-quickwrite+local-catalog"})
        except Exception as e:
            return JSONResponse({"detail": "Handwriting read nahi hui: " + str(e)[:220]}, status_code=422)

    return await call_next(request)