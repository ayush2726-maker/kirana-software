from __future__ import annotations

from fastapi.responses import HTMLResponse

import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner


VERSION = "148"

SMART_PATCH = r'''
<style id="kirana-smart-hard-style">
#kirana-smart-fixed{position:fixed;right:14px;top:72px;z-index:2147483000;display:flex;gap:7px;pointer-events:auto}
#kirana-smart-fixed a{width:44px;height:44px;border-radius:50%;display:grid;place-items:center;text-decoration:none;background:#eef8fe;border:1px solid #d5e2e9;box-shadow:0 4px 14px rgba(26,74,104,.16);font-size:21px;color:#17354b}
#kirana-smart-fixed a[data-kirana-quick-direct]{background:#fff7d8}
.kirana-smart-menu-row{display:flex!important;align-items:center!important;width:100%!important;min-height:74px!important;padding:14px 12px!important;border:0!important;border-bottom:1px solid #e3e8eb!important;background:#fff!important;text-decoration:none!important;color:#263545!important;gap:14px!important;text-align:left!important}
.kirana-smart-menu-row .ks-icon{font-size:28px;min-width:42px;text-align:center}
.kirana-smart-menu-row .ks-copy{display:flex;flex-direction:column;min-width:0;flex:1}
.kirana-smart-menu-row b{font-size:17px;line-height:1.25}
.kirana-smart-menu-row small{font-size:13px;line-height:1.25;color:#7b8791;margin-top:3px}
.kirana-smart-menu-row .ks-next{font-size:28px;color:#0784bd}
@media(max-width:700px){#kirana-smart-fixed{top:70px;right:12px}}
</style>
<script id="kirana-smart-hard-nav">
(function(){
  'use strict';
  if(window.__kiranaSmartHard148)return;
  window.__kiranaSmartHard148=true;

  var routes={
    quick:'/owner/quick-bill?direct=148',
    photo:'/owner/smart-tools?direct=148#photo',
    barcode:'/owner/smart-tools?direct=148#barcode'
  };

  function go(kind){
    var url=routes[kind];
    if(!url)return;
    try{ window.location.assign(url); }catch(e){ window.location.href=url; }
  }

  function fixed(){
    var old=document.getElementById('kirana-smart-fixed');
    if(old)return;
    var box=document.createElement('nav');
    box.id='kirana-smart-fixed';
    box.setAttribute('aria-label','Smart Billing');
    box.innerHTML='<a href="'+routes.photo+'" data-kirana-photo-direct title="Photo to Bill">📷</a>'+
      '<a href="'+routes.quick+'" data-kirana-quick-direct title="Quick Write Bill">✍️</a>'+
      '<a href="'+routes.barcode+'" data-kirana-barcode-direct title="Barcode Generator">▥</a>';
    document.body.appendChild(box);
  }

  function row(kind,icon,title,sub){
    var a=document.createElement('a');
    a.href=routes[kind];
    a.className='kirana-smart-menu-row';
    a.setAttribute('data-kirana-'+kind+'-direct','1');
    a.innerHTML='<span class="ks-icon">'+icon+'</span><span class="ks-copy"><b>'+title+'</b><small>'+sub+'</small></span><span class="ks-next">›</span>';
    return a;
  }

  function bestMenuContainer(){
    var direct=document.querySelector('#page-menu .menu-list');
    if(direct)return direct;
    var page=document.querySelector('#page-menu');
    if(page){
      var cards=page.querySelectorAll('.card,.menu-list,[class*=menu]');
      if(cards.length)return cards[cards.length-1];
      return page;
    }
    var candidates=Array.prototype.slice.call(document.querySelectorAll('.menu-list,.settings-list,.list-card,.card'));
    for(var i=0;i<candidates.length;i++){
      var t=(candidates[i].innerText||'').toLowerCase();
      if(t.indexOf('settings')>=0 && (t.indexOf('sale')>=0 || t.indexOf('import')>=0 || t.indexOf('business')>=0))return candidates[i];
    }
    return null;
  }

  function menu(){
    var container=bestMenuContainer();
    if(!container)return;
    if(!container.querySelector('[data-kirana-photo-direct]')) container.appendChild(row('photo','📷','Photo to Bill','Bill photo se editable Sale/Purchase draft'));
    if(!container.querySelector('[data-kirana-quick-direct]')) container.appendChild(row('quick','✍️','Quick Write Bill','Hindi/English note se item + size + saved rate'));
    if(!container.querySelector('[data-kirana-barcode-direct]')) container.appendChild(row('barcode','▥','Barcode Generator','Item barcode generate aur labels print'));
  }

  function install(){ fixed(); menu(); }

  function directEvent(event){
    var node=event.target&&event.target.closest?event.target.closest('[data-kirana-quick-direct],[data-kirana-photo-direct],[data-kirana-barcode-direct]'):null;
    if(!node)return;
    var kind=node.hasAttribute('data-kirana-quick-direct')?'quick':node.hasAttribute('data-kirana-photo-direct')?'photo':'barcode';
    event.preventDefault();
    event.stopPropagation();
    if(event.stopImmediatePropagation)event.stopImmediatePropagation();
    go(kind);
  }

  // pointerdown/touchstart fires before the old owner menu can rerender or steal the click.
  document.addEventListener('pointerdown',directEvent,true);
  document.addEventListener('touchstart',directEvent,true);
  document.addEventListener('click',directEvent,true);

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true}); else install();
  [50,150,350,700,1200,2200,4000,7000].forEach(function(ms){setTimeout(install,ms)});
  if(window.MutationObserver){
    var queued=false;
    new MutationObserver(function(){
      if(queued)return; queued=true;
      requestAnimationFrame(function(){queued=false;install()});
    }).observe(document.documentElement,{childList:true,subtree:true});
  }
})();
</script>
'''


def _inject(page: str) -> str:
    if "kirana-smart-hard-nav" in page:
        return page
    return page.replace("</body>", SMART_PATCH + "</body>", 1)


_prev_native_html = native_owner.native_owner_html

def native_owner_html_148() -> str:
    return _inject(_prev_native_html())

native_owner.native_owner_html = native_owner_html_148


_prev_final_html = final_owner.final_owner_html

def final_owner_html_148() -> str:
    return _inject(_prev_final_html())

final_owner.final_owner_html = final_owner_html_148


_prev_stable_page = stable_owner.stable_owner_page

def stable_owner_page_148(token: str) -> HTMLResponse:
    original = _prev_stable_page(token)
    page = _inject(original.body.decode("utf-8"))
    headers = {k: v for k, v in original.headers.items() if k.lower() not in {"content-length", "content-type", "set-cookie"}}
    response = HTMLResponse(page, status_code=original.status_code, headers=headers)
    cookie = original.headers.get("set-cookie")
    if cookie:
        response.headers.append("set-cookie", cookie)
    response.headers["X-Kirana-Smart-Hard-Fix"] = VERSION
    return response

stable_owner.stable_owner_page = stable_owner_page_148
