from __future__ import annotations

import hashlib
import re
import secrets
from datetime import date, timedelta
from difflib import SequenceMatcher
from typing import Any

from fastapi import Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

from backend.app import STATIC_DIR, TransactionIn, TxLineIn, app, current_user, db, insert_sale, now_iso, today_iso

KIOSK_PAGE = STATIC_DIR / "ai-counter.html"
TOKEN_DAYS = 120

class CounterInterpretIn(BaseModel):
    utterance: str = Field(min_length=1, max_length=500)
    stage: str = "customer"
class CounterLineIn(BaseModel):
    item_id: int
    qty: float = Field(gt=0, le=9999)
class CounterCheckoutIn(BaseModel):
    checkout_key: str = Field(min_length=8, max_length=120)
    customer_id: int | None = None
    payment_mode: str = "cash"
    items: list[CounterLineIn] = Field(min_items=1, max_items=100)

NUMBER_WORDS={"ek":1,"one":1,"1":1,"एक":1,"do":2,"two":2,"2":2,"दो":2,"teen":3,"three":3,"3":3,"तीन":3,"char":4,"chaar":4,"four":4,"4":4,"चार":4,"panch":5,"paanch":5,"five":5,"5":5,"पांच":5,"che":6,"chhe":6,"six":6,"6":6,"छह":6,"saat":7,"seven":7,"7":7,"सात":7,"aath":8,"eight":8,"8":8,"आठ":8,"nau":9,"nine":9,"9":9,"नौ":9,"das":10,"ten":10,"10":10,"दस":10,"aadha":.5,"adha":.5,"half":.5,"आधा":.5,"paav":.25,"pav":.25,"quarter":.25,"पाव":.25}
HINDI_WORDS={
"काबुली":"kabuli","काबली":"kabuli","चना":"chana","चने":"chana","देसी":"desi","देशी":"desi","शक्कर":"shakkar","शकर":"shakkar","चीनी":"sugar","पिसी":"pisi","दाल":"dal","तेल":"oil","चावल":"rice","आटा":"atta","मैदा":"maida","सूजी":"suji","रवा":"rava","बेसन":"besan","नमक":"salt","हल्दी":"haldi","मिर्च":"mirch","धनिया":"dhaniya","जीरा":"jeera","अजवाइन":"ajwain","सौंफ":"saunf","मूंग":"moong","मूँग":"moong","मसूर":"masoor","उड़द":"urad","उड़द":"urad","अरहर":"arhar","तुअर":"toor","तूर":"toor","राजमा":"rajma","मटर":"matar","मूंगफली":"moongfali","गुड़":"gud","गुड़":"gud","साबूदाना":"sabudana","पोहे":"poha","पोहा":"poha","दलिया":"daliya","नारियल":"nariyal","बादाम":"badam","काजू":"kaju","किशमिश":"kishmish","मखाना":"makhana","साबुन":"sabun","सर्फ":"surf","विम":"vim","किलो":"kg","किलोग्राम":"kg","ग्राम":"g","लीटर":"ltr","लिटर":"ltr","पैकेट":"packet","पैक":"pack","बोतल":"bottle","डिब्बा":"box","हटाओ":"remove","निकालो":"remove","और":"and","फिर":"then"}
ALIASES={"sugar":"shakkar","chini":"shakkar","kabli":"kabuli","chhole":"chana","chole":"chana","channa":"chana","deshi":"desi","kg":"kilogram","kilo":"kilogram","ltr":"liter","litre":"liter"}

def _token_hash(token:str)->str:return hashlib.sha256(token.encode()).hexdigest()
def _norm(value:Any)->str:
    text=str(value or "").lower().strip().replace("₹"," ").replace("&"," and ")
    for src,dst in HINDI_WORDS.items(): text=text.replace(src," "+dst+" ")
    text=re.sub(r"[^\w.]+"," ",text,flags=re.UNICODE)
    words=[ALIASES.get(w,w) for w in text.split()]
    return " ".join(words).strip()
