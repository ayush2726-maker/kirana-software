from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from backend.app import STATIC_DIR, app
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.photo_bill_barcode_ext as smart


VERSION = "167"
RUNTIME_FILE = STATIC_DIR / "owner-smart-tools-runtime.js"
RUNTIME_PATH = "/owner-smart-tools-runtime.js"
LEARNING_FILE = STATIC_DIR / "local-handwriting-learning.js"
LEARNING_PATH = "/local-handwriting-learning.js"
SAFETY_FILE = STATIC_DIR / "owner-smart-tools-safety.js"
SAFETY_PATH = "/owner-smart-tools-safety.js"


def _no_cache() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }


def _remove_legacy_inline_runtime(page: str) -> str:
    start = page.rfind("<script>")
    if start < 0:
        return page
    end = page.find("</script>", start)
    if end < 0:
        return page
    return page[:start] + page[end + len("</script>") :]


def _camera_upload_ui(page: str) -> str:
    old = '<label class="upload"><strong>📷 Take Photo / Upload Bill</strong><input id="bill-photo" type="file" accept="image/*" capture="environment" /><small id="photo-name">Clear, straight full bill photo best rahegi</small></label>'
    new = '''<div class="upload"><strong>📷 Bill Photo</strong><input id="bill-photo" type="file" accept="image/*" style="display:none" /><div class="actions" style="width:100%;margin-top:2px"><button type="button" class="primary" id="take-photo" style="flex:1">📷 Take Photo</button><button type="button" class="secondary" id="upload-photo" style="flex:1">📁 Upload Photo</button></div><small id="photo-name">Camera se photo lo ya gallery/file se upload karo</small></div>'''
    return page.replace(old, new, 1)


CAMERA_HELPER = r'''
<script>
(function(){
  var input=document.getElementById('bill-photo');
  var take=document.getElementById('take-photo');
  var upload=document.getElementById('upload-photo');
  var name=document.getElementById('photo-name');
  if(!input||!take||!upload)return;
  take.addEventListener('click',function(){input.setAttribute('capture','environment');input.click();});
  upload.addEventListener('click',function(){input.removeAttribute('capture');input.click();});
  input.addEventListener('change',function(){
    var f=input.files&&input.files[0];
    if(name)name.textContent=f?f.name:'Camera se photo lo ya gallery/file se upload karo';
  });
})();
</script>
'''


@app.middleware("http")
async def serve_smart_tools_runtime_fix(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"

    if request.method == "GET" and path == RUNTIME_PATH:
        return Response(
            RUNTIME_FILE.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={**_no_cache(), "X-Kirana-Smart-Runtime": VERSION},
        )

    if request.method == "GET" and path == LEARNING_PATH:
        return Response(
            LEARNING_FILE.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={**_no_cache(), "X-Kirana-Local-Learning": VERSION},
        )

    if request.method == "GET" and path == SAFETY_PATH:
        return Response(
            SAFETY_FILE.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={**_no_cache(), "X-Kirana-Draft-Safety": VERSION},
        )

    if request.method == "GET" and path == "/owner/smart-tools":
        session = _session_row(request.cookies.get(COOKIE_NAME))
        if not session:
            return RedirectResponse("/owner-login", status_code=303)

        page = smart.SMART_PAGE.read_text(encoding="utf-8")
        page = _remove_legacy_inline_runtime(page)
        page = _camera_upload_ui(page)
        scripts = (
            f'<script src="{RUNTIME_PATH}?v={VERSION}"></script>'
            f'<script src="{LEARNING_PATH}?v={VERSION}"></script>'
            f'<script src="{SAFETY_PATH}?v={VERSION}"></script>'
            + CAMERA_HELPER
        )
        page = page.replace("</body>", scripts + "</body>", 1)

        return HTMLResponse(
            page,
            headers={
                **_no_cache(),
                "X-Kirana-Smart-Tools": VERSION,
                "Clear-Site-Data": '"cache"',
            },
        )

    return await call_next(request)
