from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

import backend.ai_counter_ext as counter
import backend.ai_counter_route_order_ext as desk
from backend.app import TransactionIn, TxLineIn, app, db, insert_sale, now_iso, today_iso

VERSION = "185"


class CounterRateLineIn(BaseModel):
    item_id: int
    qty: float = Field(gt=0, le=9999)
    rate: float | None = Field(default=None, gt=0, le=10_000_000)


class CounterRateCheckoutIn(BaseModel):
    checkout_key: str = Field(min_length=8, max_length=120)
    customer_id: int | None = None
    payment_mode: str = "cash"
    items: list[CounterRateLineIn] = Field(min_items=1, max_items=100)


# Replace the older checkout route so a spoken rate can be carried all the way
# into the final sale instead of being overwritten by the catalogue/history rate.
for route in list(app.router.routes):
    if getattr(route, "path", None) == "/api/ai-counter/checkout" and "POST" in (getattr(route, "methods", set()) or set()):
        app.router.routes.remove(route)


@app.post("/api/ai-counter/checkout")
def ai_counter_checkout_with_spoken_rate(
    payload: CounterRateCheckoutIn,
    bid: int = Depends(counter._kiosk_business),
):
    counter._init_counter_schema()
    mode = str(payload.payment_mode or "cash").lower()
    if mode not in {"cash", "upi", "credit"}:
        raise HTTPException(400, "Payment mode must be cash, upi or credit")
    if mode == "credit" and not payload.customer_id:
        raise HTTPException(400, "Credit bill ke liye customer select karna zaroori hai")

    with db() as conn:
        existing = conn.execute(
            "SELECT sale_id FROM ai_counter_checkouts WHERE business_id=? AND checkout_key=?",
            (bid, payload.checkout_key),
        ).fetchone()
        if existing:
            sale = conn.execute(
                "SELECT * FROM sales WHERE id=? AND business_id=?",
                (existing["sale_id"], bid),
            ).fetchone()
            if sale:
                result = dict(sale)
                result["items"] = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT * FROM sale_items WHERE sale_id=? ORDER BY id",
                        (sale["id"],),
                    ).fetchall()
                ]
                result["replayed"] = True
                return result

        if payload.customer_id:
            customer = conn.execute(
                "SELECT id FROM parties WHERE id=? AND business_id=? AND type IN ('customer','both')",
                (payload.customer_id, bid),
            ).fetchone()
            if not customer:
                raise HTTPException(404, "Customer not found")

        tx_lines: list[TxLineIn] = []
        estimate = 0.0
        for raw in payload.items:
            item = conn.execute(
                "SELECT * FROM items WHERE id=? AND business_id=? AND COALESCE(archived_at,'')=''",
                (raw.item_id, bid),
            ).fetchone()
            if not item:
                raise HTTPException(404, f"Item {raw.item_id} not found")
            d: dict[str, Any] = dict(item)
            rate = float(raw.rate) if raw.rate is not None else counter._last_customer_rate(
                conn, bid, payload.customer_id, d
            )
            gst = float(item["gst_rate"] or 0)
            estimate += float(raw.qty) * rate * (1 + gst / 100)
            tx_lines.append(
                TxLineIn(
                    item_id=int(item["id"]),
                    item_name=str(item["name"]),
                    size=str(item["size"] or ""),
                    qty=float(raw.qty),
                    rate=rate,
                    gst_rate=gst,
                )
            )

        tx = TransactionIn(
            party_id=payload.customer_id,
            invoice_date=today_iso(),
            paid=0 if mode == "credit" else round(estimate, 2),
            payment_mode=mode,
            notes="AI Billing Desk",
            items=tx_lines,
        )
        sale = insert_sale(conn, bid, tx)
        conn.execute(
            "INSERT INTO ai_counter_checkouts(business_id,checkout_key,sale_id,created_at) VALUES(?,?,?,?)",
            (bid, payload.checkout_key, sale["id"], now_iso()),
        )
        sale["replayed"] = False
        sale["print_url"] = f"/owner/print-center/print?items=sale:{sale['id']}&autoprint=true"
        return sale


# Keep the replacement API before the SPA catch-all.
matches = [r for r in list(app.router.routes) if getattr(r, "path", None) == "/api/ai-counter/checkout"]
for r in matches:
    try:
        app.router.routes.remove(r)
    except ValueError:
        pass
fallback = next(
    (i for i, r in enumerate(app.router.routes) if getattr(r, "path", None) == "/{path:path}"),
    len(app.router.routes),
)
app.router.routes[fallback:fallback] = matches