def _qty_from_segment(segment:str)->float:
    raw=str(segment or "").lower(); words=raw.split()+_norm(raw).split()
    for word in words[:8]:
        if word in NUMBER_WORDS:return float(NUMBER_WORDS[word])
        try:
            v=float(word)
            if 0<v<=9999:return v
        except ValueError:pass
    return 1.0

def _init_counter_schema():
    with db() as conn: conn.executescript("""CREATE TABLE IF NOT EXISTS ai_counter_tokens(id INTEGER PRIMARY KEY AUTOINCREMENT,business_id INTEGER NOT NULL,token_hash TEXT NOT NULL UNIQUE,label TEXT DEFAULT 'AI Desk',expires_on TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,last_used_at TEXT DEFAULT '');CREATE INDEX IF NOT EXISTS idx_ai_counter_tokens_business ON ai_counter_tokens(business_id,active);CREATE TABLE IF NOT EXISTS ai_counter_checkouts(business_id INTEGER NOT NULL,checkout_key TEXT NOT NULL,sale_id INTEGER NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(business_id,checkout_key));""")
@app.on_event("startup")
def ai_counter_startup():_init_counter_schema()
def _kiosk_business(x_kiosk_token:str|None=Header(default=None,alias="X-Kiosk-Token"))->int:
    token=str(x_kiosk_token or "").strip()
    if not token:raise HTTPException(401,"AI Desk token required")
    with db() as conn:
        row=conn.execute("SELECT * FROM ai_counter_tokens WHERE token_hash=? AND active=1 AND expires_on>=?",(_token_hash(token),today_iso())).fetchone()
        if not row:raise HTTPException(401,"AI Desk token expired or invalid")
        conn.execute("UPDATE ai_counter_tokens SET last_used_at=? WHERE id=?",(now_iso(),row["id"]));return int(row["business_id"])
def _active_items(conn,bid):return [dict(r) for r in conn.execute("SELECT id,name,size,unit,sku,barcode,sale_price,gst_rate,stock FROM items WHERE business_id=? AND COALESCE(archived_at,'')='' ORDER BY name,size LIMIT 2500",(bid,)).fetchall()]
def _customers(conn,bid):return [dict(r) for r in conn.execute("SELECT id,name,phone,balance FROM parties WHERE business_id=? AND type IN ('customer','both') ORDER BY name LIMIT 2500",(bid,)).fetchall()]
def _score(text,candidate):
    a,b=_norm(text),_norm(candidate)
    if not a or not b:return 0.0
    if b in a or a in b:return .98
    at,bt=set(a.split()),set(b.split()); overlap=len(at&bt)/max(1,min(len(at),len(bt)))
    return max(overlap,SequenceMatcher(None,a,b).ratio())
def _best_rows(text,rows,limit=4):
    ranked=[]
    for row in rows:
        label=" ".join(str(row.get(k) or "") for k in ("name","size","unit","sku","barcode"));score=_score(text,label)
        if score>=.38:ranked.append((score,row))
    ranked.sort(key=lambda p:p[0],reverse=True);return [{**r,"match_score":round(s,3)} for s,r in ranked[:limit]]
def _last_customer_rate(conn,bid,customer_id,item):
    default=float(item.get("sale_price") or 0)
    if not customer_id:return default
    cutoff=(date.today()-timedelta(days=15)).isoformat();row=conn.execute("SELECT si.rate FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE s.business_id=? AND s.party_id=? AND si.item_id=? AND s.invoice_date>=? ORDER BY s.invoice_date DESC,s.id DESC,si.id DESC LIMIT 1",(bid,customer_id,item["id"],cutoff)).fetchone()
    return float(row["rate"]) if row and float(row["rate"] or 0)>0 else default
