from __future__ import annotations

import re
from io import BytesIO
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import pytesseract

from backend.app import app, db
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.quick_write_canvas_fix_ext as quick_canvas
import backend.quick_write_local_ai_ext as local_reader

VERSION = "159"

NUM_WORDS = {
    "आधा":0.5,"aadha":0.5,"half":0.5,"डेढ़":1.5,"dedh":1.5,
    "एक":1,"ek":1,"one":1,"दो":2,"do":2,"two":2,"तीन":3,"teen":3,"three":3,
    "चार":4,"char":4,"four":4,"पांच":5,"पाँच":5,"paanch":5,"five":5,
    "छह":6,"chhe":6,"six":6,"सात":7,"saat":7,"seven":7,"आठ":8,"aath":8,"eight":8,
    "नौ":9,"nau":9,"nine":9,"दस":10,"das":10,"ten":10,"बीस":20,"bees":20,
    "तीस":30,"tees":30,"चालीस":40,"chalis":40,"पचास":50,"pachas":50,
    "साठ":60,"saath":60,"सत्तर":70,"sattar":70,"अस्सी":80,"assi":80,"नब्बे":90,"nabbe":90,
    "सौ":100,"sau":100,"hundred":100,
}


def _ntext(text: Any) -> float:
    s=str(text or "").strip().lower().replace(",","")
    s=s.replace("½","0.5").replace("¼","0.25").replace("¾","0.75")
    m=re.search(r"\d+(?:\.\d+)?",s)
    if m:
        return float(m.group())
    return float(NUM_WORDS.get(s,0) or 0)


def _prep(raw: bytes) -> Image.Image:
    img=Image.open(BytesIO(raw)); img=ImageOps.exif_transpose(img).convert("L")
    if img.width<1200:
        sc=1200/max(1,img.width); img=img.resize((int(img.width*sc),int(img.height*sc)))
    img=ImageEnhance.Contrast(img).enhance(2.2)
    return img.filter(ImageFilter.SHARPEN)


def _crop_lines(img: Image.Image, x1: float, x2: float, lang: str, numeric: bool=False):
    crop=img.crop((int(img.width*x1),0,int(img.width*x2),img.height))
    cfg="--oem 3 --psm 6"
    if numeric:
        cfg += " -c tessedit_char_whitelist=0123456789./"
        lang="eng"
    data=pytesseract.image_to_data(crop,lang=lang,config=cfg,output_type=pytesseract.Output.DICT)
    groups={}; n=len(data.get("text",[]))
    for i in range(n):
        t=str(data["text"][i] or "").strip()
        if not t: continue
        key=(data.get("block_num",[0]*n)[i],data.get("par_num",[0]*n)[i],data.get("line_num",[0]*n)[i])
        y=float(data["top"][i])+float(data["height"][i])/2
        try: conf=max(0.0,min(1.0,float(data.get("conf",[0]*n)[i])/100.0))
        except Exception: conf=0.0
        groups.setdefault(key,[]).append((t,y,conf))
    out=[]
    for vals in groups.values():
        txt=" ".join(v[0] for v in vals).strip(); y=sum(v[1] for v in vals)/len(vals); c=sum(v[2] for v in vals)/len(vals)
        if txt: out.append({"text":txt,"y":y,"score":c})
    return sorted(out,key=lambda r:r["y"])


def _nearest(rows,y,tol):
    cand=[r for r in rows if abs(r["y"]-y)<=tol]
    return min(cand,key=lambda r:abs(r["y"]-y)) if cand else None


def _better_extract(raw: bytes) -> list[dict[str,Any]]:
    img=_prep(raw)
    # Read the three handwritten columns independently. This stops rate digits
    # from leaking into item names and qty from being treated as size.
    left=_crop_lines(img,0.00,0.24,"eng",True)
    try: middle=_crop_lines(img,0.18,0.74,"hin+eng",False)
    except Exception: middle=_crop_lines(img,0.18,0.74,"eng",False)
    right=_crop_lines(img,0.70,1.00,"eng",True)
    anchors=middle or right or left
    tol=max(28.0,img.height*0.025)
    out=[]
    for m in anchors:
        y=m["y"]; l=_nearest(left,y,tol); r=_nearest(right,y,tol)
        name=(m.get("text") if m in middle else "") or ""
        name=re.sub(r"^[\s\d./]+|[\s₹\d.,/]+$","",name).strip()
        if len(quick_canvas._norm(name))<2: continue
        qty=_ntext(l.get("text") if l else "") or 1.0
        rate=_ntext(r.get("text") if r else "")
        if not (0<qty<=999): qty=1.0
        if not (0<rate<=250000): rate=0.0
        score=(float(m.get("score") or 0)+(float(l.get("score") or 0) if l else 0)+(float(r.get("score") or 0) if r else 0))/3
        out.append({"item_name":name[:160],"source_text":name[:160],"qty":round(qty,3),"size":"","rate":round(rate,2),"confidence":round(score,3)})
    if not out:
        return local_reader._local_quick_extract(raw)
    return out[:40]