_prev_page = desk._desk_page_with_quantity_fix

PATCH_JS = r'''
var _baseProcessSpeechRate185=processSpeech;
function parseSpokenQtyRate185(raw){
 var t=String(raw||'').trim();
 var q=qty(t);if(!q)return null;
 var m=t.match(/(?:₹\s*)?(\d+(?:\.\d+)?)\s*(?:रुपये?|रुपया|rs\.?|rupees?)?\s*(?:के\s*(?:भाव|रेट)\s*से|के\s*भाव\s*से|भाव\s*से|रेट\s*से|rate)?\s*$/i);
 if(!m)return null;
 var rate=Number(m[1]);if(!(rate>0))return null;
 var before=t.slice(0,m.index).trim();
 var itemText=before.replace(/^\s*(?:\d+(?:\.\d+)?|एक|दो|तीन|चार|पांच|पाँच|छह|सात|आठ|नौ|दस|आधा|डे[ढ़ढ़]|पाव|aadha|half|dedh|pav|paav)\s*(?:किलो|किलोग्राम|kg|kgs?|kilo|kilogram|ग्राम|gram|grams?|gm|लीटर|लिटर|ltr|liter|litre|पीस|pcs?|piece|पैकेट|packet|pack)?\s*/i,'').trim();
 itemText=itemText.replace(/\s+(?:का|के)?\s*(?:भाव|रेट)\s*$/i,'').trim();
 if(!itemText)return null;
 return {q:q,rate:rate,itemText:itemText};
}
function addWithRate185(item,q,rate){
 addItem(item,q,true);
 var line=S.cart.find(function(x){return Number(x.item.id)===Number(item.id)});
 if(line){line.item=Object.assign({},line.item,{sale_price:Number(rate)});line.rateOverride=Number(rate);line.qty=Number(q.qty);line.displayUnit=q.unit||line.displayUnit||line.item.unit||''}
 render();
 say(item.name+' '+displayQty(line)+' '+money(rate)+' ke bhav se add kar diya. Aur kuch?');
}
processSpeech=async function(raw){
 var p=(S.stage==='items')?parseSpokenQtyRate185(raw):null;
 if(!p)return _baseProcessSpeechRate185(raw);
 clearFail();$('heard').textContent='You: '+String(raw||'');
 try{
  var d=await api('/api/ai-counter/interpret',{method:'POST',body:JSON.stringify({utterance:p.itemText,stage:'items'})});
  if(d.intent==='items'&&d.items&&d.items[0]){addWithRate185(d.items[0].item,p.q,p.rate);return}
  if(d.intent==='item_candidates'){
   var rows=d.groups&&d.groups[0]?d.groups[0].matches:[];
   choices(rows,function(r){addWithRate185(r,p.q,p.rate)});say('Item clear nahi hai. Sahi item select kijiye.');return;
  }
  say(d.say||'Item nahi mila. Naam dobara boliye.');
 }catch(e){fail(e.message)}
};
checkout=async function(){
 if(!S.cart.length)return say('Pehle item add kijiye.');
 if(S.stage!=='payment'||!S.pay)return choosePayment();
 if(S.pay==='credit'&&!S.customer){S.stage='customer';S.pay='';$('paymentButtons').classList.add('hidden');return say('Credit bill ke liye customer select kijiye.')}
 try{
  if(!S.checkoutKey)S.checkoutKey='desk-'+Date.now()+'-'+Math.random().toString(36).slice(2);
  var sale=await api('/api/ai-counter/checkout',{method:'POST',body:JSON.stringify({checkout_key:S.checkoutKey,customer_id:S.customer?S.customer.id:null,payment_mode:S.pay,items:S.cart.map(function(x){return {item_id:x.item.id,qty:x.qty,rate:x.rateOverride||null}})})});
  S.lastPrint=sale.print_url||'';$('desk').classList.add('hidden');$('completeScreen').classList.remove('hidden');$('completeText').textContent='Bill '+sale.invoice_no+' • '+money(sale.total)+' • '+S.pay.toUpperCase();$('printBill').classList.toggle('hidden',!S.lastPrint);say('Bill complete. Total '+money(sale.total));
 }catch(e){fail(e.message)}
};
'''


def _page_with_spoken_rate() -> str:
    page = _prev_page()
    marker = "$('scanBarcode').onclick=openScanner;"
    if "parseSpokenQtyRate185" not in page and marker in page:
        page = page.replace(marker, PATCH_JS + "\n" + marker, 1)
    return page


desk._desk_page_with_quantity_fix = _page_with_spoken_rate
