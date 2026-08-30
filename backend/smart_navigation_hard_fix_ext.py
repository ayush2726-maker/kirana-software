from __future__ import annotations

from fastapi.responses import HTMLResponse

import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner


VERSION = "205"
native_owner.BUILD = VERSION
final_owner.BUILD = VERSION
stable_owner.VERSION = VERSION

SMART_PATCH = r'''
<style id="kirana-smart-hard-style">
#kirana-smart-fixed{display:none!important}
#kirana-smart-fixed a{width:44px;height:44px;border-radius:50%;display:grid;place-items:center;text-decoration:none;background:#eef8fe;border:1px solid #d5e2e9;box-shadow:0 4px 14px rgba(26,74,104,.16);font-size:21px;color:#17354b}
#kirana-smart-fixed a[data-kirana-quick-direct]{background:#fff7d8}
.kirana-smart-menu-row{display:grid!important;grid-template-columns:44px minmax(0,1fr) 20px!important;align-items:center!important;width:100%!important;min-height:72px!important;padding:11px 12px!important;border:0!important;border-radius:13px!important;background:#fff!important;text-decoration:none!important;color:#172033!important;gap:11px!important;text-align:left!important;position:relative!important;z-index:1!important}
.kirana-smart-menu-row:hover{background:#f7f9fd!important}
.kirana-smart-menu-row .ks-icon{display:grid!important;place-items:center!important;width:42px!important;height:42px!important;border-radius:13px!important;background:#eff6ff!important;color:#2563eb!important;font-size:20px!important;min-width:0!important;text-align:center!important}
.kirana-smart-menu-row .ks-copy{display:grid!important;min-width:0!important;gap:2px!important}
.kirana-smart-menu-row b{overflow:hidden!important;font-size:14px!important;line-height:1.3!important;text-overflow:ellipsis!important;white-space:nowrap!important}
.kirana-smart-menu-row small{overflow:hidden!important;font-size:10px!important;line-height:1.3!important;color:#667085!important;text-overflow:ellipsis!important;white-space:nowrap!important}
.kirana-smart-menu-row .ks-next{font-size:20px!important;color:#98a2b3!important}
</style>
<script id="kirana-smart-hard-nav">
(function(){
  'use strict';
  if(window.__kiranaSmartHard205)return;
  window.__kiranaSmartHard205=true;

  var routes={
    quick:'/owner/quick-bill?direct=205',
    photo:'/owner/smart-tools?direct=205#photo',
    barcode:'/owner/smart-tools?direct=205#barcode'
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
    a.addEventListener('click',function(event){
      event.preventDefault();
      event.stopPropagation();
      go(kind);
    });
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
    return null;
  }

  function menu(){
    var container=bestMenuContainer();
    if(!container)return;
    function ensureOne(kind,selector,icon,title,sub){
      var matches=container.querySelectorAll(selector);
      for(var i=1;i<matches.length;i++)matches[i].remove();
      if(!matches.length)container.appendChild(row(kind,icon,title,sub));
    }
    ensureOne('photo','[data-smart-photo],[data-kirana-photo-direct]','📷','Photo to Bill','Bill photo se editable Sale/Purchase draft');
    ensureOne('quick','[data-smart-quick],[data-kirana-quick-direct]','✍️','Quick Write Bill','Hindi/English note se item + size + saved rate');
    ensureOne('barcode','[data-smart-barcode],[data-kirana-barcode-direct]','▥','Barcode Generator','Item barcode generate aur labels print');
  }

  function install(){ fixed(); menu(); }

  // IMPORTANT: do not capture pointerdown/touchstart globally. On Android the
  // Menu tab can reveal content underneath the same finger and a global early
  // handler may turn that gesture into a Smart Tools navigation. Only the
  // actual injected row's click handler is allowed to open Smart Tools.
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

def native_owner_html_177() -> str:
    return _inject(_prev_native_html())

native_owner.native_owner_html = native_owner_html_177


_prev_final_html = final_owner.final_owner_html

def final_owner_html_177() -> str:
    return _inject(_prev_final_html())

final_owner.final_owner_html = final_owner_html_177


_prev_stable_page = stable_owner.stable_owner_page

def stable_owner_page_177(token: str) -> HTMLResponse:
    original = _prev_stable_page(token)
    page = _inject(original.body.decode("utf-8"))
    headers = {k: v for k, v in original.headers.items() if k.lower() not in {"content-length", "content-type", "set-cookie"}}
    response = HTMLResponse(page, status_code=original.status_code, headers=headers)
    cookie = original.headers.get("set-cookie")
    if cookie:
        response.headers.append("set-cookie", cookie)
    response.headers["X-Kirana-Smart-Hard-Fix"] = VERSION
    return response

stable_owner.stable_owner_page = stable_owner_page_177
