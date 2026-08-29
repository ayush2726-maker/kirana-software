from __future__ import annotations

import backend.ai_counter_route_order_ext as desk

VERSION = "199"
_prev_page = desk._desk_page_with_quantity_fix

_OLD = "async function api(path,opt){var r=await fetch(path,Object.assign({credentials:'omit',headers:headers()},opt||{}));var d=await r.json().catch(()=>({detail:'Request failed'}));if(!r.ok)throw new Error(d.detail||'Request failed');return d}"

_NEW = r'''async function api(path,opt){
 var lastErr=null;
 for(var attempt=0;attempt<3;attempt++){
  try{
   var cfg=Object.assign({credentials:'omit',headers:headers(),cache:'no-store'},opt||{});
   var r=await fetch(path,cfg);
   var d=await r.json().catch(()=>({detail:'Request failed'}));
   if(!r.ok)throw new Error(d.detail||('Request failed ('+r.status+')'));
   return d;
  }catch(e){
   lastErr=e;
   var msg=String((e&&e.message)||'');
   var network=/failed to fetch|networkerror|load failed|network request failed/i.test(msg);
   if(!network || attempt===2)break;
   await new Promise(function(resolve){setTimeout(resolve,500*(attempt+1));});
  }
 }
 var raw=String((lastErr&&lastErr.message)||'Request failed');
 if(/failed to fetch|networkerror|load failed|network request failed/i.test(raw)){
  throw new Error('Server connection nahi mili. Internet check karke dobara boliye.');
 }
 throw lastErr||new Error('Request failed');
}'''


def _page() -> str:
    page = _prev_page()
    if "Server connection nahi mili" not in page and _OLD in page:
        page = page.replace(_OLD, _NEW, 1)
    return page


desk._desk_page_with_quantity_fix = _page