quick_canvas._gemini_canvas_extract=_better_extract


def _spoken_number(tok: str) -> float:
    tok=tok.strip().lower(); return _ntext(tok)


def _voice_rows(text: str, items, bill_type: str, conn, bid: int):
    text=str(text or "").strip()
    chunks=[c.strip() for c in re.split(r"(?:\s+फिर\s+|\s+next\s+|\s+अगला\s+|[,;\n]+)",text,flags=re.I) if c.strip()]
    out=[]
    for chunk in chunks:
        toks=chunk.split(); qty=1.0; rate=0.0
        if toks:
            q=_spoken_number(toks[0])
            if q>0: qty=q; toks=toks[1:]
        if toks:
            rr=_spoken_number(toks[-1])
            if rr>0: rate=rr; toks=toks[:-1]
        name=" ".join(toks).strip()
        name=re.sub(r"\b(?:rate|रेट|रुपये|रुपया|rs)\b"," ",name,flags=re.I).strip()
        if not name: continue
        item,score=quick_canvas._best(name,"",items)
        if item:
            final_rate=rate if rate>0 else quick_canvas._effective_rate(conn,bid,item,bill_type)
            out.append({"source_text":chunk,"item_id":int(item["id"]),"item_name":str(item.get("name") or name),"size":str(item.get("size") or ""),"qty":round(qty,3),"rate":round(final_rate,2),"gst_rate":round(quick_canvas.quick._number(item.get("gst_rate")),2),"match_confidence":round(score,3)})
        else:
            out.append({"source_text":chunk,"item_id":None,"item_name":name,"size":"","qty":round(qty,3),"rate":round(rate,2),"gst_rate":0,"match_confidence":0})
    return out


@app.post("/api/quick-bill/voice-parse")
async def quick_bill_voice_parse(request: Request):
    session=_session_row(request.cookies.get(COOKIE_NAME))
    if not session: return RedirectResponse("/owner-login",status_code=303)
    try:
        p=await request.json(); text=str(p.get("text") or ""); bill_type=str(p.get("bill_type") or "sale").lower()
        if bill_type not in {"sale","purchase"}: bill_type="sale"
        bid=int(session["business_id"])
        with db() as conn:
            items=[dict(r) for r in conn.execute("SELECT * FROM items WHERE business_id=? ORDER BY name,size,id",(bid,)).fetchall()]
            rows=_voice_rows(text,items,bill_type,conn,bid)
        return JSONResponse({"ok":True,"items":rows,"heard":text,"version":VERSION})
    except Exception as exc:
        return JSONResponse({"detail":f"Voice parse failed: {exc}"},status_code=400)


# Add continuous voice billing to the same Quick Write page.
html=quick_canvas.HTML
html=html.replace('<button class="btn secondary" id="eraser">🧽 Eraser</button>','<button class="btn secondary" id="eraser">🧽 Eraser</button><button class="btn secondary" id="voice">🎤 Voice Bill</button>')
voice_js=r'''
var SR=window.SpeechRecognition||window.webkitSpeechRecognition,rec=null,voiceOn=false;
function addVoiceRows(got){if(!got||!got.length)return;lines=lines.concat(got);render();show(got.length+' item voice se add hua. Bolte raho…')}
async function parseVoice(t){try{show('Suna: '+t);var r=await fetch('/api/quick-bill/voice-parse',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t,bill_type:q('type').value})});var d=await r.json();if(!r.ok)throw new Error(d.detail||'Voice parse failed');addVoiceRows(d.items||[])}catch(e){show(e.message||String(e),true)}}
q('voice').onclick=function(){if(!SR){show('Is phone/browser me voice recognition available nahi hai.',true);return}if(!rec){rec=new SR();rec.lang='hi-IN';rec.continuous=true;rec.interimResults=false;rec.onresult=function(e){for(var i=e.resultIndex;i<e.results.length;i++){if(e.results[i].isFinal)parseVoice(e.results[i][0].transcript)}};rec.onerror=function(e){show('Voice error: '+e.error,true)};rec.onend=function(){if(voiceOn){try{rec.start()}catch(_){}}}}voiceOn=!voiceOn;this.textContent=voiceOn?'⏹ Stop Voice':'🎤 Voice Bill';this.classList.toggle('eraser-on',voiceOn);if(voiceOn){show('Voice ON: bolo — “2 moong 100”, phir next item bolo.');try{rec.start()}catch(_){}}else{try{rec.stop()}catch(_){}}};
'''
html=html.replace("q('clear').onclick=clearPad;",voice_js+"q('clear').onclick=clearPad;")
html=html.replace('Likho: LEFT me Qty, MIDDLE me Item, RIGHT me Rate.','Likho: LEFT me Qty, MIDDLE me Item, RIGHT me Rate. Ya 🎤 Voice Bill me bolo: “2 moong 100”.')
quick_canvas.HTML=html
quick_canvas.VERSION=VERSION
