from __future__ import annotations

import re

from fastapi import HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

import backend.ai_counter_ext as ai_counter
import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner
from backend.app import app, db, today_iso


AI_DESK_GET_PATHS = {"/owner/ai-desk", "/api/ai-counter/bootstrap"}
VERSION = "205"


def _move_ai_desk_get_routes_before_spa_fallback() -> None:
    routes = list(app.router.routes)
    selected = [route for route in routes if getattr(route, "path", None) in AI_DESK_GET_PATHS]
    if not selected:
        return
    for route in selected:
        try:
            app.router.routes.remove(route)
        except ValueError:
            pass
    fallback_index = next((i for i, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"), len(app.router.routes))
    for offset, route in enumerate(selected):
        app.router.routes.insert(fallback_index + offset, route)


# Android / Google speech commonly returns grocery words as ordinary words.
# Correct only high-confidence grocery confusions, then remove quantity/unit noise
# before fuzzy matching so unrelated catalog rows cannot win on strings like
# "1 kilo shop" or "aadha kilo desi channel".
_prev_norm = ai_counter._norm
_prev_score = ai_counter._score

_SPEECH_FIXES = {
    "channel": "chana",
    "चैनल": "chana",
    "chenal": "chana",
    "chanel": "chana",
    "shop": "saunf",
    "शॉप": "saunf",
    "soap": "saunf",
    "सोप": "saunf",
    "sauf": "saunf",
    "souf": "saunf",
    "saumph": "saunf",
}

_QTY_NOISE = {
    "kg", "kilogram", "kilo", "g", "gram", "grams", "gm", "ltr", "liter", "litre",
    "packet", "pack", "pcs", "piece", "pieces", "bottle", "box",
}


def _speech_norm(value):
    text = str(value or "")
    for src, dst in _SPEECH_FIXES.items():
        text = re.sub(rf"(?<!\w){re.escape(src)}(?!\w)", dst, text, flags=re.I)
    return _prev_norm(text)


def _match_text(value):
    text = _speech_norm(value)
    words = []
    for word in text.split():
        if word in _QTY_NOISE:
            continue
        if word in ai_counter.NUMBER_WORDS:
            continue
        try:
            float(word)
            continue
        except ValueError:
            pass
        words.append(word)
    return " ".join(words).strip()


def _speech_score(text, candidate):
    a = _match_text(text)
    b = _match_text(candidate)
    if not a or not b:
        return 0.0
    # Exact normalized item phrase is safest and should beat generic fuzzy rows.
    if a == b:
        return 1.0
    if b in a or a in b:
        return 0.98
    return _prev_score(a, b)


ai_counter._norm = _speech_norm
ai_counter._score = _speech_score


DESK_PATCH = r'''
<style id="kirana-ai-desk-menu-style-205">
.kirana-ai-desk-row{display:grid!important;grid-template-columns:44px minmax(0,1fr) 20px!important;align-items:center!important;width:100%!important;min-height:72px!important;padding:11px 12px!important;border:0!important;border-radius:13px!important;background:#fff!important;color:#172033!important;gap:11px!important;text-align:left!important;font:inherit!important}
.kirana-ai-desk-row .ks-icon{display:grid!important;place-items:center!important;width:42px!important;height:42px!important;border-radius:13px!important;background:#eef8fe!important;font-size:20px!important}.kirana-ai-desk-row .ks-copy{display:grid!important;min-width:0!important;gap:2px!important}.kirana-ai-desk-row b{font-size:14px!important}.kirana-ai-desk-row small{font-size:10px!important;color:#667085!important}.kirana-ai-desk-row .ks-next{font-size:20px!important;color:#98a2b3!important}
</style>
<script id="kirana-ai-desk-menu-script-205">
(function(){
 'use strict';
 if(window.__kiranaAiDeskMenu205)return;window.__kiranaAiDeskMenu205=true;
 var launching=false;
 function container(){var direct=document.querySelector('#page-menu .menu-list');if(direct)return direct;var page=document.querySelector('#page-menu');if(page){var rows=page.querySelectorAll('.card,.menu-list,[class*=menu]');if(rows.length)return rows[rows.length-1];return page}return null}
 function cleanup(c){if(!c)return null;var all=c.querySelectorAll('[data-smart-desk],[data-kirana-ai-desk]');for(var i=1;i<all.length;i++)all[i].remove();return all.length?all[0]:null}
 function launch(btn,e){if(e){e.preventDefault();e.stopPropagation();if(e.stopImmediatePropagation)e.stopImmediatePropagation()}if(launching)return;launching=true;if(btn){btn.disabled=true;btn.style.opacity='.7'}fetch('/api/ai-counter/kiosk-token',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:'{}'}).then(function(r){return r.json().then(function(d){if(!r.ok)throw new Error(d.detail||'AI Desk open nahi hua');return d})}).then(function(d){if(!d.url)throw new Error('AI Desk URL missing');window.location.assign(d.url)}).catch(function(err){launching=false;if(btn){btn.disabled=false;btn.style.opacity=''}window.alert(err.message||'AI Desk open nahi hua')})}
 function install(){var c=container();if(!c||cleanup(c))return;var b=document.createElement('button');b.type='button';b.className='kirana-ai-desk-row';b.setAttribute('data-kirana-ai-desk','1');b.innerHTML='<span class="ks-icon">🤖</span><span class="ks-copy"><b>AI Billing Desk</b><small>Customer button dabaye aur voice se bill banaye</small></span><span class="ks-next">›</span>';c.appendChild(b)}
 function eventHandler(e){var b=e.target&&e.target.closest?e.target.closest('[data-kirana-ai-desk]'):null;if(b)launch(b,e)}
 document.addEventListener('pointerdown',eventHandler,true);
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
 [80,250,600,1200,2500,5000].forEach(function(ms){setTimeout(install,ms)});
 if(window.MutationObserver)new MutationObserver(function(){setTimeout(install,0)}).observe(document.documentElement,{childList:true,subtree:true});
})();
</script>
'''


def _inject(page: str) -> str:
    if "kirana-ai-desk-menu-script-205" in page:
        return page
    return page.replace("</body>", DESK_PATCH + "</body>", 1)


_prev_native_html = native_owner.native_owner_html
def native_owner_html_ai_desk() -> str:
    return _inject(_prev_native_html())
native_owner.native_owner_html = native_owner_html_ai_desk

_prev_final_html = final_owner.final_owner_html
def final_owner_html_ai_desk() -> str:
    return _inject(_prev_final_html())
final_owner.final_owner_html = final_owner_html_ai_desk

_prev_stable_page = stable_owner.stable_owner_page
def stable_owner_page_ai_desk(token: str) -> HTMLResponse:
    original = _prev_stable_page(token)
    page = _inject(original.body.decode("utf-8"))
    headers = {k: v for k, v in original.headers.items() if k.lower() not in {"content-length", "content-type", "set-cookie"}}
    response = HTMLResponse(page, status_code=original.status_code, headers=headers)
    cookie = original.headers.get("set-cookie")
    if cookie: response.headers.append("set-cookie", cookie)
    response.headers["X-Kirana-AI-Desk-UI"] = VERSION
    return response
stable_owner.stable_owner_page = stable_owner_page_ai_desk


QUANTITY_JS = r'''
function parseQtyOnly(raw){
 var t=String(raw||'').trim().toLowerCase();
 var dev='०१२३४५६७८९';t=t.replace(/[०-९]/g,function(c){return String(dev.indexOf(c))});
 t=t.replace(/किलोग्राम|किलो|kgs?|kilograms?|kilos?/g,' kg ')
    .replace(/ग्राम|grams?|gms?/g,' g ')
    .replace(/लीटर|लिटर|litres?|liters?|ltr/g,' ltr ')
    .replace(/पैकेट|packets?|pkt/g,' packet ')
    .replace(/पीस|pieces?|pcs?/g,' pcs ')
    .replace(/आधा|aadha|adha|half/g,' 0.5 ')
    .replace(/पाव|paav|pav|quarter/g,' 0.25 ')
    .replace(/डेढ़|डेढ|dedh|derh/g,' 1.5 ')
    .replace(/एक|ek|one/g,' 1 ').replace(/दो|do|two/g,' 2 ').replace(/तीन|teen|three/g,' 3 ')
    .replace(/चार|chaar|char|four/g,' 4 ').replace(/पांच|पाँच|paanch|panch|five/g,' 5 ');
 t=t.replace(/\s+/g,' ').trim();
 if(!/^\d+(?:\.\d+)?\s*(?:kg|g|ltr|packet|pcs)?$/.test(t))return null;
 var m=t.match(/^(\d+(?:\.\d+)?)\s*(kg|g|ltr|packet|pcs)?$/);if(!m)return null;
 var q=Number(m[1]),unit=m[2]||'';if(!(q>0))return null;
 if(unit==='g'){q=q/1000;unit='kg'}
 return {qty:q,unit:unit};
}
'''


def _desk_page_with_quantity_fix() -> str:
    page = ai_counter.KIOSK_PAGE.read_text(encoding="utf-8")
    if "function parseQtyOnly(raw)" not in page:
        page = page.replace("async function handle(text){", QUANTITY_JS + "\nasync function handle(text){", 1)
    old = "clearFail();text=String(text||'').trim();if(!text)return;$('heard').textContent='You: '+text;"
    new = old + "\n var qonly=(S.stage==='items'&&S.cart.length)?parseQtyOnly(text):null;if(qonly){var last=S.cart[S.cart.length-1];last.qty=qonly.qty;last.spokenUnit=qonly.unit||last.spokenUnit||'';$('choices').innerHTML='';render();say(last.item.name+' ki quantity '+Number(qonly.qty).toFixed(3).replace(/\\.?0+$/,'')+(qonly.unit?' '+qonly.unit:'')+' kar di. Aur kuch?');return;}"
    page = page.replace(old, new, 1)
    page = page.replace("escapeHtml(x.item.size||x.item.unit||'')", "escapeHtml(x.spokenUnit||x.item.size||x.item.unit||'')", 1)
    return page


# Replace only the AI desk page route so quantity-only speech is handled before item search.
for route in list(app.router.routes):
    if getattr(route, "path", None) == "/owner/ai-desk" and "GET" in (getattr(route, "methods", set()) or set()):
        app.router.routes.remove(route)


@app.get("/owner/ai-desk", response_class=HTMLResponse)
def ai_counter_page_quantity_fixed(token: str = Query(default="")):
    if not ai_counter.KIOSK_PAGE.exists():
        raise HTTPException(status_code=404, detail="AI Desk page missing")
    if token:
        with db() as conn:
            row = conn.execute(
                "SELECT id FROM ai_counter_tokens WHERE token_hash=? AND active=1 AND expires_on>=?",
                (ai_counter._token_hash(token), today_iso()),
            ).fetchone()
        if not row:
            return RedirectResponse("/owner-login", status_code=303)
    return HTMLResponse(
        _desk_page_with_quantity_fix(),
        headers={"Cache-Control":"no-store, no-cache, must-revalidate, max-age=0","X-Kirana-AI-Desk":VERSION},
    )


_move_ai_desk_get_routes_before_spa_fallback()
