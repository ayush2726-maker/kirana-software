from __future__ import annotations

from fastapi import Request
from fastapi.responses import Response

from backend.app import STATIC_DIR, app


BROKEN_LINE = "if(metaEl)metaEl.textContent=`${line.size?`${line.size} · `:''}${line.unit||'pcs'} · GST ${line.gst_rate}%`}updateCartTotals(k)}"
FIXED_LINE = "if(metaEl)metaEl.textContent=`${line.size?`${line.size} · `:''}${line.unit||'pcs'} · GST ${line.gst_rate}%`;updateCartTotals(k)}}"

BOOT_START = "async function boot(){paintIcons();attachEvents();updateSyncUI();try{"
SAFE_BOOT_START = """async function boot(){
  paintIcons();
  try{attachEvents()}catch(error){
    console.error('Owner event setup failed',error);
    window.__ownerEventSetupError=error;
  }
  try{updateSyncUI()}catch(error){
    console.error('Owner sync UI setup failed',error);
  }
  try{"""

BOOT_CALL = "\nboot();"
SAFE_BOOT_CALL = r"""
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
    box.style.cssText='position:fixed;left:14px;right:14px;bottom:18px;z-index:999999;padding:14px 16px;border-radius:14px;background:#fff0ef;color:#9f241c;border:1px solid #ffc6c1;box-shadow:0 12px 34px #0002;font:700 13px/1.45 Arial,sans-serif;';
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


def corrected_owner_core() -> str:
    core = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    core = core.replace(BROKEN_LINE, FIXED_LINE, 1)
    core = core.replace(BOOT_START, SAFE_BOOT_START, 1)
    if BOOT_CALL in core:
        core = core.rsplit(BOOT_CALL, 1)[0] + "\n" + SAFE_BOOT_CALL + "\n"
    return core


def no_cache_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-Owner-Core-Version": "072",
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
