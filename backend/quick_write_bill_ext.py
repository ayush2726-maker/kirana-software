from __future__ import annotations

import difflib
import html
import re
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.app import app, db
from backend.owner_session_ext import COOKIE_NAME, _session_row

VERSION = "149"

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
SIZE_RE = re.compile(r"(?<!\w)(\d+(?:\.\d+)?)\s*(kg|kgs|kilo|kilogram|g|gm|gms|gram|grams|ml|l|ltr|litre|liter|pc|pcs|pkt|pack)(?!\w)", re.I)
QTY_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:x|×)\s*", re.I)

VOWELS = {"अ":"a","आ":"aa","इ":"i","ई":"ee","उ":"u","ऊ":"oo","ए":"e","ऐ":"ai","ओ":"o","औ":"au","ऋ":"ri"}
MATRAS = {"ा":"aa","ि":"i","ी":"ee","ु":"u","ू":"oo","े":"e","ै":"ai","ो":"o","ौ":"au","ृ":"ri","ं":"n","ँ":"n","ः":"h","्":""}
CONS = {
    "क":"k","ख":"kh","ग":"g","घ":"gh","ङ":"n","च":"ch","छ":"chh","ज":"j","झ":"jh","ञ":"n",
    "ट":"t","ठ":"th","ड":"d","ढ":"dh","ण":"n","त":"t","थ":"th","द":"d","ध":"dh","न":"n",
    "प":"p","फ":"ph","ब":"b","भ":"bh","म":"m","य":"y","र":"r","ल":"l","व":"v","श":"sh","ष":"sh","स":"s","ह":"h",
}


def _transliterate(text: str) -> str:
    out: list[str] = []
    chars = list(str(text or ""))
    i = 0
    while i < len(chars):
        ch = chars[i]
        if ch in VOWELS:
            out.append(VOWELS[ch])
        elif ch in CONS:
            base = CONS[ch]
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            if nxt in MATRAS:
                out.append(base + MATRAS[nxt])
                i += 1
            elif nxt == "्":
                out.append(base)
                i += 1
            else:
                out.append(base + "a")
        elif ch in MATRAS:
            out.append(MATRAS[ch])
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _norm(value: Any) -> str:
    text = str(value or "").translate(DEVANAGARI_DIGITS).lower().strip()
    text = _transliterate(text)
    text = text.replace("shakkar", "shakar").replace("sakkar", "shakar")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _size(value: str) -> str:
    match = SIZE_RE.search(str(value or "").translate(DEVANAGARI_DIGITS))
    if not match:
        return ""
    number = match.group(1)
    unit = match.group(2).lower()
    unit = {"kgs":"kg","kilo":"kg","kilogram":"kg","gm":"g","gms":"g","gram":"g","grams":"g","ltr":"L","litre":"L","liter":"L","pcs":"pc"}.get(unit, unit)
    if number.endswith(".0"):
        number = number[:-2]
    return f"{number}{unit}"