@app.post("/api/ai-counter/kiosk-token")
def create_ai_counter_token(user:dict=Depends(current_user)):
    _init_counter_schema();token=secrets.token_urlsafe(36);expires=(date.today()+timedelta(days=TOKEN_DAYS)).isoformat()
    with db() as conn:
        conn.execute("UPDATE ai_counter_tokens SET active=0 WHERE business_id=?",(user["business_id"],));conn.execute("INSERT INTO ai_counter_tokens(business_id,token_hash,label,expires_on,active,created_at) VALUES(?,?,?,?,1,?)",(user["business_id"],_token_hash(token),"AI Billing Desk",expires,now_iso()))
    return {"ok":True,"token":token,"expires_on":expires,"url":f"/owner/ai-desk?token={token}"}
@app.get("/owner/ai-desk")
def ai_counter_page(token:str=Query(default="")):
    if not KIOSK_PAGE.exists():raise HTTPException(404,"AI Desk page missing")
    if token:
        with db() as conn:row=conn.execute("SELECT id FROM ai_counter_tokens WHERE token_hash=? AND active=1 AND expires_on>=?",(_token_hash(token),today_iso())).fetchone()
        if not row:return RedirectResponse("/owner-login",303)
    return FileResponse(KIOSK_PAGE,headers={"Cache-Control":"no-store","X-Kirana-AI-Desk":"1"})
@app.get("/api/ai-counter/bootstrap")
def ai_counter_bootstrap(bid:int=Depends(_kiosk_business)):
    with db() as conn:
        business=conn.execute("SELECT id,name FROM businesses WHERE id=?",(bid,)).fetchone();return {"business":dict(business) if business else {"id":bid,"name":"Kirana Software"},"customers":_customers(conn,bid),"items":_active_items(conn,bid)}
@app.post("/api/ai-counter/interpret")
def ai_counter_interpret(payload:CounterInterpretIn,bid:int=Depends(_kiosk_business)):
    text=_norm(payload.utterance)
    if not text:return {"intent":"unknown","say":"Awaaz clear nahi aayi. Dobara boliye."}
    if any(x in text for x in ("cancel bill","reset","naya bill","new bill","shuru se")):return {"intent":"reset","say":"Theek hai, naya bill shuru karte hain."}
    if any(x in text for x in ("bas","bill karo","bill kar do","checkout","done","ho gaya")):return {"intent":"checkout","say":"Theek hai. Payment cash, UPI ya credit?"}
    if any(x in text for x in ("upi","gpay","phonepe","paytm")):return {"intent":"payment","payment_mode":"upi","say":"UPI select ho gaya."}
    if any(x in text for x in ("credit","udhar","udhhar")):return {"intent":"payment","payment_mode":"credit","say":"Credit select ho gaya."}
    if text in {"cash","nakad"} or "cash payment" in text:return {"intent":"payment","payment_mode":"cash","say":"Cash select ho gaya."}
    with db() as conn:
        if payload.stage=="customer":
            if any(x in text for x in ("cash customer","skip","guest","without customer")):return {"intent":"cash_customer","say":"Cash customer. Ab items boliye."}
            found=[];digits=re.sub(r"\D","",text)
            for row in _customers(conn,bid):
                phone=re.sub(r"\D","",str(row.get("phone") or ""));score=max(_score(text,row.get("name") or ""),1.0 if digits and phone and (digits in phone or phone in digits) else 0)
                if score>=.42:found.append(({**row,"match_score":round(score,3)},score))
            found.sort(key=lambda p:p[1],reverse=True);found=[p[0] for p in found[:5]]
            if len(found)==1 or (found and found[0]["match_score"]>=.82 and (len(found)==1 or found[0]["match_score"]-found[1]["match_score"]>=.12)):return {"intent":"customer","customer":found[0],"say":f"{found[0]['name']} select ho gaye. Ab items boliye."}
            if found:return {"intent":"customer_candidates","matches":found,"say":"Milte-julte customers mile hain. Screen par customer select kijiye."}
            return {"intent":"customer_unknown","say":"Customer nahi mila. Naam ya mobile dobara boliye, ya cash customer boliye."}
        items=_active_items(conn,bid);remove_mode="remove" in text or any(x in text for x in ("hatao","delete","nikalo"));segments=[s.strip() for s in re.split(r"\b(?:and|aur|plus|then|phir)\b|[,;]",text) if s.strip()];resolved=[];ambiguous=[]
        for segment in segments[:12]:
            matches=_best_rows(segment,items,4)
            if not matches:continue
            top=matches[0]
            if top["match_score"]>=.62 and (len(matches)==1 or top["match_score"]-matches[1]["match_score"]>=.07):resolved.append({"item":top,"qty":_qty_from_segment(segment)})
            else:ambiguous.append({"text":segment,"matches":matches})
        if remove_mode and resolved:return {"intent":"remove","item_id":resolved[0]["item"]["id"],"say":f"{resolved[0]['item']['name']} hata diya."}
        if resolved:return {"intent":"items","items":resolved,"ambiguous":ambiguous,"say":", ".join(f"{x['qty']:g} {x['item']['name']}" for x in resolved[:4])+" add kar diya. Aur kuch?"}
        if ambiguous:return {"intent":"item_candidates","groups":ambiguous,"say":"Item clear nahi hai. Screen par sahi item select kijiye."}
    return {"intent":"unknown","say":"Ye item nahi mila. Naam ya quantity dobara boliye."}
