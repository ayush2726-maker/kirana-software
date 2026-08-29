from __future__ import annotations

from fastapi.responses import HTMLResponse

import backend.ai_counter_ext  # noqa: F401
import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner
from backend.app import app


AI_DESK_GET_PATHS = {"/owner/ai-desk", "/api/ai-counter/bootstrap"}
VERSION = "176"


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


DESK_PATCH = r'''
<style id="kirana-ai-desk-menu-style-176">
.kirana-ai-desk-row{display:grid!important;grid-template-columns:44px minmax(0,1fr) 20px!important;align-items:center!important;width:100%!important;min-height:72px!important;padding:11px 12px!important;border:0!important;border-radius:13px!important;background:#fff!important;color:#172033!important;gap:11px!important;text-align:left!important;font:inherit!important}
.kirana-ai-desk-row .ks-icon{display:grid!important;place-items:center!important;width:42px!important;height:42px!important;border-radius:13px!important;background:#eef8fe!important;font-size:20px!important}.kirana-ai-desk-row .ks-copy{display:grid!important;min-width:0!important;gap:2px!important}.kirana-ai-desk-row b{font-size:14px!important}.kirana-ai-desk-row small{font-size:10px!important;color:#667085!important}.kirana-ai-desk-row .ks-next{font-size:20px!important;color:#98a2b3!important}
</style>
<script id="kirana-ai-desk-menu-script-176">
(function(){
 'use strict';
 if(window.__kiranaAiDeskMenu176)return;window.__kiranaAiDeskMenu176=true;
 var launching=false;
 function container(){var direct=document.querySelector('#page-menu .menu-list');if(direct)return direct;var page=document.querySelector('#page-menu');if(page){var rows=page.querySelectorAll('.card,.menu-list,[class*=menu]');if(rows.length)return rows[rows.length-1];return page}return null}
 function cleanup(){
   var all=document.querySelectorAll('[data-kirana-ai-desk]');for(var i=1;i<all.length;i++)all[i].remove();
 }
 function launch(btn,e){
   if(e){e.preventDefault();e.stopPropagation();if(e.stopImmediatePropagation)e.stopImmediatePropagation()}
   if(launching)return;launching=true;if(btn){btn.disabled=true;btn.style.opacity='.7'}
   fetch('/api/ai-counter/kiosk-token',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(function(r){return r.json().then(function(d){if(!r.ok)throw new Error(d.detail||'AI Desk open nahi hua');return d})})
    .then(function(d){if(!d.url)throw new Error('AI Desk URL missing');window.location.assign(d.url)})
    .catch(function(err){launching=false;if(btn){btn.disabled=false;btn.style.opacity=''}window.alert(err.message||'AI Desk open nahi hua')});
 }
 function install(){cleanup();var c=container();if(!c||c.querySelector('[data-kirana-ai-desk]'))return;var b=document.createElement('button');b.type='button';b.className='kirana-ai-desk-row';b.setAttribute('data-kirana-ai-desk','1');b.innerHTML='<span class="ks-icon">🤖</span><span class="ks-copy"><b>AI Billing Desk</b><small>Customer button dabaye aur voice se bill banaye</small></span><span class="ks-next">›</span>';c.appendChild(b)}
 function eventHandler(e){var b=e.target&&e.target.closest?e.target.closest('[data-kirana-ai-desk]'):null;if(b)launch(b,e)}
 document.addEventListener('pointerdown',eventHandler,true);
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
 [80,250,600,1200,2500,5000].forEach(function(ms){setTimeout(install,ms)});
 if(window.MutationObserver)new MutationObserver(function(){setTimeout(install,0)}).observe(document.documentElement,{childList:true,subtree:true});
})();
</script>
'''


def _inject(page: str) -> str:
    if "kirana-ai-desk-menu-script-176" in page:
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
_move_ai_desk_get_routes_before_spa_fallback()