def _size_key(value: Any) -> str:
    return _norm(str(value or "")).replace(" ", "")


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value or "").replace(",", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        return default


def _line_parts(line: str) -> tuple[str, str, float]:
    raw = str(line or "").translate(DEVANAGARI_DIGITS).strip()
    qty = 1.0
    qmatch = QTY_RE.match(raw)
    if qmatch:
        qty = max(0.001, min(100.0, _number(qmatch.group(1), 1.0)))
        raw = raw[qmatch.end():].strip()
    size = _size(raw)
    without_size = SIZE_RE.sub(" ", raw, count=1)
    without_size = re.sub(r"\s*[@=]\s*₹?\s*[0-9][0-9,.]*\s*$", " ", without_size)
    name = re.sub(r"\s+", " ", without_size).strip(" -,:;/")
    return name, size, qty


def _score_item(name: str, size: str, item: dict[str, Any]) -> float:
    query = _norm(name)
    candidate = _norm(item.get("name"))
    if not query or not candidate:
        return 0.0
    score = difflib.SequenceMatcher(None, query, candidate).ratio()
    if query in candidate or candidate in query:
        score = max(score, 0.86)
    qwords, cwords = set(query.split()), set(candidate.split())
    if qwords and cwords:
        overlap = len(qwords & cwords) / max(1, len(qwords | cwords))
        score = max(score, overlap)
    if size:
        wanted = _size_key(size)
        actual = _size_key(item.get("size") or item.get("unit"))
        if wanted and actual:
            if wanted == actual:
                score += 0.18
            else:
                score -= 0.20
    return max(0.0, min(1.0, score))


def _best_item(name: str, size: str, items: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    ranked = sorted(((_score_item(name, size, item), item) for item in items), key=lambda pair: pair[0], reverse=True)
    if not ranked:
        return None, 0.0
    score, item = ranked[0]
    return (item, score) if score >= 0.48 else (None, score)


def _parse_note(text: str, items: list[dict[str, Any]], bill_type: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_line in re.split(r"[\r\n]+", str(text or "")):
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        name, size, qty = _line_parts(raw_line)
        if len(_norm(name)) < 2:
            continue
        matched, score = _best_item(name, size, items)
        if matched:
            rate_field = "purchase_price" if bill_type == "purchase" else "sale_price"
            rate = _number(matched.get(rate_field))
            rows.append({
                "source_text": raw_line,
                "item_id": int(matched["id"]),
                "item_name": str(matched.get("name") or name),
                "size": str(matched.get("size") or size),
                "qty": round(qty, 3),
                "rate": round(rate, 2),
                "gst_rate": round(_number(matched.get("gst_rate")), 2),
                "match_confidence": round(score, 3),
            })
        else:
            rows.append({
                "source_text": raw_line,
                "item_id": None,
                "item_name": name,
                "size": size,
                "qty": round(qty, 3),
                "rate": 0,
                "gst_rate": 0,
                "match_confidence": round(score, 3),
            })
    return rows


@app.post("/api/quick-bill/parse")
async def parse_quick_bill(request: Request):
    session = _session_row(request.cookies.get(COOKIE_NAME))
    if not session:
        return JSONResponse({"detail": "Session expired"}, status_code=401)
    try:
        data = await request.json()
    except Exception:
        data = {}
    bill_type = str(data.get("bill_type") or "sale").strip().lower()
    if bill_type not in {"sale", "purchase"}:
        bill_type = "sale"
    text = str(data.get("text") or "")[:12000]
    if not text.strip():
        return JSONResponse({"detail": "Item note likhein, jaise: काबली 1kg"}, status_code=400)
    with db() as conn:
        items = [dict(row) for row in conn.execute(
            "SELECT * FROM items WHERE business_id=? ORDER BY name,size,id",
            (int(session["business_id"]),),
        ).fetchall()]
    rows = _parse_note(text, items, bill_type)
    if not rows:
        return JSONResponse({"detail": "Note se koi item line nahi mili"}, status_code=422)
    return JSONResponse({"items": rows, "detected_lines": len(rows), "version": VERSION}, headers={"Cache-Control": "no-store"})


QUICK_HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#087fbf"><title>Quick Write Bill</title><style>
*{box-sizing:border-box}body{margin:0;background:#eef8fe;color:#263545;font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}.head{position:sticky;top:0;z-index:9;background:#fff;border-bottom:1px solid #d5e2e9;padding:12px 14px;display:flex;gap:12px;align-items:center}.back{width:44px;height:44px;border:0;border-radius:50%;background:#eaf5fb;color:#0873a7;font-size:25px}.head small{font-weight:900;letter-spacing:1.2px;color:#0873a7}.head h1{margin:2px 0 0;font-size:23px}.wrap{max-width:1000px;margin:auto;padding:14px 12px 50px}.card{background:#fff;border:1px solid #d5e2e9;border-radius:18px;padding:15px;margin-bottom:12px;box-shadow:0 7px 22px rgba(32,77,104,.06)}.hero{background:linear-gradient(145deg,#087fbf,#0da1d2);color:#fff}.hero h2{margin:4px 0 6px}.hero p{margin:0;line-height:1.45}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}label{display:grid;gap:6px;font-size:13px;font-weight:850;color:#53616d}select,textarea,input{font:inherit;width:100%;border:2px solid #d5e2e9;border-radius:12px;padding:10px;background:#fff;color:#263545}textarea{min-height:170px;font-size:19px;line-height:1.6}.btn{border:0;border-radius:12px;min-height:48px;padding:10px 16px;font-weight:900;background:#0b82c2;color:#fff}.secondary{background:#fff;color:#0873a7;border:2px solid #b8d6e6}.actions{display:flex;gap:9px;flex-wrap:wrap;margin-top:12px}.status{display:none;margin-top:10px;padding:10px 12px;border-radius:10px;background:#eef7fb;font-weight:750}.status.show{display:block}.status.err{background:#fff0ef;color:#b42318}.table{overflow:auto;border:1px solid #d5e2e9;border-radius:12px;margin-top:12px}table{width:100%;min-width:760px;border-collapse:collapse}th,td{padding:7px;border-bottom:1px solid #e2eaee;text-align:left}th{background:#f1f6f9;font-size:12px}td input{min-height:38px;padding:6px;border-width:1px}.ok{color:#138a52;font-size:11px;font-weight:900}.low{color:#a16a00}.total{text-align:right;font-size:20px;font-weight:900;margin-top:10px}@media(max-width:700px){.grid{grid-template-columns:1fr}.actions .btn{flex:1}.wrap{padding-left:10px;padding-right:10px}}
</style></head><body><header class="head"><button class="back" id="back">‹</button><div><small>SMART BILLING</small><h1>✍️ Quick Write Bill</h1></div></header><main class="wrap"><section class="card hero"><h2>Jaise note me likhte ho, waise type karo</h2><p>Hindi / English / Hinglish chalega. Har item nayi line me: <b>काबली 1kg</b>, <b>शक्कर 500g</b>, <b>2x मैदा 1kg</b>. App catalog se item + size match karke saved rate laga dega.</p></section><section class="card"><div class="grid"><label>Bill Type<select id="type"><option value="sale">Sale</option><option value="purchase">Purchase</option></select></label><label>Party<select id="party"><option value="">Cash / No party</option></select></label></div><label style="margin-top:10px">Quick Note<textarea id="note" placeholder="काबली 1kg&#10;शक्कर 500g&#10;2x मैदा 1kg"></textarea></label><div class="actions"><button class="btn" id="make">Make Bill Draft</button><button class="btn secondary" id="clear">Clear</button></div><div id="status" class="status"></div></section><section class="card" id="draft" style="display:none"><div class="table"><table><thead><tr><th>#</th><th>Item</th><th>Size</th><th>Qty</th><th>Rate</th><th>Amount</th></tr></thead><tbody id="rows"></tbody></table></div><div class="total" id="total">₹0.00</div><div class="actions"><button class="btn" id="save">Save Bill</button></div></section></main><script>
(function(){'use strict';var lines=[],items=[],parties=[];function q(x){return document.getElementById(x)}function n(v){var x=Number(v||0);return isFinite(x)?x:0}function money(v){return '₹'+n(v).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})}async function api(p,o){o=o||{};var h=Object.assign({Accept:'application/json'},o.headers||{}),b=o.body;if(b&&typeof b!=='string'){h['Content-Type']='application/json';b=JSON.stringify(b)}var r=await fetch(p,Object.assign({},o,{body:b,headers:h,credentials:'include',cache:'no-store'}));var d=await r.json().catch(function(){return{}});if(!r.ok)throw new Error(d.detail||('Request failed '+r.status));return d}function itemLabel(i){return String(i.name||'')+(i.size?' | '+i.size:'')}function render(){q('rows').innerHTML=lines.map(function(x,i){var conf=Math.round(n(x.match_confidence)*100),label=x.item_id?(conf>=75?'Matched '+conf+'%':'Check '+conf+'%'):'Select item';return '<tr data-i="'+i+'"><td>'+(i+1)+'</td><td><input data-f="item" list="all-items" value="'+String(x.item_name||'').replace(/"/g,'&quot;')+'"><div class="'+(conf>=75?'ok':'ok low')+'">'+label+'</div></td><td><input data-f="size" value="'+String(x.size||'').replace(/"/g,'&quot;')+'"></td><td><input data-f="qty" type="number" step="0.001" value="'+n(x.qty)+'"></td><td><input data-f="rate" type="number" step="0.01" value="'+n(x.rate)+'"></td><td><b>'+money(n(x.qty)*n(x.rate))+'</b></td></tr>'}).join('');var t=lines.reduce(function(s,x){return s+n(x.qty)*n(x.rate)},0);q('total').textContent=money(t);q('draft').style.display='block'}async function load(){try{var a=await Promise.all([api('/api/items?limit=2000'),api('/api/parties')]);items=a[0]||[];parties=a[1]||[];var dl=document.createElement('datalist');dl.id='all-items';dl.innerHTML=items.map(function(i){return '<option value="'+itemLabel(i).replace(/"/g,'&quot;')+'"></option>'}).join('');document.body.appendChild(dl);fillParties()}catch(e){show(e.message,true)}}function fillParties(){var want=q('type').value==='purchase'?'supplier':'customer';q('party').innerHTML='<option value="">Cash / No party</option>'+parties.filter(function(p){return p.type===want||p.type==='both'}).map(function(p){return '<option value="'+p.id+'">'+p.name+'</option>'}).join('')}function show(m,e){q('status').textContent=m;q('status').className='status show'+(e?' err':'')}q('make').onclick=async function(){try{show('Note samajh raha hai…');var d=await api('/api/quick-bill/parse',{method:'POST',body:{text:q('note').value,bill_type:q('type').value}});lines=d.items||[];render();show(lines.length+' item line ready. Save se pehle check/edit kar lo.')}catch(e){show(e.message,true)}};q('rows').addEventListener('input',function(e){var tr=e.target.closest('tr');if(!tr)return;var i=Number(tr.dataset.i),x=lines[i],f=e.target.dataset.f;if(!x||!f)return;if(f==='qty'||f==='rate')x[f]=n(e.target.value);else if(f==='size')x.size=e.target.value;else if(f==='item'){var v=e.target.value.trim().toLowerCase();var m=items.find(function(z){return itemLabel(z).toLowerCase()===v})||items.find(function(z){return String(z.name||'').toLowerCase()===v});if(m){x.item_id=Number(m.id);x.item_name=m.name;x.size=m.size||'';x.rate=n(q('type').value==='purchase'?m.purchase_price:m.sale_price);x.gst_rate=n(m.gst_rate);x.match_confidence=1}else{x.item_id=null;x.item_name=e.target.value}}render()});q('save').onclick=async function(){try{var clean=lines.filter(function(x){return String(x.item_name||'').trim()&&n(x.qty)>0});if(!clean.length)throw new Error('Valid item chahiye');var bad=clean.filter(function(x){return !x.item_id});if(bad.length)throw new Error(bad.length+' item catalog se match nahi hua; pehle item select karo');var payload={party_id:q('party').value?Number(q('party').value):null,invoice_date:new Date().toISOString().slice(0,10),discount:0,paid:0,payment_mode:'credit',notes:'Created from Quick Write',items:clean.map(function(x){return{item_id:Number(x.item_id),item_name:x.item_name,size:x.size||'',qty:n(x.qty),rate:n(x.rate),gst_rate:n(x.gst_rate)}})};var type=q('type').value;var s=await api(type==='purchase'?'/api/purchases':'/api/sales',{method:'POST',body:payload});show((type==='purchase'?'Purchase':'Sale')+' bill saved: '+String(s.invoice_no||''));q('save').textContent='Saved ✓'}catch(e){show(e.message,true)}};q('clear').onclick=function(){q('note').value='';lines=[];q('draft').style.display='none';q('status').className='status'};q('type').onchange=fillParties;q('back').onclick=function(){location.assign('/?page=menu&mobile=1&quickReturn=1')};load()})();
</script></body></html>'''


@app.get("/owner/quick-bill", response_class=HTMLResponse)
def quick_bill_page(request: Request):
    session = _session_row(request.cookies.get(COOKIE_NAME))
    if not session:
        return RedirectResponse("/owner-login", status_code=303)
    return HTMLResponse(
        QUICK_HTML,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Kirana-Build": VERSION,
        },
    )


# Critical: backend.app has a catch-all /{path:path} frontend route. Extensions
# imported later must move their explicit routes in front of that catch-all,
# otherwise /owner/quick-bill is swallowed and the old frontend "My Business"
# menu appears instead. The user video showed exactly that route fall-through.
for wanted_path in ("/owner/quick-bill", "/api/quick-bill/parse"):
    matches = [route for route in list(app.router.routes) if getattr(route, "path", None) == wanted_path]
    for route in matches:
        app.router.routes.remove(route)
    fallback_index = next(
        (index for index, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
        len(app.router.routes),
    )
    app.router.routes[fallback_index:fallback_index] = matches
