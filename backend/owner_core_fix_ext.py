from __future__ import annotations

import re

from fastapi import Request
from fastapi.responses import Response

from backend.app import STATIC_DIR, app


BROKEN_LINE = "if(metaEl)metaEl.textContent=`${line.size?`${line.size} · `:''}${line.unit||'pcs'} · GST ${line.gst_rate}%`}updateCartTotals(k)}"
FIXED_LINE = "if(metaEl)metaEl.textContent=`${line.size?`${line.size} · `:''}${line.unit||'pcs'} · GST ${line.gst_rate}%`;updateCartTotals(k)}}"

BOOT_START = "async function boot(){paintIcons();attachEvents();updateSyncUI();try{"
SAFE_BOOT_START = """async function boot(){
  paintIcons();
  try{
    attachEvents();
    window.__ownerEventsReady=true;
  }catch(error){
    console.error('Owner event setup failed',error);
    window.__ownerEventSetupError=error;
    window.__ownerEventsReady=false;
  }
  try{updateSyncUI()}catch(error){
    console.error('Owner sync UI setup failed',error);
  }
  try{"""

OLD_REFRESH_ALL = "async function refreshAll(){await Promise.all([refreshMasterData(),loadDashboard(),loadActivity()]);renderItems();renderParties();renderActivity()}"
SAFE_REFRESH_ALL = """async function refreshAll(){
  const jobs=await Promise.allSettled([
    refreshMasterData(),
    loadDashboard(),
    loadActivity()
  ]);
  const failed=jobs.filter(row=>row.status==='rejected');
  failed.forEach(row=>console.error('Dashboard section failed',row.reason));
  try{renderItems()}catch(error){console.error('Item render failed',error)}
  try{renderParties()}catch(error){console.error('Party render failed',error)}
  try{renderActivity()}catch(error){console.error('Activity render failed',error)}
  if(failed.length){
    toast(`${failed.length} dashboard section${failed.length===1?'':'s'} could not load. Other features remain available.`,true);
  }
}"""

OLD_ENTER_APP = "async function enterApp(){state.me=await api('/api/me');$('#auth-screen').classList.add('hidden');$('#app-shell').classList.remove('hidden');$('#shop-name').textContent=state.me.business.name;$('#drawer-shop').textContent=state.me.business.name;$('#profile-btn').textContent=(state.me.business.owner_name||state.me.business.name||'A')[0].toUpperCase();fillBusinessForm();await refreshAll();const requested=new URLSearchParams(location.search).get('page');navigate(requested&&$(`#page-${requested}`)?requested:'home');flushQueue()}"
SAFE_ENTER_APP = """async function enterApp(){
  state.me=await api('/api/me');
  $('#auth-screen')?.classList.add('hidden');
  $('#app-shell')?.classList.remove('hidden');
  if($('#shop-name'))$('#shop-name').textContent=state.me.business.name;
  if($('#drawer-shop'))$('#drawer-shop').textContent=state.me.business.name;
  if($('#profile-btn'))$('#profile-btn').textContent=(state.me.business.owner_name||state.me.business.name||'A')[0].toUpperCase();
  try{fillBusinessForm()}catch(error){console.error('Business form fill failed',error)}
  const requested=new URLSearchParams(location.search).get('page');
  navigate(requested&&$(`#page-${requested}`)?requested:'home');
  await refreshAll();
  flushQueue();
}"""

BOOT_CALL = "\nboot();"
SAFE_BOOT_CALL = r"""
// Emergency navigation remains active only when the full event setup failed.
document.addEventListener('click',event=>{
  if(window.__ownerEventsReady)return;
  const target=event.target.closest&&event.target.closest('[data-go]');
  if(!target)return;
  const page=target.dataset.go;
  const pageNode=document.querySelector(`#page-${page}`);
  if(!pageNode)return;
  event.preventDefault();
  document.querySelectorAll('.page').forEach(node=>node.classList.toggle('active',node===pageNode));
  document.querySelectorAll('.bottom-nav button').forEach(node=>node.classList.toggle('active',node.dataset.go===page));
  window.scrollTo(0,0);
},true);

window.__showOwnerBootError=function(error){
  console.error('Owner dashboard boot failed',error);
  const auth=document.querySelector('#auth-screen');
  const shell=document.querySelector('#app-shell');
  const login=document.querySelector('#login-box');
  const token=localStorage.getItem('ks_token');
  let box=document.querySelector('#owner-runtime-error');
  if(!box){
    box=document.createElement('div');
    box.id='owner-runtime-error';
    box.style.cssText='position:fixed;left:14px;right:14px;bottom:82px;z-index:999999;padding:14px 16px;border-radius:14px;background:#fff0ef;color:#9f241c;border:1px solid #ffc6c1;box-shadow:0 12px 34px #0002;font:700 13px/1.45 Arial,sans-serif;';
    document.body.appendChild(box);
  }
  box.textContent='Dashboard startup error: '+String(error&&error.message||error||'Unknown error');
  if(token && shell){
    auth&&auth.classList.add('hidden');
    login&&login.classList.add('hidden');
    shell.classList.remove('hidden');
  }
};
boot().catch(window.__showOwnerBootError);"""

# Direct ID listeners are optional because extensions can add/remove controls.
DIRECT_ID_LISTENER = re.compile(r"(\$\((?:'[^']*'|\"[^\"]*\")\))\.addEventListener")


def corrected_owner_core() -> str:
    core = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    core = core.replace(BROKEN_LINE, FIXED_LINE, 1)
    core = DIRECT_ID_LISTENER.sub(r"\1?.addEventListener", core)
    core = core.replace(OLD_REFRESH_ALL, SAFE_REFRESH_ALL, 1)
    core = core.replace(OLD_ENTER_APP, SAFE_ENTER_APP, 1)
    core = core.replace(BOOT_START, SAFE_BOOT_START, 1)
    if BOOT_CALL in core:
        core = core.rsplit(BOOT_CALL, 1)[0] + "\n" + SAFE_BOOT_CALL + "\n"
    return core


def no_cache_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-Owner-Core-Version": "075",
    }


@app.middleware("http")
async def serve_correct_owner_core(request: Request, call_next):
    if request.method == "GET" and request.url.path.rstrip("/") == "/owner-core.js":
        return Response(
            corrected_owner_core(),
            media_type="application/javascript",
            headers=no_cache_headers(),
        )
    return await call_next(request)
