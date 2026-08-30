from __future__ import annotations

import re

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

import backend.ai_counter_ext as counter
import backend.ai_counter_route_order_ext as desk
from backend.app import app, db, now_iso

VERSION = "204"
_prev_page = desk._desk_page_with_quantity_fix


class CounterCustomerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(default="", max_length=30)


@app.post("/api/ai-counter/customer")
def ai_counter_create_customer(
    payload: CounterCustomerIn,
    bid: int = Depends(counter._kiosk_business),
):
    name = re.sub(r"\s+", " ", str(payload.name or "")).strip()
    phone = re.sub(r"[^0-9+]", "", str(payload.phone or "")).strip()
    if len(name) < 2:
        raise HTTPException(400, "Customer name required")

    with db() as conn:
        existing = None
        digits = re.sub(r"\D", "", phone)
        if digits:
            rows = conn.execute(
                "SELECT id,name,phone,balance FROM parties WHERE business_id=? AND type IN ('customer','both')",
                (bid,),
            ).fetchall()
            for row in rows:
                old_digits = re.sub(r"\D", "", str(row["phone"] or ""))
                if old_digits and old_digits == digits:
                    existing = row
                    break
        if existing is None:
            existing = conn.execute(
                "SELECT id,name,phone,balance FROM parties WHERE business_id=? AND type IN ('customer','both') AND lower(trim(name))=lower(trim(?)) ORDER BY id LIMIT 1",
                (bid, name),
            ).fetchone()
        if existing:
            return {"ok": True, "created": False, "customer": dict(existing)}

        ts = now_iso()
        cur = conn.execute(
            "INSERT INTO parties(business_id,name,type,phone,gstin,address,opening_balance,balance,created_at,updated_at) VALUES(?,?,?,?,?,?,0,0,?,?)",
            (bid, name, "customer", phone, "", "", ts, ts),
        )
        row = conn.execute(
            "SELECT id,name,phone,balance FROM parties WHERE id=? AND business_id=?",
            (cur.lastrowid, bid),
        ).fetchone()
        return {"ok": True, "created": True, "customer": dict(row)}


# Keep the kiosk customer-create API before the SPA catch-all route.
_matches = [r for r in list(app.router.routes) if getattr(r, "path", None) == "/api/ai-counter/customer"]
for _r in _matches:
    try:
        app.router.routes.remove(_r)
    except ValueError:
        pass
_fallback = next(
    (i for i, r in enumerate(app.router.routes) if getattr(r, "path", None) == "/{path:path}"),
    len(app.router.routes),
)
app.router.routes[_fallback:_fallback] = _matches

STYLE = r'''
<style id="ai-customer-add-204">
.customer-add-btn{width:100%;min-height:58px;border:1px dashed #8fb4ff;border-radius:17px;background:linear-gradient(135deg,#f3f7ff,#f8f4ff);color:#3157c8;font-weight:900;font-size:16px;padding:14px 16px}
#customerModal .modal-card{max-width:460px}#customerModal .customer-modal-icon{width:58px;height:58px;border-radius:18px;background:linear-gradient(135deg,#eaf2ff,#f2ecff);display:grid;place-items:center;font-size:28px;margin-bottom:10px}#customerModal .customer-help{margin:0 0 16px;color:#64748b;font-size:14px}
</style>
'''

MODAL = r'''
<div id="customerModal" class="modal hidden"><div class="modal-card"><div class="customer-modal-icon">👤</div><h2>Naya Customer Add Karein</h2><p class="customer-help">Naam zaroori hai. Mobile optional hai, lekin dene se customer dobara jaldi mil jayega.</p><div class="field"><label>Customer Name</label><input id="newCustomerName" autocomplete="off"></div><div class="field"><label>Mobile Number</label><input id="newCustomerPhone" inputmode="tel" autocomplete="off" placeholder="Optional"></div><div class="modal-actions"><button id="cancelCustomer" type="button">Cancel</button><button id="saveCustomer" type="button" class="primary">Save & Select</button></div></div></div>
'''

SCRIPT = r'''
/* ai-customer-add-script-204 */
 window.__aiCustomerAdd204=true;
 var lastCustomerSpeech='';
 function customerSpeech(){
  var heard=$('heard'),text=lastCustomerSpeech||(heard?heard.textContent:'');
  return String(text||'').replace(/^(?:you|aap)\s*:\s*/i,'').trim();
 }
 function openCustomerModal(){
  var m=$('customerModal');if(!m)return;
  $('newCustomerName').value=customerSpeech();
  $('newCustomerPhone').value='';m.classList.remove('hidden');
  setTimeout(function(){$('newCustomerName').focus()},60);
 }
 function closeCustomerModal(){var m=$('customerModal');if(m)m.classList.add('hidden')}
 function ensureAddCustomer(){
  // `S` is declared with top-level `const` in the kiosk page. Such bindings are
  // globally accessible but are not properties of `window`.
  if(typeof S==='undefined'||S.stage!=='customer')return;
  var c=$('choices');if(!c||c.querySelector('[data-add-customer-204]'))return;
  if(!customerSpeech())return;
  var b=document.createElement('button');b.type='button';b.className='customer-add-btn';b.setAttribute('data-add-customer-204','1');b.textContent='➕ Naya Customer Add Karein';b.onclick=openCustomerModal;
  var retry=c.querySelector('.choice-action');c.insertBefore(b,retry||null);
 }
 var baseProcess=processSpeech;
 processSpeech=async function(raw){
  var wasCustomer=S.stage==='customer';
  if(wasCustomer)lastCustomerSpeech=String(raw||'').trim();
  var result=await baseProcess(raw);
  if(wasCustomer&&S.stage==='customer')setTimeout(ensureAddCustomer,0);
  return result;
 };
 $('cancelCustomer').onclick=closeCustomerModal;
 $('saveCustomer').onclick=async function(){
  clearFail();var name=$('newCustomerName').value.trim(),phone=$('newCustomerPhone').value.trim();
  if(name.length<2){fail('Customer name daliye.');return}
  var btn=this,old=btn.textContent;btn.disabled=true;btn.textContent='Saving…';
  try{
   var d=await api('/api/ai-counter/customer',{method:'POST',body:JSON.stringify({name:name,phone:phone})});
   S.customer=d.customer;S.stage='items';S.pay='';$('choices').innerHTML='';closeCustomerModal();render();
   say(d.customer.name+' select ho gaye. Ab items boliye.');
  }catch(e){fail(e.message||'Customer add nahi hua.')}finally{btn.disabled=false;btn.textContent=old}
 };
 var c=$('choices');if(c&&window.MutationObserver)new MutationObserver(function(){if(S.stage==='customer')setTimeout(ensureAddCustomer,0)}).observe(c,{childList:true});
'''


def _page() -> str:
    page = _prev_page()
    if "ai-customer-add-script-204" in page:
        return page
    page = page.replace("</head>", STYLE + "</head>", 1)
    page = page.replace("<script>\n(function(){", MODAL + "\n<script>\n(function(){", 1)
    marker = "$('scanBarcode').onclick=openScanner;"
    if marker in page:
        page = page.replace(marker, SCRIPT + "\n" + marker, 1)
    return page


desk._desk_page_with_quantity_fix = _page