@app.post("/api/ai-counter/checkout")
def ai_counter_checkout(payload:CounterCheckoutIn,bid:int=Depends(_kiosk_business)):
    _init_counter_schema();mode=str(payload.payment_mode or "cash").lower()
    if mode not in {"cash","upi","credit"}:raise HTTPException(400,"Payment mode must be cash, upi or credit")
    if mode=="credit" and not payload.customer_id:raise HTTPException(400,"Credit bill ke liye customer select karna zaroori hai")
    with db() as conn:
        existing=conn.execute("SELECT sale_id FROM ai_counter_checkouts WHERE business_id=? AND checkout_key=?",(bid,payload.checkout_key)).fetchone()
        if existing:
            sale=conn.execute("SELECT * FROM sales WHERE id=? AND business_id=?",(existing["sale_id"],bid)).fetchone()
            if sale:
                result=dict(sale);result["items"]=[dict(r) for r in conn.execute("SELECT * FROM sale_items WHERE sale_id=? ORDER BY id",(sale["id"],)).fetchall()];result["replayed"]=True;return result
        if payload.customer_id and not conn.execute("SELECT id FROM parties WHERE id=? AND business_id=? AND type IN ('customer','both')",(payload.customer_id,bid)).fetchone():raise HTTPException(404,"Customer not found")
        tx_lines=[];estimate=0.0
        for raw in payload.items:
            item=conn.execute("SELECT * FROM items WHERE id=? AND business_id=? AND COALESCE(archived_at,'')=''",(raw.item_id,bid)).fetchone()
            if not item:raise HTTPException(404,f"Item {raw.item_id} not found")
            d=dict(item);rate=_last_customer_rate(conn,bid,payload.customer_id,d);gst=float(item["gst_rate"] or 0);estimate+=float(raw.qty)*rate*(1+gst/100);tx_lines.append(TxLineIn(item_id=int(item["id"]),item_name=str(item["name"]),size=str(item["size"] or ""),qty=float(raw.qty),rate=rate,gst_rate=gst))
        tx=TransactionIn(party_id=payload.customer_id,invoice_date=today_iso(),paid=0 if mode=="credit" else round(estimate,2),payment_mode=mode,notes="AI Billing Desk",items=tx_lines);sale=insert_sale(conn,bid,tx);conn.execute("INSERT INTO ai_counter_checkouts(business_id,checkout_key,sale_id,created_at) VALUES(?,?,?,?)",(bid,payload.checkout_key,sale["id"],now_iso()));sale["replayed"]=False;sale["print_url"]=f"/owner/print-center/print?items=sale:{sale['id']}&autoprint=true";return sale
